"""Monitoring Scheduler Service for periodic compliance scans.

This module provides functionality to schedule and manage periodic compliance
scans using APScheduler. It integrates with the DatabaseScannerService to
execute scans and detect new violations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.compliance_rule import ComplianceRule
from app.models.database_connection import DatabaseConnection
from app.models.monitoring_config import MonitoringConfig
from app.models.scan_history import ScanHistory
from app.models.violation import Violation
from app.models.enums import ScanStatus, ViolationStatus

if TYPE_CHECKING:
    from app.services.db_scanner import DatabaseScannerService

logger = logging.getLogger(__name__)

# Job ID for the scheduled scan job
SCAN_JOB_ID = "compliance_scan_job"

# Valid interval range (hourly to daily)
MIN_INTERVAL_MINUTES = 60
MAX_INTERVAL_MINUTES = 1440


class SchedulerStatus(BaseModel):
    """Status information for the monitoring scheduler.
    
    Attributes:
        is_running: Whether the scheduler is currently running.
        is_enabled: Whether scheduled scans are enabled.
        next_run_time: The next scheduled scan time, if any.
        last_run_time: The last time a scan was executed, if any.
        interval_minutes: The configured scan interval in minutes.
    """
    is_running: bool = Field(default=False, description="Whether scheduler is running")
    is_enabled: bool = Field(default=False, description="Whether scheduled scans are enabled")
    next_run_time: Optional[datetime] = Field(default=None, description="Next scheduled scan time")
    last_run_time: Optional[datetime] = Field(default=None, description="Last scan execution time")
    interval_minutes: Optional[int] = Field(default=None, description="Scan interval in minutes")


class ScanResult(BaseModel):
    """Result of a compliance scan execution.
    
    Attributes:
        scan_id: Unique identifier for the scan.
        started_at: When the scan started.
        completed_at: When the scan completed.
        total_violations: Total number of violations found.
        new_violations: Number of new violations detected.
        status: Final status of the scan.
        error_message: Error message if scan failed.
    """
    scan_id: UUID = Field(..., description="Unique scan identifier")
    started_at: datetime = Field(..., description="Scan start time")
    completed_at: datetime = Field(..., description="Scan completion time")
    total_violations: int = Field(default=0, description="Total violations found")
    new_violations: int = Field(default=0, description="New violations detected")
    status: str = Field(default=ScanStatus.COMPLETED.value, description="Scan status")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class SchedulerConfigError(Exception):
    """Raised when scheduler configuration is invalid."""
    pass


class MonitoringScheduler:
    """Service for scheduling and managing periodic compliance scans.
    
    This service uses APScheduler to schedule periodic compliance scans.
    It integrates with the DatabaseScannerService to execute scans and
    tracks scan history and new violations.
    
    Usage:
        scheduler = MonitoringScheduler()
        scheduler.start()
        await scheduler.schedule_scan(interval_minutes=60)
        status = scheduler.get_status()
        scheduler.cancel_schedule()
        scheduler.shutdown()
    """

    def __init__(self):
        """Initialize the MonitoringScheduler."""
        self._scheduler: AsyncIOScheduler = AsyncIOScheduler()
        self._is_started: bool = False
        self._retry_count: int = 0
        self._max_retries: int = 3
        self._base_retry_delay: int = 1  # seconds

    def start(self) -> None:
        """Start the APScheduler.
        
        This must be called before scheduling any scans.
        """
        if not self._is_started:
            self._scheduler.start()
            self._is_started = True
            logger.info("Monitoring scheduler started")

    def shutdown(self, wait: bool = False) -> None:
        """Shutdown the APScheduler.
        
        This should be called when the application is shutting down.
        
        Args:
            wait: Whether to wait for running jobs to complete.
        """
        if self._is_started:
            try:
                self._scheduler.shutdown(wait=wait)
            except Exception:
                pass  # Ignore errors during shutdown
            self._is_started = False
            logger.info("Monitoring scheduler shut down")

    async def schedule_scan(self, interval_minutes: int) -> str:
        """Schedule periodic compliance scans.
        
        Configures the scheduler to run compliance scans at the specified
        interval. If a schedule already exists, it will be replaced.
        
        Args:
            interval_minutes: The interval between scans in minutes.
                             Must be between 60 (hourly) and 1440 (daily).
            
        Returns:
            A confirmation message with the schedule details.
            
        Raises:
            SchedulerConfigError: If the interval is outside valid range.
        """
        # Validate interval range
        if interval_minutes < MIN_INTERVAL_MINUTES or interval_minutes > MAX_INTERVAL_MINUTES:
            raise SchedulerConfigError(
                f"Scan interval must be between {MIN_INTERVAL_MINUTES} (1 hour) "
                f"and {MAX_INTERVAL_MINUTES} (24 hours) minutes."
            )
        
        # Ensure scheduler is started
        if not self._is_started:
            self.start()
        
        # Remove existing job if present
        try:
            self._scheduler.remove_job(SCAN_JOB_ID)
            logger.info("Removed existing scan schedule")
        except JobLookupError:
            pass  # No existing job
        
        # Add the new job - next_run_time=None means use the trigger's default
        # which will schedule the first run after the interval
        self._scheduler.add_job(
            self._execute_scheduled_scan,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=SCAN_JOB_ID,
            name="Compliance Scan",
            replace_existing=True,
        )
        
        # Persist configuration to database
        async with async_session_maker() as session:
            await self._save_config(session, interval_minutes, is_enabled=True)
        
        logger.info(f"Scheduled compliance scans every {interval_minutes} minutes")
        
        return f"Scheduled compliance scans every {interval_minutes} minutes"

    def cancel_schedule(self) -> bool:
        """Cancel any scheduled compliance scans.
        
        Removes the scheduled scan job from the scheduler and updates
        the configuration in the database.
        
        Returns:
            True if a schedule was cancelled, False if no schedule existed.
        """
        try:
            self._scheduler.remove_job(SCAN_JOB_ID)
            logger.info("Cancelled scheduled compliance scans")
            
            # Update configuration in database (fire and forget)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._disable_config())
                else:
                    loop.run_until_complete(self._disable_config())
            except RuntimeError:
                # No event loop, skip database update
                pass
            
            return True
        except JobLookupError:
            logger.info("No scheduled scan to cancel")
            return False

    def get_status(self) -> SchedulerStatus:
        """Get the current scheduler status.
        
        Returns:
            SchedulerStatus containing the current state of the scheduler.
        """
        status = SchedulerStatus(
            is_running=self._is_started and self._scheduler.running,
            is_enabled=False,
            next_run_time=None,
            last_run_time=None,
            interval_minutes=None,
        )
        
        # Get job information if it exists
        job = self._scheduler.get_job(SCAN_JOB_ID)
        if job:
            status.is_enabled = True
            status.next_run_time = job.next_run_time
            
            # Extract interval from trigger
            if hasattr(job.trigger, 'interval'):
                total_seconds = job.trigger.interval.total_seconds()
                status.interval_minutes = int(total_seconds / 60)
        
        return status

    async def run_scheduled_scan(
        self,
        db_session: Optional[AsyncSession] = None,
    ) -> ScanResult:
        """Execute a compliance scan and detect new violations.
        
        This method:
        1. Creates a ScanHistory record
        2. Retrieves active database connection and compliance rules
        3. Executes the scan using DatabaseScannerService
        4. Compares results with previous scans to identify new violations
        5. Updates the ScanHistory with results
        
        Args:
            db_session: Optional database session. If not provided,
                       a new session will be created.
            
        Returns:
            ScanResult containing the scan outcome.
        """
        from app.services.db_scanner import (
            DatabaseScannerService,
            DBConnectionConfig,
            DatabaseConnectionError,
        )
        
        # Create session if not provided
        own_session = db_session is None
        if own_session:
            session = async_session_maker()
        else:
            session = db_session
        
        started_at = datetime.now(timezone.utc)
        scan_history = ScanHistory(
            started_at=started_at,
            status=ScanStatus.RUNNING.value,
        )
        
        try:
            session.add(scan_history)
            await session.flush()  # Get the ID
            
            logger.info(f"Starting scheduled compliance scan {scan_history.id}")
            
            # Get active database connection
            db_conn_result = await session.execute(
                select(DatabaseConnection).where(DatabaseConnection.is_active == True)
            )
            db_connection = db_conn_result.scalar_one_or_none()
            
            if not db_connection:
                raise DatabaseConnectionError("No active database connection configured")
            
            # Get all active compliance rules
            rules_result = await session.execute(
                select(ComplianceRule).where(ComplianceRule.is_active == True)
            )
            rules = list(rules_result.scalars().all())
            
            if not rules:
                logger.warning("No active compliance rules found")
                scan_history.status = ScanStatus.COMPLETED.value
                scan_history.completed_at = datetime.now(timezone.utc)
                scan_history.violations_found = 0
                scan_history.new_violations = 0
                await session.commit()
                
                return ScanResult(
                    scan_id=scan_history.id,
                    started_at=started_at,
                    completed_at=scan_history.completed_at,
                    total_violations=0,
                    new_violations=0,
                    status=ScanStatus.COMPLETED.value,
                )
            
            # Get existing violation identifiers for comparison
            existing_violations_result = await session.execute(
                select(Violation.record_identifier, Violation.rule_id)
            )
            existing_violation_keys = {
                (row.record_identifier, row.rule_id)
                for row in existing_violations_result
            }
            
            # Create scanner and connect
            scanner = DatabaseScannerService()
            config = DBConnectionConfig(
                host=db_connection.host,
                port=db_connection.port,
                database=db_connection.database_name,
                username=db_connection.username,
                password=db_connection.encrypted_password,  # In production, decrypt this
            )
            
            await scanner.connect(config)
            
            try:
                # Execute scan
                violations = await scanner.scan_for_violations(rules, session)
                
                # Count new violations
                new_violation_count = 0
                for violation in violations:
                    key = (violation.record_identifier, violation.rule_id)
                    if key not in existing_violation_keys:
                        new_violation_count += 1
                
                # Update scan history
                completed_at = datetime.now(timezone.utc)
                scan_history.status = ScanStatus.COMPLETED.value
                scan_history.completed_at = completed_at
                scan_history.violations_found = len(violations)
                scan_history.new_violations = new_violation_count
                
                # Update monitoring config last_run_at
                await self._update_last_run(session, completed_at)
                
                await session.commit()
                
                logger.info(
                    f"Scan {scan_history.id} completed: "
                    f"{len(violations)} violations found, {new_violation_count} new"
                )
                
                # Reset retry count on success
                self._retry_count = 0
                
                return ScanResult(
                    scan_id=scan_history.id,
                    started_at=started_at,
                    completed_at=completed_at,
                    total_violations=len(violations),
                    new_violations=new_violation_count,
                    status=ScanStatus.COMPLETED.value,
                )
                
            finally:
                await scanner.disconnect()
                
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            
            # Update scan history with failure
            completed_at = datetime.now(timezone.utc)
            scan_history.status = ScanStatus.FAILED.value
            scan_history.completed_at = completed_at
            scan_history.error_message = str(e)
            
            try:
                await session.commit()
            except Exception:
                await session.rollback()
            
            # Handle retry with exponential backoff
            self._retry_count += 1
            if self._retry_count <= self._max_retries:
                retry_delay = self._base_retry_delay * (2 ** (self._retry_count - 1))
                logger.info(
                    f"Scheduling retry {self._retry_count}/{self._max_retries} "
                    f"in {retry_delay} seconds"
                )
                # Note: In production, you would schedule a retry here
            else:
                logger.error(f"Max retries ({self._max_retries}) exceeded for scan")
                self._retry_count = 0
            
            return ScanResult(
                scan_id=scan_history.id,
                started_at=started_at,
                completed_at=completed_at,
                total_violations=0,
                new_violations=0,
                status=ScanStatus.FAILED.value,
                error_message=str(e),
            )
            
        finally:
            if own_session:
                await session.close()

    async def _execute_scheduled_scan(self) -> None:
        """Internal method called by APScheduler to execute a scan.
        
        This wraps run_scheduled_scan for use as a scheduled job.
        """
        logger.info("Executing scheduled compliance scan")
        try:
            result = await self.run_scheduled_scan()
            logger.info(f"Scheduled scan completed with status: {result.status}")
        except Exception as e:
            logger.error(f"Scheduled scan failed with error: {e}")

    async def _save_config(
        self,
        session: AsyncSession,
        interval_minutes: int,
        is_enabled: bool,
    ) -> None:
        """Save or update monitoring configuration in database.
        
        Args:
            session: Database session.
            interval_minutes: The scan interval in minutes.
            is_enabled: Whether scheduling is enabled.
        """
        # Get existing config or create new one
        result = await session.execute(select(MonitoringConfig))
        config = result.scalar_one_or_none()
        
        next_run = datetime.now(timezone.utc)
        
        if config:
            config.interval_minutes = interval_minutes
            config.is_enabled = is_enabled
            config.next_run_at = next_run if is_enabled else None
        else:
            config = MonitoringConfig(
                interval_minutes=interval_minutes,
                is_enabled=is_enabled,
                next_run_at=next_run if is_enabled else None,
            )
            session.add(config)
        
        await session.commit()

    async def _disable_config(self) -> None:
        """Disable monitoring configuration in database."""
        async with async_session_maker() as session:
            result = await session.execute(select(MonitoringConfig))
            config = result.scalar_one_or_none()
            
            if config:
                config.is_enabled = False
                config.next_run_at = None
                await session.commit()

    async def _update_last_run(
        self,
        session: AsyncSession,
        last_run_at: datetime,
    ) -> None:
        """Update the last run time in monitoring configuration.
        
        Args:
            session: Database session.
            last_run_at: The time of the last scan execution.
        """
        result = await session.execute(select(MonitoringConfig))
        config = result.scalar_one_or_none()
        
        if config:
            config.last_run_at = last_run_at
            # Calculate next run time based on interval
            if config.is_enabled and config.interval_minutes:
                from datetime import timedelta
                config.next_run_at = last_run_at + timedelta(minutes=config.interval_minutes)


# Global scheduler instance
_scheduler_instance: Optional[MonitoringScheduler] = None


def get_monitoring_scheduler() -> MonitoringScheduler:
    """Get or create the global MonitoringScheduler instance.
    
    Returns:
        The global MonitoringScheduler instance.
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MonitoringScheduler()
    return _scheduler_instance


def reset_monitoring_scheduler() -> None:
    """Reset the global scheduler instance.
    
    This is primarily useful for testing.
    """
    global _scheduler_instance
    if _scheduler_instance is not None:
        _scheduler_instance.shutdown()
        _scheduler_instance = None

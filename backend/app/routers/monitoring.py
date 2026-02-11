"""Monitoring API routes for scheduler management.

This module provides FastAPI endpoints for managing the monitoring scheduler:
- Get scheduler status
- Configure scan schedule
- Disable scheduled scans

Requirements: 5.1, 5.6
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.services.scheduler import (
    MonitoringScheduler,
    SchedulerConfigError,
    SchedulerStatus,
    get_monitoring_scheduler,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


# Pydantic Models

class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status.
    
    Attributes:
        is_running: Whether the scheduler is currently running.
        is_enabled: Whether scheduled scans are enabled.
        next_run_time: The next scheduled scan time, if any.
        last_run_time: The last time a scan was executed, if any.
        interval_minutes: The configured scan interval in minutes.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    is_running: bool = Field(
        default=False,
        description="Whether the scheduler is currently running",
    )
    is_enabled: bool = Field(
        default=False,
        description="Whether scheduled scans are enabled",
    )
    next_run_time: Optional[datetime] = Field(
        default=None,
        description="The next scheduled scan time",
    )
    last_run_time: Optional[datetime] = Field(
        default=None,
        description="The last time a scan was executed",
    )
    interval_minutes: Optional[int] = Field(
        default=None,
        description="The configured scan interval in minutes",
    )


class ScheduleConfigRequest(BaseModel):
    """Request model for configuring the scan schedule.
    
    Attributes:
        interval_minutes: The interval between scans in minutes.
                         Must be between 60 (hourly) and 1440 (daily).
    """
    
    interval_minutes: int = Field(
        ...,
        ge=MIN_INTERVAL_MINUTES,
        le=MAX_INTERVAL_MINUTES,
        description=f"Scan interval in minutes ({MIN_INTERVAL_MINUTES}-{MAX_INTERVAL_MINUTES})",
    )


class ScheduleConfigResponse(BaseModel):
    """Response model for schedule configuration.
    
    Attributes:
        id: A placeholder ID for the configuration.
        interval_minutes: The configured scan interval.
        is_enabled: Whether scheduling is now enabled.
        next_run_at: The next scheduled scan time.
        last_run_at: The last scan execution time.
    """
    
    id: str = Field(default="monitoring-config", description="Configuration identifier")
    interval_minutes: int = Field(..., description="Configured scan interval in minutes")
    is_enabled: bool = Field(default=True, description="Whether scheduling is enabled")
    next_run_at: Optional[datetime] = Field(default=None, description="Next scheduled scan time")
    last_run_at: Optional[datetime] = Field(default=None, description="Last scan execution time")


class ScheduleDisableResponse(BaseModel):
    """Response model for disabling the schedule.
    
    Attributes:
        message: Confirmation message.
        was_enabled: Whether a schedule was previously enabled.
    """
    
    message: str = Field(..., description="Confirmation message")
    was_enabled: bool = Field(..., description="Whether a schedule was previously enabled")


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


# Dependency

def get_scheduler() -> MonitoringScheduler:
    """Dependency to get the monitoring scheduler instance.
    
    Returns:
        The global MonitoringScheduler instance.
    """
    return get_monitoring_scheduler()


# API Endpoints

@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
    description="Retrieve the current status of the monitoring scheduler including "
                "whether it's running, enabled, and the next/last run times.",
)
async def get_status(
    scheduler: MonitoringScheduler = Depends(get_scheduler),
) -> SchedulerStatusResponse:
    """Get the current scheduler status.
    
    Returns the current state of the monitoring scheduler including:
    - Whether the scheduler is running
    - Whether scheduled scans are enabled
    - The next scheduled scan time (if any)
    - The last scan execution time (if any)
    - The configured scan interval in minutes
    
    Args:
        scheduler: The monitoring scheduler instance (injected)
        
    Returns:
        SchedulerStatusResponse with current scheduler state
    """
    status = scheduler.get_status()
    
    logger.info(
        f"Scheduler status requested: running={status.is_running}, "
        f"enabled={status.is_enabled}, interval={status.interval_minutes}"
    )
    
    return SchedulerStatusResponse(
        is_running=status.is_running,
        is_enabled=status.is_enabled,
        next_run_time=status.next_run_time,
        last_run_time=status.last_run_time,
        interval_minutes=status.interval_minutes,
    )


@router.post(
    "/schedule",
    response_model=ScheduleConfigResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid interval configuration"},
    },
    summary="Configure scan schedule",
    description="Configure the monitoring scheduler to run compliance scans at the "
                "specified interval. Valid intervals are between 60 (hourly) and "
                "1440 (daily) minutes.",
)
async def configure_schedule(
    config: ScheduleConfigRequest,
    scheduler: MonitoringScheduler = Depends(get_scheduler),
) -> ScheduleConfigResponse:
    """Configure the scan schedule.
    
    Sets up the monitoring scheduler to run compliance scans at the specified
    interval. If a schedule already exists, it will be replaced with the new
    configuration.
    
    Args:
        config: The schedule configuration containing interval_minutes
        scheduler: The monitoring scheduler instance (injected)
        
    Returns:
        ScheduleConfigResponse with confirmation and configuration details
        
    Raises:
        HTTPException: 400 if the interval is outside the valid range
    """
    try:
        message = await scheduler.schedule_scan(config.interval_minutes)
        
        logger.info(f"Schedule configured: interval={config.interval_minutes} minutes")
        
        # Get the updated status to return next_run_at and last_run_at
        scheduler_status = scheduler.get_status()
        
        return ScheduleConfigResponse(
            id="monitoring-config",
            interval_minutes=config.interval_minutes,
            is_enabled=True,
            next_run_at=scheduler_status.next_run_time,
            last_run_at=scheduler_status.last_run_time,
        )
    except SchedulerConfigError as e:
        logger.warning(f"Invalid schedule configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/schedule",
    response_model=ScheduleDisableResponse,
    summary="Disable scheduled scans",
    description="Disable any scheduled compliance scans. This cancels the current "
                "schedule but does not affect the scheduler itself.",
)
async def disable_schedule(
    scheduler: MonitoringScheduler = Depends(get_scheduler),
) -> ScheduleDisableResponse:
    """Disable scheduled scans.
    
    Cancels any currently scheduled compliance scans. The scheduler remains
    running but no automatic scans will be triggered until a new schedule
    is configured.
    
    Args:
        scheduler: The monitoring scheduler instance (injected)
        
    Returns:
        ScheduleDisableResponse with confirmation and previous state
    """
    was_enabled = scheduler.cancel_schedule()
    
    if was_enabled:
        message = "Scheduled scans have been disabled"
        logger.info("Scheduled scans disabled")
    else:
        message = "No scheduled scans were active"
        logger.info("No scheduled scans to disable")
    
    return ScheduleDisableResponse(
        message=message,
        was_enabled=was_enabled,
    )

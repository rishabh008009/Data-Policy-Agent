"""Dashboard API routes for compliance overview and statistics.

This module provides FastAPI endpoints for the compliance dashboard:
- Get compliance summary statistics (total violations by status and severity)
- Get last scan time and next scheduled scan time
- Get violation trends over time with improvement/degradation indicators
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance_rule import ComplianceRule
from app.models.enums import Severity, ViolationStatus
from app.models.monitoring_config import MonitoringConfig
from app.models.policy import Policy
from app.models.scan_history import ScanHistory
from app.models.violation import Violation
from app.services.scheduler import get_monitoring_scheduler


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# Pydantic Models

class ViolationsByStatus(BaseModel):
    """Violation counts grouped by status."""
    
    pending: int = Field(default=0, description="Number of pending violations")
    confirmed: int = Field(default=0, description="Number of confirmed violations")
    false_positive: int = Field(default=0, description="Number of false positive violations")
    resolved: int = Field(default=0, description="Number of resolved violations")


class ViolationsBySeverity(BaseModel):
    """Violation counts grouped by severity."""
    
    low: int = Field(default=0, description="Number of low severity violations")
    medium: int = Field(default=0, description="Number of medium severity violations")
    high: int = Field(default=0, description="Number of high severity violations")
    critical: int = Field(default=0, description="Number of critical severity violations")


class DashboardSummaryResponse(BaseModel):
    """Response model for dashboard summary statistics.
    
    Provides an overview of the compliance posture including:
    - Total violation count
    - Violations grouped by status (flat fields)
    - Violations grouped by severity
    - Last scan timestamp
    - Next scheduled scan timestamp
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    total_violations: int = Field(
        default=0,
        description="Total number of violations in the system",
    )
    total_policies: int = Field(
        default=0,
        description="Total number of uploaded policies",
    )
    total_rules: int = Field(
        default=0,
        description="Total number of extracted compliance rules",
    )
    total_transactions: int = Field(
        default=0,
        description="Total number of transactions in the database",
    )
    pending_count: int = Field(
        default=0,
        description="Number of pending violations",
    )
    confirmed_count: int = Field(
        default=0,
        description="Number of confirmed violations",
    )
    resolved_count: int = Field(
        default=0,
        description="Number of resolved violations",
    )
    false_positive_count: int = Field(
        default=0,
        description="Number of false positive violations",
    )
    by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Violation counts grouped by severity",
    )
    last_scan_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the most recent compliance scan",
    )
    next_scan_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the next scheduled compliance scan",
    )


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


# API Endpoints

@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get compliance overview statistics",
    description="Retrieve a summary of compliance status including total violations, "
                "violations by status and severity, and scan timing information.",
)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Get compliance overview statistics for the dashboard.
    
    This endpoint provides:
    - Total count of all violations
    - Violations grouped by status (pending, confirmed, false_positive, resolved)
    - Violations grouped by severity (low, medium, high, critical)
    - Timestamp of the last completed scan
    - Timestamp of the next scheduled scan
    
    Args:
        db: Database session (injected)
        
    Returns:
        DashboardSummaryResponse with compliance overview statistics
        
    Raises:
        HTTPException: 500 if there's an error retrieving statistics
    """
    try:
        # Get total violations count
        total_result = await db.execute(
            select(func.count(Violation.id))
        )
        total_violations = total_result.scalar() or 0
        
        # Get total policies count
        policies_result = await db.execute(
            select(func.count(Policy.id))
        )
        total_policies = policies_result.scalar() or 0
        
        # Get total rules count
        rules_result = await db.execute(
            select(func.count(ComplianceRule.id))
        )
        total_rules = rules_result.scalar() or 0
        
        # Get total transactions count
        from sqlalchemy import text
        try:
            tx_result = await db.execute(text("SELECT count(*) FROM transactions"))
            total_transactions = tx_result.scalar() or 0
        except Exception:
            total_transactions = 0
        
        # Get violations count by status
        status_counts = await _get_violations_by_status(db)
        
        # Get violations count by severity
        severity_counts = await _get_violations_by_severity(db)
        
        # Get last scan time from scan history
        last_scan_at = await _get_last_scan_time(db)
        
        # Get next scheduled scan time from monitoring config and scheduler
        next_scan_at = await _get_next_scan_time(db)
        
        logger.info(
            f"Dashboard summary retrieved: {total_violations} total violations, "
            f"last_scan={last_scan_at}, next_scan={next_scan_at}"
        )
        
        return DashboardSummaryResponse(
            total_violations=total_violations,
            total_policies=total_policies,
            total_rules=total_rules,
            total_transactions=total_transactions,
            pending_count=status_counts.pending,
            confirmed_count=status_counts.confirmed,
            resolved_count=status_counts.resolved,
            false_positive_count=status_counts.false_positive,
            by_severity={
                "low": severity_counts.low,
                "medium": severity_counts.medium,
                "high": severity_counts.high,
                "critical": severity_counts.critical,
            },
            last_scan_at=last_scan_at,
            next_scan_at=next_scan_at,
        )
        
    except Exception as e:
        logger.error(f"Error retrieving dashboard summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard summary: {str(e)}",
        )


async def _get_violations_by_status(db: AsyncSession) -> ViolationsByStatus:
    """Get violation counts grouped by status.
    
    Args:
        db: Database session
        
    Returns:
        ViolationsByStatus with counts for each status
    """
    # Query to get counts grouped by status
    result = await db.execute(
        select(
            Violation.status,
            func.count(Violation.id).label("count"),
        ).group_by(Violation.status)
    )
    
    # Initialize counts
    counts = {
        ViolationStatus.PENDING.value: 0,
        ViolationStatus.CONFIRMED.value: 0,
        ViolationStatus.FALSE_POSITIVE.value: 0,
        ViolationStatus.RESOLVED.value: 0,
    }
    
    # Populate counts from query results
    for row in result:
        if row.status in counts:
            counts[row.status] = row.count
    
    return ViolationsByStatus(
        pending=counts[ViolationStatus.PENDING.value],
        confirmed=counts[ViolationStatus.CONFIRMED.value],
        false_positive=counts[ViolationStatus.FALSE_POSITIVE.value],
        resolved=counts[ViolationStatus.RESOLVED.value],
    )


async def _get_violations_by_severity(db: AsyncSession) -> ViolationsBySeverity:
    """Get violation counts grouped by severity.
    
    Args:
        db: Database session
        
    Returns:
        ViolationsBySeverity with counts for each severity level
    """
    # Query to get counts grouped by severity
    result = await db.execute(
        select(
            Violation.severity,
            func.count(Violation.id).label("count"),
        ).group_by(Violation.severity)
    )
    
    # Initialize counts
    counts = {
        Severity.LOW.value: 0,
        Severity.MEDIUM.value: 0,
        Severity.HIGH.value: 0,
        Severity.CRITICAL.value: 0,
    }
    
    # Populate counts from query results
    for row in result:
        if row.severity in counts:
            counts[row.severity] = row.count
    
    return ViolationsBySeverity(
        low=counts[Severity.LOW.value],
        medium=counts[Severity.MEDIUM.value],
        high=counts[Severity.HIGH.value],
        critical=counts[Severity.CRITICAL.value],
    )


async def _get_last_scan_time(db: AsyncSession) -> Optional[datetime]:
    """Get the timestamp of the most recent completed scan.
    
    Args:
        db: Database session
        
    Returns:
        Datetime of the last completed scan, or None if no scans exist
    """
    result = await db.execute(
        select(ScanHistory.completed_at)
        .where(ScanHistory.completed_at.isnot(None))
        .order_by(ScanHistory.completed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def _get_next_scan_time(db: AsyncSession) -> Optional[datetime]:
    """Get the timestamp of the next scheduled scan.
    
    First checks the scheduler for the actual next run time,
    then falls back to the monitoring config if scheduler info unavailable.
    
    Args:
        db: Database session
        
    Returns:
        Datetime of the next scheduled scan, or None if no scan is scheduled
    """
    # First try to get from the scheduler (most accurate)
    try:
        scheduler = get_monitoring_scheduler()
        scheduler_status = scheduler.get_status()
        if scheduler_status.is_enabled and scheduler_status.next_run_time:
            return scheduler_status.next_run_time
    except Exception as e:
        logger.warning(f"Could not get scheduler status: {e}")
    
    # Fall back to monitoring config
    result = await db.execute(
        select(MonitoringConfig)
        .where(MonitoringConfig.is_enabled == True)
        .limit(1)
    )
    config = result.scalar_one_or_none()
    
    if config and config.next_run_at:
        return config.next_run_at
    
    return None


# =============================================================================
# Trends API Models and Endpoint
# =============================================================================

class TimeRange(str, Enum):
    """Supported time ranges for trend analysis."""
    
    LAST_7_DAYS = "7d"
    LAST_14_DAYS = "14d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"


class TrendBucket(str, Enum):
    """Time bucket granularity for trend data."""
    
    DAILY = "daily"
    WEEKLY = "weekly"


class TrendIndicator(str, Enum):
    """Indicator for compliance trend direction."""
    
    IMPROVEMENT = "improvement"
    DEGRADATION = "degradation"
    STABLE = "stable"


class TrendDataPoint(BaseModel):
    """A single data point in the trend timeline.
    
    Represents violation counts for a specific time period (day or week).
    """
    
    date: str = Field(
        description="Date string in ISO format (YYYY-MM-DD) representing the start of the period",
    )
    total_violations: int = Field(
        default=0,
        description="Total number of violations detected in this period",
    )
    new_violations: int = Field(
        default=0,
        description="Number of new violations detected in this period",
    )
    resolved_violations: int = Field(
        default=0,
        description="Number of violations resolved in this period",
    )


class TrendSummary(BaseModel):
    """Summary statistics for the trend period.
    
    Provides aggregate metrics and comparison with previous period.
    """
    
    current_period_total: int = Field(
        default=0,
        description="Total violations in the current period",
    )
    previous_period_total: int = Field(
        default=0,
        description="Total violations in the previous period (for comparison)",
    )
    percentage_change: Optional[float] = Field(
        default=None,
        description="Percentage change from previous period. Positive means more violations (degradation), negative means fewer (improvement). None if previous period had 0 violations.",
    )
    trend_indicator: TrendIndicator = Field(
        default=TrendIndicator.STABLE,
        description="Indicator showing whether compliance is improving, degrading, or stable",
    )
    total_new_violations: int = Field(
        default=0,
        description="Total new violations detected in the current period",
    )
    total_resolved_violations: int = Field(
        default=0,
        description="Total violations resolved in the current period",
    )


class TrendsResponse(BaseModel):
    """Response model for violation trends over time.
    
    Provides time-series data showing violation counts and a summary
    with improvement/degradation indicators.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    time_range: str = Field(
        description="The time range for this trend data (e.g., '7d', '30d')",
    )
    bucket: str = Field(
        description="The time bucket granularity ('daily' or 'weekly')",
    )
    data_points: List[TrendDataPoint] = Field(
        default_factory=list,
        description="List of data points showing violations over time",
    )
    summary: TrendSummary = Field(
        default_factory=TrendSummary,
        description="Summary statistics including percentage change and trend indicator",
    )


@router.get(
    "/trends",
    response_model=TrendsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get violation trends over time",
    description="Retrieve violation trends showing counts over time with "
                "improvement/degradation percentages. Supports daily or weekly buckets.",
)
async def get_dashboard_trends(
    db: AsyncSession = Depends(get_db),
    time_range: TimeRange = Query(
        default=TimeRange.LAST_7_DAYS,
        description="Time range for trend data",
    ),
    bucket: TrendBucket = Query(
        default=TrendBucket.DAILY,
        description="Time bucket granularity (daily or weekly)",
    ),
) -> TrendsResponse:
    """Get violation trends over time for the dashboard.
    
    This endpoint provides:
    - Time-series data of violation counts (daily or weekly buckets)
    - Comparison with previous period
    - Percentage change calculation
    - Improvement/degradation indicator
    
    Args:
        db: Database session (injected)
        time_range: Time range for trend data (7d, 14d, 30d, 90d)
        bucket: Time bucket granularity (daily or weekly)
        
    Returns:
        TrendsResponse with trend data and summary statistics
        
    Raises:
        HTTPException: 400 if parameters are invalid
        HTTPException: 500 if there's an error retrieving trends
    """
    try:
        # Calculate date ranges
        now = datetime.now(timezone.utc)
        days = _get_days_from_time_range(time_range)
        
        current_period_start = now - timedelta(days=days)
        previous_period_start = current_period_start - timedelta(days=days)
        previous_period_end = current_period_start
        
        # Get data points for current period
        data_points = await _get_trend_data_points(
            db, current_period_start, now, bucket
        )
        
        # Calculate summary statistics
        summary = await _calculate_trend_summary(
            db,
            current_period_start,
            now,
            previous_period_start,
            previous_period_end,
        )
        
        logger.info(
            f"Trends retrieved: time_range={time_range.value}, bucket={bucket.value}, "
            f"data_points={len(data_points)}, change={summary.percentage_change}%"
        )
        
        return TrendsResponse(
            time_range=time_range.value,
            bucket=bucket.value,
            data_points=data_points,
            summary=summary,
        )
        
    except ValueError as e:
        logger.error(f"Invalid parameters for trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving dashboard trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard trends: {str(e)}",
        )


def _get_days_from_time_range(time_range: TimeRange) -> int:
    """Convert time range enum to number of days.
    
    Args:
        time_range: Time range enum value
        
    Returns:
        Number of days for the time range
    """
    mapping = {
        TimeRange.LAST_7_DAYS: 7,
        TimeRange.LAST_14_DAYS: 14,
        TimeRange.LAST_30_DAYS: 30,
        TimeRange.LAST_90_DAYS: 90,
    }
    return mapping[time_range]


async def _get_trend_data_points(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    bucket: TrendBucket,
) -> List[TrendDataPoint]:
    """Get trend data points for the specified period.
    
    Groups violations by day or week and returns counts for each period.
    
    Args:
        db: Database session
        start_date: Start of the period
        end_date: End of the period
        bucket: Time bucket granularity
        
    Returns:
        List of TrendDataPoint objects
    """
    # Generate all dates/weeks in the range
    data_points = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if bucket == TrendBucket.WEEKLY:
        # Align to start of week (Monday)
        current = current - timedelta(days=current.weekday())
        step = timedelta(days=7)
    else:
        step = timedelta(days=1)
    
    # Query for new violations (detected_at in period)
    new_violations_query = await db.execute(
        select(
            cast(Violation.detected_at, Date).label("date"),
            func.count(Violation.id).label("count"),
        )
        .where(
            and_(
                Violation.detected_at >= start_date,
                Violation.detected_at < end_date,
            )
        )
        .group_by(cast(Violation.detected_at, Date))
    )
    new_violations_by_date = {
        row.date: row.count for row in new_violations_query
    }
    
    # Query for resolved violations (resolved_at in period)
    resolved_violations_query = await db.execute(
        select(
            cast(Violation.resolved_at, Date).label("date"),
            func.count(Violation.id).label("count"),
        )
        .where(
            and_(
                Violation.resolved_at >= start_date,
                Violation.resolved_at < end_date,
                Violation.resolved_at.isnot(None),
            )
        )
        .group_by(cast(Violation.resolved_at, Date))
    )
    resolved_violations_by_date = {
        row.date: row.count for row in resolved_violations_query
    }
    
    # Build data points
    while current < end_date:
        period_end = current + step
        if period_end > end_date:
            period_end = end_date
        
        # Sum violations for this bucket
        new_count = 0
        resolved_count = 0
        
        bucket_current = current
        while bucket_current < period_end:
            date_key = bucket_current.date()
            new_count += new_violations_by_date.get(date_key, 0)
            resolved_count += resolved_violations_by_date.get(date_key, 0)
            bucket_current += timedelta(days=1)
        
        data_points.append(TrendDataPoint(
            date=current.strftime("%Y-%m-%d"),
            total_violations=new_count,  # For simplicity, using new violations as total for the period
            new_violations=new_count,
            resolved_violations=resolved_count,
        ))
        
        current = period_end if bucket == TrendBucket.DAILY else current + step
        
        # Prevent infinite loop
        if bucket == TrendBucket.DAILY and current >= end_date:
            break
    
    return data_points


async def _calculate_trend_summary(
    db: AsyncSession,
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
) -> TrendSummary:
    """Calculate trend summary statistics.
    
    Compares current period with previous period to determine
    improvement or degradation.
    
    Args:
        db: Database session
        current_start: Start of current period
        current_end: End of current period
        previous_start: Start of previous period
        previous_end: End of previous period
        
    Returns:
        TrendSummary with comparison statistics
    """
    # Count violations detected in current period
    current_result = await db.execute(
        select(func.count(Violation.id))
        .where(
            and_(
                Violation.detected_at >= current_start,
                Violation.detected_at < current_end,
            )
        )
    )
    current_total = current_result.scalar() or 0
    
    # Count violations detected in previous period
    previous_result = await db.execute(
        select(func.count(Violation.id))
        .where(
            and_(
                Violation.detected_at >= previous_start,
                Violation.detected_at < previous_end,
            )
        )
    )
    previous_total = previous_result.scalar() or 0
    
    # Count new violations in current period
    new_violations_result = await db.execute(
        select(func.count(Violation.id))
        .where(
            and_(
                Violation.detected_at >= current_start,
                Violation.detected_at < current_end,
            )
        )
    )
    total_new = new_violations_result.scalar() or 0
    
    # Count resolved violations in current period
    resolved_result = await db.execute(
        select(func.count(Violation.id))
        .where(
            and_(
                Violation.resolved_at >= current_start,
                Violation.resolved_at < current_end,
                Violation.resolved_at.isnot(None),
            )
        )
    )
    total_resolved = resolved_result.scalar() or 0
    
    # Calculate percentage change
    # Formula: ((current - previous) / previous) * 100
    # Positive = more violations (degradation)
    # Negative = fewer violations (improvement)
    percentage_change: Optional[float] = None
    trend_indicator = TrendIndicator.STABLE
    
    if previous_total > 0:
        percentage_change = round(
            ((current_total - previous_total) / previous_total) * 100,
            2
        )
        
        # Determine trend indicator
        # Using 5% threshold for stability
        if percentage_change > 5:
            trend_indicator = TrendIndicator.DEGRADATION
        elif percentage_change < -5:
            trend_indicator = TrendIndicator.IMPROVEMENT
        else:
            trend_indicator = TrendIndicator.STABLE
    elif current_total > 0:
        # Previous was 0, current has violations = degradation
        trend_indicator = TrendIndicator.DEGRADATION
    # else: both are 0, stable
    
    return TrendSummary(
        current_period_total=current_total,
        previous_period_total=previous_total,
        percentage_change=percentage_change,
        trend_indicator=trend_indicator,
        total_new_violations=total_new,
        total_resolved_violations=total_resolved,
    )

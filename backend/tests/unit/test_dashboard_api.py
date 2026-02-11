"""Unit tests for the Dashboard API endpoints."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.enums import Severity, ViolationStatus, ScanStatus
from app.models.monitoring_config import MonitoringConfig
from app.models.scan_history import ScanHistory
from app.models.violation import Violation
from app.routers.dashboard import (
    DashboardSummaryResponse,
    ViolationsByStatus,
    ViolationsBySeverity,
)


# Test fixtures

@pytest.fixture
def sample_violations():
    """Create sample violations with various statuses and severities."""
    violations = []
    
    # Pending violations
    for i in range(3):
        v = Violation(
            rule_id=uuid.uuid4(),
            record_identifier=f"record_pending_{i}",
            record_data={"id": f"record_pending_{i}"},
            justification="Test justification",
            severity=Severity.HIGH.value,
            status=ViolationStatus.PENDING.value,
        )
        v.id = uuid.uuid4()
        v.detected_at = datetime.now(timezone.utc)
        violations.append(v)
    
    # Confirmed violations
    for i in range(2):
        v = Violation(
            rule_id=uuid.uuid4(),
            record_identifier=f"record_confirmed_{i}",
            record_data={"id": f"record_confirmed_{i}"},
            justification="Test justification",
            severity=Severity.CRITICAL.value,
            status=ViolationStatus.CONFIRMED.value,
        )
        v.id = uuid.uuid4()
        v.detected_at = datetime.now(timezone.utc)
        violations.append(v)
    
    # False positive violations
    v = Violation(
        rule_id=uuid.uuid4(),
        record_identifier="record_fp_0",
        record_data={"id": "record_fp_0"},
        justification="Test justification",
        severity=Severity.LOW.value,
        status=ViolationStatus.FALSE_POSITIVE.value,
    )
    v.id = uuid.uuid4()
    v.detected_at = datetime.now(timezone.utc)
    violations.append(v)
    
    # Resolved violations
    for i in range(4):
        v = Violation(
            rule_id=uuid.uuid4(),
            record_identifier=f"record_resolved_{i}",
            record_data={"id": f"record_resolved_{i}"},
            justification="Test justification",
            severity=Severity.MEDIUM.value,
            status=ViolationStatus.RESOLVED.value,
        )
        v.id = uuid.uuid4()
        v.detected_at = datetime.now(timezone.utc) - timedelta(days=1)
        v.resolved_at = datetime.now(timezone.utc)
        violations.append(v)
    
    return violations


@pytest.fixture
def sample_scan_history():
    """Create sample scan history records."""
    scans = []
    
    # Completed scan
    scan1 = ScanHistory(
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1, minutes=55),
        status=ScanStatus.COMPLETED.value,
        violations_found=10,
        new_violations=3,
    )
    scan1.id = uuid.uuid4()
    scans.append(scan1)
    
    # Another completed scan (more recent)
    scan2 = ScanHistory(
        started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        completed_at=datetime.now(timezone.utc) - timedelta(minutes=25),
        status=ScanStatus.COMPLETED.value,
        violations_found=12,
        new_violations=2,
    )
    scan2.id = uuid.uuid4()
    scans.append(scan2)
    
    return scans


@pytest.fixture
def sample_monitoring_config():
    """Create sample monitoring configuration."""
    config = MonitoringConfig(
        interval_minutes=60,
        is_enabled=True,
        next_run_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        last_run_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    config.id = uuid.uuid4()
    return config


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


class TestGetDashboardSummary:
    """Tests for GET /api/dashboard/summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary_empty_database(self, mock_db_session):
        """Test getting summary when no violations exist."""
        # Mock total count query
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 0
        
        # Mock status count query (empty)
        mock_status_result = MagicMock()
        mock_status_result.__iter__ = lambda self: iter([])
        
        # Mock severity count query (empty)
        mock_severity_result = MagicMock()
        mock_severity_result.__iter__ = lambda self: iter([])
        
        # Mock last scan query (no scans)
        mock_scan_result = MagicMock()
        mock_scan_result.scalar_one_or_none.return_value = None
        
        # Mock monitoring config query (no config)
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None
        
        # Setup execute to return different results for different queries
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_severity_result,
            mock_scan_result,
            mock_config_result,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        # Mock the scheduler
        with patch('app.routers.dashboard.get_monitoring_scheduler') as mock_scheduler:
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = MagicMock(
                is_enabled=False,
                next_run_time=None,
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/dashboard/summary")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["total_violations"] == 0
                assert data["pending_count"] == 0
                assert data["confirmed_count"] == 0
                assert data["false_positive_count"] == 0
                assert data["resolved_count"] == 0
                assert data["by_severity"]["low"] == 0
                assert data["by_severity"]["medium"] == 0
                assert data["by_severity"]["high"] == 0
                assert data["by_severity"]["critical"] == 0
                assert data["last_scan_at"] is None
                assert data["next_scan_at"] is None
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_summary_with_violations(self, mock_db_session, sample_violations):
        """Test getting summary with existing violations."""
        # Mock total count query
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 10  # Total violations
        
        # Mock status count query
        mock_status_result = MagicMock()
        status_rows = [
            MagicMock(status=ViolationStatus.PENDING.value, count=3),
            MagicMock(status=ViolationStatus.CONFIRMED.value, count=2),
            MagicMock(status=ViolationStatus.FALSE_POSITIVE.value, count=1),
            MagicMock(status=ViolationStatus.RESOLVED.value, count=4),
        ]
        mock_status_result.__iter__ = lambda self: iter(status_rows)
        
        # Mock severity count query
        mock_severity_result = MagicMock()
        severity_rows = [
            MagicMock(severity=Severity.LOW.value, count=1),
            MagicMock(severity=Severity.MEDIUM.value, count=4),
            MagicMock(severity=Severity.HIGH.value, count=3),
            MagicMock(severity=Severity.CRITICAL.value, count=2),
        ]
        mock_severity_result.__iter__ = lambda self: iter(severity_rows)
        
        # Mock last scan query
        last_scan_time = datetime.now(timezone.utc) - timedelta(minutes=25)
        mock_scan_result = MagicMock()
        mock_scan_result.scalar_one_or_none.return_value = last_scan_time
        
        # Mock monitoring config query
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None
        
        # Setup execute to return different results for different queries
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_severity_result,
            mock_scan_result,
            mock_config_result,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        # Mock the scheduler
        next_scan_time = datetime.now(timezone.utc) + timedelta(minutes=35)
        with patch('app.routers.dashboard.get_monitoring_scheduler') as mock_scheduler:
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = MagicMock(
                is_enabled=True,
                next_run_time=next_scan_time,
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/dashboard/summary")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                # Check total
                assert data["total_violations"] == 10
                
                # Check by status (flat fields)
                assert data["pending_count"] == 3
                assert data["confirmed_count"] == 2
                assert data["false_positive_count"] == 1
                assert data["resolved_count"] == 4
                
                # Check by severity
                assert data["by_severity"]["low"] == 1
                assert data["by_severity"]["medium"] == 4
                assert data["by_severity"]["high"] == 3
                assert data["by_severity"]["critical"] == 2
                
                # Check scan times
                assert data["last_scan_at"] is not None
                assert data["next_scan_at"] is not None
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_summary_scheduler_disabled(self, mock_db_session):
        """Test getting summary when scheduler is disabled."""
        # Mock total count query
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 5
        
        # Mock status count query
        mock_status_result = MagicMock()
        status_rows = [
            MagicMock(status=ViolationStatus.PENDING.value, count=5),
        ]
        mock_status_result.__iter__ = lambda self: iter(status_rows)
        
        # Mock severity count query
        mock_severity_result = MagicMock()
        severity_rows = [
            MagicMock(severity=Severity.HIGH.value, count=5),
        ]
        mock_severity_result.__iter__ = lambda self: iter(severity_rows)
        
        # Mock last scan query
        mock_scan_result = MagicMock()
        mock_scan_result.scalar_one_or_none.return_value = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Mock monitoring config query (disabled)
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_severity_result,
            mock_scan_result,
            mock_config_result,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        # Mock the scheduler as disabled
        with patch('app.routers.dashboard.get_monitoring_scheduler') as mock_scheduler:
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = MagicMock(
                is_enabled=False,
                next_run_time=None,
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/dashboard/summary")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["total_violations"] == 5
                assert data["last_scan_at"] is not None
                assert data["next_scan_at"] is None  # No scheduled scan
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_summary_fallback_to_monitoring_config(self, mock_db_session, sample_monitoring_config):
        """Test getting next scan time from monitoring config when scheduler unavailable."""
        # Mock total count query
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 0
        
        # Mock status count query
        mock_status_result = MagicMock()
        mock_status_result.__iter__ = lambda self: iter([])
        
        # Mock severity count query
        mock_severity_result = MagicMock()
        mock_severity_result.__iter__ = lambda self: iter([])
        
        # Mock last scan query
        mock_scan_result = MagicMock()
        mock_scan_result.scalar_one_or_none.return_value = None
        
        # Mock monitoring config query (enabled with next_run_at)
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = sample_monitoring_config
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_severity_result,
            mock_scan_result,
            mock_config_result,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        # Mock the scheduler to raise an exception (simulating unavailability)
        with patch('app.routers.dashboard.get_monitoring_scheduler') as mock_scheduler:
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = MagicMock(
                is_enabled=False,
                next_run_time=None,
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/dashboard/summary")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                # Should fall back to monitoring config's next_run_at
                assert data["next_scan_at"] is not None
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_summary_partial_status_counts(self, mock_db_session):
        """Test getting summary when only some statuses have violations."""
        # Mock total count query
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 5
        
        # Mock status count query - only pending and confirmed
        mock_status_result = MagicMock()
        status_rows = [
            MagicMock(status=ViolationStatus.PENDING.value, count=3),
            MagicMock(status=ViolationStatus.CONFIRMED.value, count=2),
        ]
        mock_status_result.__iter__ = lambda self: iter(status_rows)
        
        # Mock severity count query - only high
        mock_severity_result = MagicMock()
        severity_rows = [
            MagicMock(severity=Severity.HIGH.value, count=5),
        ]
        mock_severity_result.__iter__ = lambda self: iter(severity_rows)
        
        # Mock last scan query
        mock_scan_result = MagicMock()
        mock_scan_result.scalar_one_or_none.return_value = None
        
        # Mock monitoring config query
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_severity_result,
            mock_scan_result,
            mock_config_result,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with patch('app.routers.dashboard.get_monitoring_scheduler') as mock_scheduler:
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = MagicMock(
                is_enabled=False,
                next_run_time=None,
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/dashboard/summary")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                # Check that missing statuses default to 0 (flat fields)
                assert data["pending_count"] == 3
                assert data["confirmed_count"] == 2
                assert data["false_positive_count"] == 0
                assert data["resolved_count"] == 0
                
                # Check that missing severities default to 0
                assert data["by_severity"]["low"] == 0
                assert data["by_severity"]["medium"] == 0
                assert data["by_severity"]["high"] == 5
                assert data["by_severity"]["critical"] == 0
            finally:
                app.dependency_overrides.clear()


class TestPydanticModels:
    """Tests for Pydantic models."""

    def test_violations_by_status_model(self):
        """Test ViolationsByStatus model creation."""
        by_status = ViolationsByStatus(
            pending=5,
            confirmed=3,
            false_positive=1,
            resolved=10,
        )
        
        assert by_status.pending == 5
        assert by_status.confirmed == 3
        assert by_status.false_positive == 1
        assert by_status.resolved == 10

    def test_violations_by_status_defaults(self):
        """Test ViolationsByStatus model with defaults."""
        by_status = ViolationsByStatus()
        
        assert by_status.pending == 0
        assert by_status.confirmed == 0
        assert by_status.false_positive == 0
        assert by_status.resolved == 0

    def test_violations_by_severity_model(self):
        """Test ViolationsBySeverity model creation."""
        by_severity = ViolationsBySeverity(
            low=2,
            medium=5,
            high=8,
            critical=3,
        )
        
        assert by_severity.low == 2
        assert by_severity.medium == 5
        assert by_severity.high == 8
        assert by_severity.critical == 3

    def test_violations_by_severity_defaults(self):
        """Test ViolationsBySeverity model with defaults."""
        by_severity = ViolationsBySeverity()
        
        assert by_severity.low == 0
        assert by_severity.medium == 0
        assert by_severity.high == 0
        assert by_severity.critical == 0

    def test_dashboard_summary_response_model(self):
        """Test DashboardSummaryResponse model creation."""
        now = datetime.now(timezone.utc)
        
        response = DashboardSummaryResponse(
            total_violations=20,
            pending_count=5,
            confirmed_count=3,
            false_positive_count=2,
            resolved_count=10,
            by_severity={"low": 2, "medium": 8, "high": 7, "critical": 3},
            last_scan_at=now - timedelta(hours=1),
            next_scan_at=now + timedelta(hours=1),
        )
        
        assert response.total_violations == 20
        assert response.pending_count == 5
        assert response.by_severity["critical"] == 3
        assert response.last_scan_at is not None
        assert response.next_scan_at is not None

    def test_dashboard_summary_response_defaults(self):
        """Test DashboardSummaryResponse model with defaults."""
        response = DashboardSummaryResponse()
        
        assert response.total_violations == 0
        assert response.pending_count == 0
        assert response.confirmed_count == 0
        assert response.by_severity == {}
        assert response.last_scan_at is None
        assert response.next_scan_at is None

    def test_dashboard_summary_response_partial(self):
        """Test DashboardSummaryResponse model with partial data."""
        response = DashboardSummaryResponse(
            total_violations=5,
            pending_count=5,
        )
        
        assert response.total_violations == 5
        assert response.pending_count == 5
        assert response.confirmed_count == 0
        assert response.by_severity == {}
        assert response.last_scan_at is None


# =============================================================================
# Tests for Trends API Endpoint
# =============================================================================

from app.routers.dashboard import (
    TimeRange,
    TrendBucket,
    TrendIndicator,
    TrendDataPoint,
    TrendSummary,
    TrendsResponse,
    _get_days_from_time_range,
)


class TestTrendsPydanticModels:
    """Tests for Trends-related Pydantic models."""

    def test_trend_data_point_model(self):
        """Test TrendDataPoint model creation."""
        data_point = TrendDataPoint(
            date="2024-01-15",
            total_violations=10,
            new_violations=5,
            resolved_violations=3,
        )
        
        assert data_point.date == "2024-01-15"
        assert data_point.total_violations == 10
        assert data_point.new_violations == 5
        assert data_point.resolved_violations == 3

    def test_trend_data_point_defaults(self):
        """Test TrendDataPoint model with defaults."""
        data_point = TrendDataPoint(date="2024-01-15")
        
        assert data_point.date == "2024-01-15"
        assert data_point.total_violations == 0
        assert data_point.new_violations == 0
        assert data_point.resolved_violations == 0

    def test_trend_summary_model(self):
        """Test TrendSummary model creation."""
        summary = TrendSummary(
            current_period_total=50,
            previous_period_total=40,
            percentage_change=25.0,
            trend_indicator=TrendIndicator.DEGRADATION,
            total_new_violations=15,
            total_resolved_violations=5,
        )
        
        assert summary.current_period_total == 50
        assert summary.previous_period_total == 40
        assert summary.percentage_change == 25.0
        assert summary.trend_indicator == TrendIndicator.DEGRADATION
        assert summary.total_new_violations == 15
        assert summary.total_resolved_violations == 5

    def test_trend_summary_defaults(self):
        """Test TrendSummary model with defaults."""
        summary = TrendSummary()
        
        assert summary.current_period_total == 0
        assert summary.previous_period_total == 0
        assert summary.percentage_change is None
        assert summary.trend_indicator == TrendIndicator.STABLE
        assert summary.total_new_violations == 0
        assert summary.total_resolved_violations == 0

    def test_trends_response_model(self):
        """Test TrendsResponse model creation."""
        response = TrendsResponse(
            time_range="7d",
            bucket="daily",
            data_points=[
                TrendDataPoint(date="2024-01-15", new_violations=5),
                TrendDataPoint(date="2024-01-16", new_violations=3),
            ],
            summary=TrendSummary(
                current_period_total=8,
                previous_period_total=10,
                percentage_change=-20.0,
                trend_indicator=TrendIndicator.IMPROVEMENT,
            ),
        )
        
        assert response.time_range == "7d"
        assert response.bucket == "daily"
        assert len(response.data_points) == 2
        assert response.summary.percentage_change == -20.0

    def test_trends_response_defaults(self):
        """Test TrendsResponse model with defaults."""
        response = TrendsResponse(
            time_range="7d",
            bucket="daily",
        )
        
        assert response.time_range == "7d"
        assert response.bucket == "daily"
        assert response.data_points == []
        assert response.summary.current_period_total == 0


class TestTimeRangeHelpers:
    """Tests for time range helper functions."""

    def test_get_days_from_time_range_7d(self):
        """Test 7 days time range."""
        assert _get_days_from_time_range(TimeRange.LAST_7_DAYS) == 7

    def test_get_days_from_time_range_14d(self):
        """Test 14 days time range."""
        assert _get_days_from_time_range(TimeRange.LAST_14_DAYS) == 14

    def test_get_days_from_time_range_30d(self):
        """Test 30 days time range."""
        assert _get_days_from_time_range(TimeRange.LAST_30_DAYS) == 30

    def test_get_days_from_time_range_90d(self):
        """Test 90 days time range."""
        assert _get_days_from_time_range(TimeRange.LAST_90_DAYS) == 90


class TestTrendIndicatorEnum:
    """Tests for TrendIndicator enum."""

    def test_trend_indicator_values(self):
        """Test TrendIndicator enum values."""
        assert TrendIndicator.IMPROVEMENT.value == "improvement"
        assert TrendIndicator.DEGRADATION.value == "degradation"
        assert TrendIndicator.STABLE.value == "stable"


class TestGetDashboardTrends:
    """Tests for GET /api/dashboard/trends endpoint."""

    @pytest.mark.asyncio
    async def test_get_trends_empty_database(self, mock_db_session):
        """Test getting trends when no violations exist."""
        # Mock queries for data points (empty results)
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        # Mock queries for summary (all zeros)
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 0
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 0
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 0
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 0
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["time_range"] == "7d"
            assert data["bucket"] == "daily"
            assert isinstance(data["data_points"], list)
            assert data["summary"]["current_period_total"] == 0
            assert data["summary"]["previous_period_total"] == 0
            assert data["summary"]["trend_indicator"] == "stable"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_with_time_range_parameter(self, mock_db_session):
        """Test getting trends with custom time range."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 0
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 0
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 0
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 0
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends?time_range=30d")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["time_range"] == "30d"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_with_weekly_bucket(self, mock_db_session):
        """Test getting trends with weekly bucket."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 0
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 0
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 0
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 0
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends?bucket=weekly")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["bucket"] == "weekly"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_improvement_indicator(self, mock_db_session):
        """Test trends showing improvement (fewer violations than previous period)."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        # Current period: 5 violations, Previous period: 10 violations = -50% (improvement)
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 5
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 10
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 5
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 8
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["summary"]["current_period_total"] == 5
            assert data["summary"]["previous_period_total"] == 10
            assert data["summary"]["percentage_change"] == -50.0
            assert data["summary"]["trend_indicator"] == "improvement"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_degradation_indicator(self, mock_db_session):
        """Test trends showing degradation (more violations than previous period)."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        # Current period: 15 violations, Previous period: 10 violations = +50% (degradation)
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 15
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 10
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 15
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 2
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["summary"]["current_period_total"] == 15
            assert data["summary"]["previous_period_total"] == 10
            assert data["summary"]["percentage_change"] == 50.0
            assert data["summary"]["trend_indicator"] == "degradation"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_stable_indicator(self, mock_db_session):
        """Test trends showing stable (similar violations to previous period)."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        # Current period: 10 violations, Previous period: 10 violations = 0% (stable)
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 10
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 10
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 10
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 10
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["summary"]["current_period_total"] == 10
            assert data["summary"]["previous_period_total"] == 10
            assert data["summary"]["percentage_change"] == 0.0
            assert data["summary"]["trend_indicator"] == "stable"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_no_previous_period_data(self, mock_db_session):
        """Test trends when previous period has no violations."""
        # Mock queries
        mock_new_violations_result = MagicMock()
        mock_new_violations_result.__iter__ = lambda self: iter([])
        
        mock_resolved_violations_result = MagicMock()
        mock_resolved_violations_result.__iter__ = lambda self: iter([])
        
        # Current period: 5 violations, Previous period: 0 violations
        mock_current_count = MagicMock()
        mock_current_count.scalar.return_value = 5
        
        mock_previous_count = MagicMock()
        mock_previous_count.scalar.return_value = 0
        
        mock_new_count = MagicMock()
        mock_new_count.scalar.return_value = 5
        
        mock_resolved_count = MagicMock()
        mock_resolved_count.scalar.return_value = 0
        
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_new_violations_result,
            mock_resolved_violations_result,
            mock_current_count,
            mock_previous_count,
            mock_new_count,
            mock_resolved_count,
        ])
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["summary"]["current_period_total"] == 5
            assert data["summary"]["previous_period_total"] == 0
            # percentage_change should be None when previous is 0
            assert data["summary"]["percentage_change"] is None
            # Should show degradation since we went from 0 to 5
            assert data["summary"]["trend_indicator"] == "degradation"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_invalid_time_range(self, mock_db_session):
        """Test getting trends with invalid time range parameter."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends?time_range=invalid")
            
            # FastAPI should return 422 for invalid enum value
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_trends_invalid_bucket(self, mock_db_session):
        """Test getting trends with invalid bucket parameter."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/dashboard/trends?bucket=invalid")
            
            # FastAPI should return 422 for invalid enum value
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

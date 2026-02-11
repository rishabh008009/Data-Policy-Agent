"""Unit tests for the Monitoring Scheduler Service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.scheduler import (
    MonitoringScheduler,
    SchedulerStatus,
    ScanResult,
    SchedulerConfigError,
    get_monitoring_scheduler,
    reset_monitoring_scheduler,
    SCAN_JOB_ID,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
)
from app.models.enums import ScanStatus


class TestSchedulerStatus:
    """Tests for the SchedulerStatus Pydantic model."""

    def test_default_values(self):
        """Test creating status with default values."""
        status = SchedulerStatus()
        
        assert status.is_running is False
        assert status.is_enabled is False
        assert status.next_run_time is None
        assert status.last_run_time is None
        assert status.interval_minutes is None

    def test_custom_values(self):
        """Test creating status with custom values."""
        now = datetime.now(timezone.utc)
        status = SchedulerStatus(
            is_running=True,
            is_enabled=True,
            next_run_time=now,
            last_run_time=now - timedelta(hours=1),
            interval_minutes=60,
        )
        
        assert status.is_running is True
        assert status.is_enabled is True
        assert status.next_run_time == now
        assert status.interval_minutes == 60


class TestScanResult:
    """Tests for the ScanResult Pydantic model."""

    def test_successful_scan_result(self):
        """Test creating a successful scan result."""
        scan_id = uuid4()
        started = datetime.now(timezone.utc)
        completed = started + timedelta(minutes=5)
        
        result = ScanResult(
            scan_id=scan_id,
            started_at=started,
            completed_at=completed,
            total_violations=10,
            new_violations=3,
            status=ScanStatus.COMPLETED.value,
        )
        
        assert result.scan_id == scan_id
        assert result.total_violations == 10
        assert result.new_violations == 3
        assert result.status == "completed"
        assert result.error_message is None

    def test_failed_scan_result(self):
        """Test creating a failed scan result."""
        scan_id = uuid4()
        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=30)
        
        result = ScanResult(
            scan_id=scan_id,
            started_at=started,
            completed_at=completed,
            status=ScanStatus.FAILED.value,
            error_message="Connection failed",
        )
        
        assert result.status == "failed"
        assert result.error_message == "Connection failed"
        assert result.total_violations == 0
        assert result.new_violations == 0


class TestMonitoringScheduler:
    """Tests for the MonitoringScheduler class."""

    @pytest.fixture
    def scheduler(self):
        """Create a MonitoringScheduler instance for testing."""
        scheduler = MonitoringScheduler()
        yield scheduler
        # Cleanup - use try/except to handle event loop issues
        try:
            if scheduler._is_started:
                scheduler.shutdown()
        except Exception:
            pass

    def test_initial_state(self, scheduler):
        """Test that scheduler starts in correct initial state."""
        assert scheduler._is_started is False
        assert scheduler._retry_count == 0
        assert scheduler._max_retries == 3

    @pytest.mark.asyncio
    async def test_start(self, scheduler):
        """Test starting the scheduler."""
        scheduler.start()
        
        assert scheduler._is_started is True

    @pytest.mark.asyncio
    async def test_start_idempotent(self, scheduler):
        """Test that starting multiple times is safe."""
        scheduler.start()
        scheduler.start()  # Should not raise
        
        assert scheduler._is_started is True

    @pytest.mark.asyncio
    async def test_shutdown(self, scheduler):
        """Test shutting down the scheduler."""
        scheduler.start()
        scheduler.shutdown()
        
        assert scheduler._is_started is False

    def test_shutdown_when_not_started(self, scheduler):
        """Test that shutdown when not started is safe."""
        scheduler.shutdown()  # Should not raise
        
        assert scheduler._is_started is False

    def test_get_status_not_started(self, scheduler):
        """Test get_status when scheduler is not started."""
        status = scheduler.get_status()
        
        assert status.is_running is False
        assert status.is_enabled is False
        assert status.next_run_time is None
        assert status.interval_minutes is None

    @pytest.mark.asyncio
    async def test_get_status_started_no_job(self, scheduler):
        """Test get_status when scheduler is started but no job scheduled."""
        scheduler.start()
        status = scheduler.get_status()
        
        # When started, the scheduler is running
        assert status.is_running is True
        assert status.is_enabled is False
        assert status.next_run_time is None

    @pytest.mark.asyncio
    async def test_schedule_scan_valid_interval(self):
        """Test scheduling a scan with valid interval."""
        scheduler = MonitoringScheduler()
        try:
            with patch.object(scheduler, '_save_config', new_callable=AsyncMock):
                result = await scheduler.schedule_scan(60)
            
            assert "60 minutes" in result
            assert scheduler._is_started is True
            
            # Verify job was added
            job = scheduler._scheduler.get_job(SCAN_JOB_ID)
            assert job is not None
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_scan_starts_scheduler(self):
        """Test that schedule_scan starts the scheduler if not started."""
        scheduler = MonitoringScheduler()
        try:
            assert scheduler._is_started is False
            
            with patch.object(scheduler, '_save_config', new_callable=AsyncMock):
                await scheduler.schedule_scan(120)
            
            assert scheduler._is_started is True
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_scan_replaces_existing(self):
        """Test that scheduling replaces existing schedule."""
        scheduler = MonitoringScheduler()
        try:
            with patch.object(scheduler, '_save_config', new_callable=AsyncMock):
                await scheduler.schedule_scan(60)
                await scheduler.schedule_scan(120)
            
            # Should only have one job
            job = scheduler._scheduler.get_job(SCAN_JOB_ID)
            assert job is not None
            
            # Verify interval was updated
            total_seconds = job.trigger.interval.total_seconds()
            assert total_seconds == 120 * 60
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_scan_interval_too_low(self, scheduler):
        """Test that interval below minimum raises error."""
        with pytest.raises(SchedulerConfigError) as exc_info:
            await scheduler.schedule_scan(30)  # Below 60 minutes
        
        assert "between" in str(exc_info.value)
        assert str(MIN_INTERVAL_MINUTES) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_schedule_scan_interval_too_high(self, scheduler):
        """Test that interval above maximum raises error."""
        with pytest.raises(SchedulerConfigError) as exc_info:
            await scheduler.schedule_scan(2000)  # Above 1440 minutes
        
        assert "between" in str(exc_info.value)
        assert str(MAX_INTERVAL_MINUTES) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_schedule_scan_boundary_min(self):
        """Test scheduling at minimum boundary (60 minutes)."""
        scheduler = MonitoringScheduler()
        try:
            with patch.object(scheduler, '_save_config', new_callable=AsyncMock):
                result = await scheduler.schedule_scan(60)
            
            assert "60 minutes" in result
            job = scheduler._scheduler.get_job(SCAN_JOB_ID)
            assert job is not None
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_scan_boundary_max(self):
        """Test scheduling at maximum boundary (1440 minutes)."""
        scheduler = MonitoringScheduler()
        try:
            with patch.object(scheduler, '_save_config', new_callable=AsyncMock):
                result = await scheduler.schedule_scan(1440)
            
            assert "1440 minutes" in result
            job = scheduler._scheduler.get_job(SCAN_JOB_ID)
            assert job is not None
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_schedule_with_job(self):
        """Test cancelling an existing schedule."""
        scheduler = MonitoringScheduler()
        try:
            scheduler.start()
            
            # Add a job manually
            scheduler._scheduler.add_job(
                lambda: None,
                trigger='interval',
                minutes=60,
                id=SCAN_JOB_ID,
            )
            
            with patch.object(scheduler, '_disable_config', new_callable=AsyncMock):
                result = scheduler.cancel_schedule()
            
            assert result is True
            assert scheduler._scheduler.get_job(SCAN_JOB_ID) is None
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_schedule_no_job(self):
        """Test cancelling when no schedule exists."""
        scheduler = MonitoringScheduler()
        try:
            scheduler.start()
            
            result = scheduler.cancel_schedule()
            
            assert result is False
        finally:
            scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_get_status_with_job(self):
        """Test get_status when a job is scheduled."""
        scheduler = MonitoringScheduler()
        try:
            scheduler.start()
            
            # Add a job manually
            scheduler._scheduler.add_job(
                lambda: None,
                trigger='interval',
                minutes=120,
                id=SCAN_JOB_ID,
            )
            
            status = scheduler.get_status()
            
            assert status.is_running is True
            assert status.is_enabled is True
            assert status.next_run_time is not None
            assert status.interval_minutes == 120
        finally:
            scheduler.shutdown()


class TestRunScheduledScan:
    """Tests for the run_scheduled_scan method."""

    @pytest.fixture
    def scheduler(self):
        """Create a MonitoringScheduler instance for testing."""
        scheduler = MonitoringScheduler()
        yield scheduler
        try:
            if scheduler._is_started:
                scheduler.shutdown()
        except Exception:
            pass

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        conn = MagicMock()
        conn.host = "localhost"
        conn.port = 5432
        conn.database_name = "testdb"
        conn.username = "user"
        conn.encrypted_password = "pass"
        conn.is_active = True
        return conn

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule."""
        rule = MagicMock()
        rule.id = uuid4()
        rule.rule_code = "DATA-001"
        rule.is_active = True
        return rule

    @pytest.mark.asyncio
    async def test_run_scan_no_db_connection(self, scheduler):
        """Test scan fails when no database connection is configured."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock no active database connection
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Patch ScanHistory to return our mock
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.FAILED.value
        assert "No active database connection" in result.error_message

    @pytest.mark.asyncio
    async def test_run_scan_no_rules(self, scheduler, mock_db_connection):
        """Test scan completes with zero violations when no rules exist."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # First call returns db connection, second returns empty rules
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = []
        
        mock_session.execute = AsyncMock(side_effect=[db_result, rules_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.COMPLETED.value
        assert result.total_violations == 0
        assert result.new_violations == 0

    @pytest.mark.asyncio
    async def test_run_scan_success(self, scheduler, mock_db_connection, mock_rule):
        """Test successful scan execution."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations (empty)
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([])
        
        # Mock monitoring config with proper values
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.interval_minutes = 60
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result, config_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Mock the scanner
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock()
        mock_scanner.disconnect = AsyncMock()
        mock_scanner.scan_for_violations = AsyncMock(return_value=[])
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.COMPLETED.value
        assert result.total_violations == 0
        mock_scanner.connect.assert_called_once()
        mock_scanner.scan_for_violations.assert_called_once()
        mock_scanner.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scan_with_violations(self, scheduler, mock_db_connection, mock_rule):
        """Test scan that finds violations."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations (empty)
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([])
        
        # Mock monitoring config with proper values
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.interval_minutes = 60
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result, config_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Create mock violations
        mock_violation1 = MagicMock()
        mock_violation1.record_identifier = "record-1"
        mock_violation1.rule_id = mock_rule.id
        
        mock_violation2 = MagicMock()
        mock_violation2.record_identifier = "record-2"
        mock_violation2.rule_id = mock_rule.id
        
        # Mock the scanner
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock()
        mock_scanner.disconnect = AsyncMock()
        mock_scanner.scan_for_violations = AsyncMock(
            return_value=[mock_violation1, mock_violation2]
        )
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.COMPLETED.value
        assert result.total_violations == 2
        assert result.new_violations == 2  # All are new since no existing

    @pytest.mark.asyncio
    async def test_run_scan_detects_new_violations(
        self, scheduler, mock_db_connection, mock_rule
    ):
        """Test that scan correctly identifies new vs existing violations."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations - one already exists
        existing_row = MagicMock()
        existing_row.record_identifier = "record-1"
        existing_row.rule_id = mock_rule.id
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([existing_row])
        
        # Mock monitoring config with proper values
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.interval_minutes = 60
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result, config_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Create mock violations - one existing, one new
        mock_violation1 = MagicMock()
        mock_violation1.record_identifier = "record-1"  # Existing
        mock_violation1.rule_id = mock_rule.id
        
        mock_violation2 = MagicMock()
        mock_violation2.record_identifier = "record-2"  # New
        mock_violation2.rule_id = mock_rule.id
        
        # Mock the scanner
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock()
        mock_scanner.disconnect = AsyncMock()
        mock_scanner.scan_for_violations = AsyncMock(
            return_value=[mock_violation1, mock_violation2]
        )
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.COMPLETED.value
        assert result.total_violations == 2
        assert result.new_violations == 1  # Only record-2 is new

    @pytest.mark.asyncio
    async def test_run_scan_connection_error(self, scheduler, mock_db_connection, mock_rule):
        """Test scan handles connection errors."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([])
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Mock the scanner to raise connection error
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock(side_effect=Exception("Connection refused"))
        mock_scanner.disconnect = AsyncMock()
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.FAILED.value
        assert "Connection refused" in result.error_message

    @pytest.mark.asyncio
    async def test_run_scan_increments_retry_count(
        self, scheduler, mock_db_connection, mock_rule
    ):
        """Test that failed scans increment retry count."""
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([])
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Mock the scanner to fail
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock(side_effect=Exception("Error"))
        mock_scanner.disconnect = AsyncMock()
        
        assert scheduler._retry_count == 0
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert scheduler._retry_count == 1

    @pytest.mark.asyncio
    async def test_run_scan_resets_retry_on_success(
        self, scheduler, mock_db_connection, mock_rule
    ):
        """Test that successful scans reset retry count."""
        scheduler._retry_count = 2  # Simulate previous failures
        
        mock_session = AsyncMock()
        
        # Mock scan history
        mock_scan_history = MagicMock()
        mock_scan_history.id = uuid4()
        
        # Mock database connection result
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = mock_db_connection
        
        # Mock rules result
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]
        
        # Mock existing violations
        violations_result = MagicMock()
        violations_result.__iter__ = lambda self: iter([])
        
        # Mock monitoring config with proper values
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.interval_minutes = 60
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        
        mock_session.execute = AsyncMock(
            side_effect=[db_result, rules_result, violations_result, config_result]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        # Mock successful scanner
        mock_scanner = AsyncMock()
        mock_scanner.connect = AsyncMock()
        mock_scanner.disconnect = AsyncMock()
        mock_scanner.scan_for_violations = AsyncMock(return_value=[])
        
        with patch('app.services.scheduler.ScanHistory', return_value=mock_scan_history):
            with patch(
                'app.services.db_scanner.DatabaseScannerService',
                return_value=mock_scanner
            ):
                result = await scheduler.run_scheduled_scan(db_session=mock_session)
        
        assert result.status == ScanStatus.COMPLETED.value
        assert scheduler._retry_count == 0


class TestGetMonitoringScheduler:
    """Tests for the get_monitoring_scheduler factory function."""

    def teardown_method(self):
        """Reset the global scheduler after each test."""
        reset_monitoring_scheduler()

    def test_returns_scheduler_instance(self):
        """Test that factory returns a MonitoringScheduler instance."""
        scheduler = get_monitoring_scheduler()
        
        assert isinstance(scheduler, MonitoringScheduler)

    def test_returns_same_instance(self):
        """Test that factory returns the same instance on multiple calls."""
        scheduler1 = get_monitoring_scheduler()
        scheduler2 = get_monitoring_scheduler()
        
        assert scheduler1 is scheduler2

    def test_reset_creates_new_instance(self):
        """Test that reset allows creating a new instance."""
        scheduler1 = get_monitoring_scheduler()
        reset_monitoring_scheduler()
        scheduler2 = get_monitoring_scheduler()
        
        assert scheduler1 is not scheduler2


class TestResetMonitoringScheduler:
    """Tests for the reset_monitoring_scheduler function."""

    def test_reset_when_none(self):
        """Test reset when no scheduler exists."""
        reset_monitoring_scheduler()  # Should not raise

    @pytest.mark.asyncio
    async def test_reset_shuts_down_scheduler(self):
        """Test that reset shuts down the scheduler."""
        scheduler = get_monitoring_scheduler()
        scheduler.start()
        
        assert scheduler._is_started is True
        
        reset_monitoring_scheduler()
        
        assert scheduler._is_started is False

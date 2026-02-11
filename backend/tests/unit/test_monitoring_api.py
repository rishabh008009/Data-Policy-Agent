"""Unit tests for the Monitoring API routes."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.routers.monitoring import router, get_scheduler
from app.services.scheduler import (
    MonitoringScheduler,
    SchedulerStatus,
    SchedulerConfigError,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
)


# Create test app
def create_test_app() -> FastAPI:
    """Create a FastAPI app for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


class TestGetStatus:
    """Tests for GET /api/monitoring/status endpoint."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_get_status_not_running(self, client, mock_scheduler):
        """Test getting status when scheduler is not running."""
        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=False,
            is_enabled=False,
            next_run_time=None,
            last_run_time=None,
            interval_minutes=None,
        )

        response = client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["is_enabled"] is False
        assert data["next_run_time"] is None
        assert data["last_run_time"] is None
        assert data["interval_minutes"] is None

    def test_get_status_running_enabled(self, client, mock_scheduler):
        """Test getting status when scheduler is running and enabled."""
        next_run = datetime.now(timezone.utc) + timedelta(hours=1)
        last_run = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=True,
            is_enabled=True,
            next_run_time=next_run,
            last_run_time=last_run,
            interval_minutes=60,
        )

        response = client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["is_enabled"] is True
        assert data["next_run_time"] is not None
        assert data["last_run_time"] is not None
        assert data["interval_minutes"] == 60

    def test_get_status_running_not_enabled(self, client, mock_scheduler):
        """Test getting status when scheduler is running but not enabled."""
        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=True,
            is_enabled=False,
            next_run_time=None,
            last_run_time=None,
            interval_minutes=None,
        )

        response = client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["is_enabled"] is False


class TestConfigureSchedule:
    """Tests for POST /api/monitoring/schedule endpoint."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        scheduler.schedule_scan = AsyncMock()
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_configure_schedule_valid_interval(self, client, mock_scheduler):
        """Test configuring schedule with valid interval."""
        mock_scheduler.schedule_scan.return_value = "Scheduled compliance scans every 60 minutes"
        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=True,
            is_enabled=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(hours=1),
            last_run_time=None,
            interval_minutes=60,
        )

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 60},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["interval_minutes"] == 60
        assert data["is_enabled"] is True
        mock_scheduler.schedule_scan.assert_called_once_with(60)

    def test_configure_schedule_max_interval(self, client, mock_scheduler):
        """Test configuring schedule with maximum interval (daily)."""
        mock_scheduler.schedule_scan.return_value = "Scheduled compliance scans every 1440 minutes"

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 1440},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["interval_minutes"] == 1440
        mock_scheduler.schedule_scan.assert_called_once_with(1440)

    def test_configure_schedule_custom_interval(self, client, mock_scheduler):
        """Test configuring schedule with custom interval."""
        mock_scheduler.schedule_scan.return_value = "Scheduled compliance scans every 120 minutes"

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 120},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["interval_minutes"] == 120

    def test_configure_schedule_interval_too_low(self, client, mock_scheduler):
        """Test configuring schedule with interval below minimum."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 30},
        )

        assert response.status_code == 422  # Validation error
        mock_scheduler.schedule_scan.assert_not_called()

    def test_configure_schedule_interval_too_high(self, client, mock_scheduler):
        """Test configuring schedule with interval above maximum."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 2000},
        )

        assert response.status_code == 422  # Validation error
        mock_scheduler.schedule_scan.assert_not_called()

    def test_configure_schedule_scheduler_error(self, client, mock_scheduler):
        """Test configuring schedule when scheduler raises error."""
        mock_scheduler.schedule_scan.side_effect = SchedulerConfigError(
            "Scan interval must be between 60 and 1440 minutes."
        )
        mock_scheduler.get_status.return_value = SchedulerStatus()

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 60},
        )

        assert response.status_code == 400
        data = response.json()
        assert "between" in data["detail"]

    def test_configure_schedule_missing_interval(self, client, mock_scheduler):
        """Test configuring schedule without interval_minutes."""
        response = client.post(
            "/api/monitoring/schedule",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_configure_schedule_invalid_type(self, client, mock_scheduler):
        """Test configuring schedule with invalid interval type."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": "sixty"},
        )

        assert response.status_code == 422  # Validation error


class TestDisableSchedule:
    """Tests for DELETE /api/monitoring/schedule endpoint."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_disable_schedule_was_enabled(self, client, mock_scheduler):
        """Test disabling schedule when one was active."""
        mock_scheduler.cancel_schedule.return_value = True

        response = client.delete("/api/monitoring/schedule")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Scheduled scans have been disabled"
        assert data["was_enabled"] is True
        mock_scheduler.cancel_schedule.assert_called_once()

    def test_disable_schedule_was_not_enabled(self, client, mock_scheduler):
        """Test disabling schedule when none was active."""
        mock_scheduler.cancel_schedule.return_value = False

        response = client.delete("/api/monitoring/schedule")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No scheduled scans were active"
        assert data["was_enabled"] is False
        mock_scheduler.cancel_schedule.assert_called_once()


class TestAsyncEndpoints:
    """Tests for async behavior of endpoints."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        scheduler.schedule_scan = AsyncMock()
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.mark.asyncio
    async def test_configure_schedule_async(self, app, mock_scheduler):
        """Test that configure_schedule works asynchronously."""
        mock_scheduler.schedule_scan.return_value = "Scheduled compliance scans every 60 minutes"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/monitoring/schedule",
                json={"interval_minutes": 60},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_status_async(self, app, mock_scheduler):
        """Test that get_status works asynchronously."""
        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=True,
            is_enabled=True,
            interval_minutes=60,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True


class TestResponseModels:
    """Tests for response model validation."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        scheduler.schedule_scan = AsyncMock()
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_status_response_has_all_fields(self, client, mock_scheduler):
        """Test that status response includes all expected fields."""
        mock_scheduler.get_status.return_value = SchedulerStatus()

        response = client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields are present
        expected_fields = [
            "is_running",
            "is_enabled",
            "next_run_time",
            "last_run_time",
            "interval_minutes",
        ]
        for field in expected_fields:
            assert field in data

    def test_schedule_config_response_has_all_fields(self, client, mock_scheduler):
        """Test that schedule config response includes all expected fields."""
        mock_scheduler.schedule_scan.return_value = "Scheduled"
        mock_scheduler.get_status.return_value = SchedulerStatus(
            is_running=True,
            is_enabled=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(hours=1),
            last_run_time=None,
            interval_minutes=60,
        )

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 60},
        )

        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields are present
        expected_fields = ["id", "interval_minutes", "is_enabled", "next_run_at", "last_run_at"]
        for field in expected_fields:
            assert field in data

    def test_disable_response_has_all_fields(self, client, mock_scheduler):
        """Test that disable response includes all expected fields."""
        mock_scheduler.cancel_schedule.return_value = True

        response = client.delete("/api/monitoring/schedule")

        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields are present
        expected_fields = ["message", "was_enabled"]
        for field in expected_fields:
            assert field in data


class TestBoundaryValues:
    """Tests for boundary value handling."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler."""
        scheduler = MagicMock(spec=MonitoringScheduler)
        scheduler.schedule_scan = AsyncMock()
        return scheduler

    @pytest.fixture
    def app(self, mock_scheduler):
        """Create test app with mocked scheduler."""
        app = create_test_app()
        app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_minimum_interval_boundary(self, client, mock_scheduler):
        """Test minimum interval boundary (60 minutes)."""
        mock_scheduler.schedule_scan.return_value = "Scheduled"

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": MIN_INTERVAL_MINUTES},
        )

        assert response.status_code == 200
        mock_scheduler.schedule_scan.assert_called_once_with(MIN_INTERVAL_MINUTES)

    def test_maximum_interval_boundary(self, client, mock_scheduler):
        """Test maximum interval boundary (1440 minutes)."""
        mock_scheduler.schedule_scan.return_value = "Scheduled"

        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": MAX_INTERVAL_MINUTES},
        )

        assert response.status_code == 200
        mock_scheduler.schedule_scan.assert_called_once_with(MAX_INTERVAL_MINUTES)

    def test_below_minimum_boundary(self, client, mock_scheduler):
        """Test just below minimum interval boundary."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": MIN_INTERVAL_MINUTES - 1},
        )

        assert response.status_code == 422
        mock_scheduler.schedule_scan.assert_not_called()

    def test_above_maximum_boundary(self, client, mock_scheduler):
        """Test just above maximum interval boundary."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": MAX_INTERVAL_MINUTES + 1},
        )

        assert response.status_code == 422
        mock_scheduler.schedule_scan.assert_not_called()

    def test_zero_interval(self, client, mock_scheduler):
        """Test zero interval is rejected."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": 0},
        )

        assert response.status_code == 422
        mock_scheduler.schedule_scan.assert_not_called()

    def test_negative_interval(self, client, mock_scheduler):
        """Test negative interval is rejected."""
        response = client.post(
            "/api/monitoring/schedule",
            json={"interval_minutes": -60},
        )

        assert response.status_code == 422
        mock_scheduler.schedule_scan.assert_not_called()

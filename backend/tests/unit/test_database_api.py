"""Unit tests for the Database API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.database_connection import DatabaseConnection
from app.routers.database import (
    ColumnInfoResponse,
    DatabaseConnectRequest,
    DatabaseConnectResponse,
    DatabaseSchemaResponse,
    TableInfoResponse,
    get_scanner_service,
)
from app.services.db_scanner import (
    AuthenticationError,
    ColumnInfo,
    ConnectionTimeoutError,
    DatabaseConnectionError,
    DatabaseNotFoundError,
    DatabaseSchema,
    DatabaseScannerService,
    HostUnreachableError,
    SSLError,
    TableInfo,
)


# Test fixtures

@pytest.fixture
def sample_connection():
    """Create a sample database connection for testing."""
    connection = DatabaseConnection(
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password="test_password",
        is_active=True,
    )
    connection.id = uuid.uuid4()
    connection.created_at = datetime.now(timezone.utc)
    return connection


@pytest.fixture
def sample_schema():
    """Create a sample database schema for testing."""
    return DatabaseSchema(
        database_name="test_db",
        tables=[
            TableInfo(
                name="users",
                schema_name="public",
                columns=[
                    ColumnInfo(
                        name="id",
                        data_type="uuid",
                        is_nullable=False,
                        is_primary_key=True,
                        default_value="gen_random_uuid()",
                    ),
                    ColumnInfo(
                        name="email",
                        data_type="character varying",
                        is_nullable=False,
                        is_primary_key=False,
                        default_value=None,
                    ),
                    ColumnInfo(
                        name="created_at",
                        data_type="timestamp with time zone",
                        is_nullable=False,
                        is_primary_key=False,
                        default_value="now()",
                    ),
                ],
                row_count=100,
            ),
            TableInfo(
                name="orders",
                schema_name="public",
                columns=[
                    ColumnInfo(
                        name="id",
                        data_type="uuid",
                        is_nullable=False,
                        is_primary_key=True,
                        default_value=None,
                    ),
                    ColumnInfo(
                        name="user_id",
                        data_type="uuid",
                        is_nullable=False,
                        is_primary_key=False,
                        default_value=None,
                    ),
                    ColumnInfo(
                        name="total",
                        data_type="numeric",
                        is_nullable=True,
                        is_primary_key=False,
                        default_value=None,
                    ),
                ],
                row_count=500,
            ),
        ],
        version="PostgreSQL 15.2",
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_scanner_service():
    """Create a mock database scanner service."""
    scanner = MagicMock(spec=DatabaseScannerService)
    scanner.is_connected = False
    scanner.connect = AsyncMock(return_value=True)
    scanner.get_schema = AsyncMock()
    return scanner


class TestConnectDatabase:
    """Tests for POST /api/database/connect endpoint."""

    @pytest.mark.asyncio
    async def test_connect_database_success(
        self, mock_db_session, mock_scanner_service, sample_connection
    ):
        """Test successful database connection."""
        mock_scanner_service.connect = AsyncMock(return_value=True)
        
        # Mock the database query for existing connections
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        
        # Mock refresh to set the ID and created_at
        async def mock_refresh(obj):
            obj.id = sample_connection.id
            obj.created_at = sample_connection.created_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["host"] == "localhost"
            assert data["port"] == 5432
            assert data["database_name"] == "test_db"
            assert data["username"] == "test_user"
            assert data["is_active"] is True
            assert "Successfully connected" in data["message"]
            
            # Verify scanner.connect was called
            mock_scanner_service.connect.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_deactivates_existing(
        self, mock_db_session, mock_scanner_service, sample_connection
    ):
        """Test that connecting deactivates existing active connections."""
        mock_scanner_service.connect = AsyncMock(return_value=True)
        
        # Create an existing active connection
        existing_connection = DatabaseConnection(
            host="old_host",
            port=5432,
            database_name="old_db",
            username="old_user",
            encrypted_password="old_password",
            is_active=True,
        )
        existing_connection.id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_connection]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        
        async def mock_refresh(obj):
            obj.id = sample_connection.id
            obj.created_at = sample_connection.created_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_201_CREATED
            # Verify existing connection was deactivated
            assert existing_connection.is_active is False
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_authentication_error(
        self, mock_db_session, mock_scanner_service
    ):
        """Test connection with invalid credentials."""
        mock_scanner_service.connect = AsyncMock(side_effect=AuthenticationError())
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "username": "wrong_user",
                        "password": "wrong_password",
                    }
                )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Authentication failed" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_not_found(
        self, mock_db_session, mock_scanner_service
    ):
        """Test connection to non-existent database."""
        mock_scanner_service.connect = AsyncMock(
            side_effect=DatabaseNotFoundError("nonexistent_db")
        )
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 5432,
                        "database": "nonexistent_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_timeout(
        self, mock_db_session, mock_scanner_service
    ):
        """Test connection timeout."""
        mock_scanner_service.connect = AsyncMock(side_effect=ConnectionTimeoutError())
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "slow_host",
                        "port": 5432,
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_408_REQUEST_TIMEOUT
            assert "timed out" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_host_unreachable(
        self, mock_db_session, mock_scanner_service
    ):
        """Test connection to unreachable host."""
        mock_scanner_service.connect = AsyncMock(side_effect=HostUnreachableError())
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "unreachable_host",
                        "port": 5432,
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Unable to connect" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_ssl_error(
        self, mock_db_session, mock_scanner_service
    ):
        """Test SSL connection error."""
        mock_scanner_service.connect = AsyncMock(side_effect=SSLError())
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                        "ssl": True,
                    }
                )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "SSL" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_connect_database_invalid_port(self, mock_db_session):
        """Test connection with invalid port number."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Port out of range
                response = await client.post(
                    "/api/database/connect",
                    json={
                        "host": "localhost",
                        "port": 70000,  # Invalid port
                        "database": "test_db",
                        "username": "test_user",
                        "password": "test_password",
                    }
                )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()


class TestGetDatabaseSchema:
    """Tests for GET /api/database/schema endpoint."""

    @pytest.mark.asyncio
    async def test_get_schema_success(self, mock_scanner_service, sample_schema):
        """Test successful schema retrieval."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.get_schema = AsyncMock(return_value=sample_schema)
        
        def override_get_scanner():
            return mock_scanner_service
        
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/database/schema")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["database_name"] == "test_db"
            assert data["version"] == "PostgreSQL 15.2"
            assert len(data["tables"]) == 2
            
            # Check first table
            users_table = data["tables"][0]
            assert users_table["name"] == "users"
            assert users_table["schema_name"] == "public"
            assert users_table["row_count"] == 100
            assert len(users_table["columns"]) == 3
            
            # Check column details
            id_column = users_table["columns"][0]
            assert id_column["name"] == "id"
            assert id_column["data_type"] == "uuid"
            assert id_column["is_nullable"] is False
            assert id_column["is_primary_key"] is True
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_schema_not_connected(self, mock_scanner_service):
        """Test schema retrieval when not connected."""
        mock_scanner_service.is_connected = False
        
        def override_get_scanner():
            return mock_scanner_service
        
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/database/schema")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Not connected" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_schema_connection_error(self, mock_scanner_service):
        """Test schema retrieval with connection error."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.get_schema = AsyncMock(
            side_effect=DatabaseConnectionError("Connection lost")
        )
        
        def override_get_scanner():
            return mock_scanner_service
        
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/database/schema")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Connection lost" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_schema_empty_database(self, mock_scanner_service):
        """Test schema retrieval for database with no tables."""
        empty_schema = DatabaseSchema(
            database_name="empty_db",
            tables=[],
            version="PostgreSQL 15.2",
        )
        mock_scanner_service.is_connected = True
        mock_scanner_service.get_schema = AsyncMock(return_value=empty_schema)
        
        def override_get_scanner():
            return mock_scanner_service
        
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/database/schema")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["database_name"] == "empty_db"
            assert data["tables"] == []
        finally:
            app.dependency_overrides.clear()


class TestPydanticModels:
    """Tests for Pydantic models."""

    def test_database_connect_request_model(self):
        """Test DatabaseConnectRequest model creation."""
        request = DatabaseConnectRequest(
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user",
            password="test_password",
            ssl=False,
        )
        
        assert request.host == "localhost"
        assert request.port == 5432
        assert request.database == "test_db"
        assert request.username == "test_user"
        assert request.password == "test_password"
        assert request.ssl is False

    def test_database_connect_request_default_port(self):
        """Test DatabaseConnectRequest with default port."""
        request = DatabaseConnectRequest(
            host="localhost",
            database="test_db",
            username="test_user",
            password="test_password",
        )
        
        assert request.port == 5432
        assert request.ssl is False

    def test_column_info_response_model(self):
        """Test ColumnInfoResponse model creation."""
        response = ColumnInfoResponse(
            name="id",
            data_type="uuid",
            is_nullable=False,
            is_primary_key=True,
            default_value="gen_random_uuid()",
        )
        
        assert response.name == "id"
        assert response.data_type == "uuid"
        assert response.is_nullable is False
        assert response.is_primary_key is True
        assert response.default_value == "gen_random_uuid()"

    def test_table_info_response_model(self):
        """Test TableInfoResponse model creation."""
        columns = [
            ColumnInfoResponse(
                name="id",
                data_type="uuid",
                is_nullable=False,
                is_primary_key=True,
            ),
        ]
        
        response = TableInfoResponse(
            name="users",
            schema_name="public",
            columns=columns,
            row_count=100,
        )
        
        assert response.name == "users"
        assert response.schema_name == "public"
        assert len(response.columns) == 1
        assert response.row_count == 100

    def test_database_schema_response_model(self):
        """Test DatabaseSchemaResponse model creation."""
        tables = [
            TableInfoResponse(
                name="users",
                schema_name="public",
                columns=[],
                row_count=100,
            ),
        ]
        
        response = DatabaseSchemaResponse(
            database_name="test_db",
            tables=tables,
            version="PostgreSQL 15.2",
        )
        
        assert response.database_name == "test_db"
        assert len(response.tables) == 1
        assert response.version == "PostgreSQL 15.2"

    def test_database_connect_response_model(self, sample_connection):
        """Test DatabaseConnectResponse model creation."""
        response = DatabaseConnectResponse(
            id=sample_connection.id,
            host=sample_connection.host,
            port=sample_connection.port,
            database_name=sample_connection.database_name,
            username=sample_connection.username,
            is_active=sample_connection.is_active,
            created_at=sample_connection.created_at,
            message="Successfully connected",
        )
        
        assert response.host == "localhost"
        assert response.port == 5432
        assert response.database_name == "test_db"
        assert response.is_active is True
        assert "Successfully connected" in response.message


from app.models.compliance_rule import ComplianceRule
from app.models.scan_history import ScanHistory
from app.models.violation import Violation
from app.models.enums import ScanStatus, Severity, ViolationStatus
from app.routers.database import ScanRequest, ScanResponse, ViolationCountBySeverity


@pytest.fixture
def sample_rules():
    """Create sample compliance rules for testing."""
    rules = []
    for i, severity in enumerate([Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]):
        rule = ComplianceRule(
            policy_id=uuid.uuid4(),
            rule_code=f"RULE-{i+1:03d}",
            description=f"Test rule {i+1}",
            evaluation_criteria=f"Check condition {i+1}",
            target_table="test_table",
            severity=severity.value,
            is_active=True,
        )
        rule.id = uuid.uuid4()
        rules.append(rule)
    return rules


@pytest.fixture
def sample_violations(sample_rules):
    """Create sample violations for testing."""
    violations = []
    for rule in sample_rules:
        violation = Violation(
            rule_id=rule.id,
            record_identifier=f"record-{rule.rule_code}",
            record_data={"field": "value"},
            justification=f"Violation of {rule.rule_code}",
            remediation_suggestion="Fix the issue",
            severity=rule.severity,
            status=ViolationStatus.PENDING.value,
        )
        violation.id = uuid.uuid4()
        violations.append(violation)
    return violations


class TestTriggerScan:
    """Tests for POST /api/database/scan endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_scan_success(
        self, mock_db_session, mock_scanner_service, sample_rules, sample_violations
    ):
        """Test successful compliance scan."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.scan_for_violations = AsyncMock(return_value=sample_violations)
        
        # Mock database queries
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = sample_rules
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to set scan history fields
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["scan_id"] == str(scan_history_id)
            assert data["status"] == ScanStatus.COMPLETED.value
            assert data["total_violations"] == 4
            assert data["new_violations"] == 4
            assert data["rules_evaluated"] == 4
            
            # Check violations by severity
            assert data["violations_by_severity"]["low"] == 1
            assert data["violations_by_severity"]["medium"] == 1
            assert data["violations_by_severity"]["high"] == 1
            assert data["violations_by_severity"]["critical"] == 1
            
            # Verify scan_for_violations was called
            mock_scanner_service.scan_for_violations.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_not_connected(self, mock_db_session, mock_scanner_service):
        """Test scan when not connected to database."""
        mock_scanner_service.is_connected = False
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Not connected" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_no_active_rules(self, mock_db_session, mock_scanner_service):
        """Test scan when no active rules exist."""
        mock_scanner_service.is_connected = True
        
        # Mock database queries - return empty rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["status"] == ScanStatus.COMPLETED.value
            assert data["total_violations"] == 0
            assert data["rules_evaluated"] == 0
            assert "No active compliance rules" in data["message"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_no_violations_found(
        self, mock_db_session, mock_scanner_service, sample_rules
    ):
        """Test scan when no violations are found."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.scan_for_violations = AsyncMock(return_value=[])
        
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = sample_rules
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["status"] == ScanStatus.COMPLETED.value
            assert data["total_violations"] == 0
            assert data["rules_evaluated"] == 4
            assert "No violations found" in data["message"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_with_specific_rules(
        self, mock_db_session, mock_scanner_service, sample_rules, sample_violations
    ):
        """Test scan with specific rule IDs."""
        mock_scanner_service.is_connected = True
        # Return only first 2 violations
        mock_scanner_service.scan_for_violations = AsyncMock(return_value=sample_violations[:2])
        
        # Return only first 2 rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = sample_rules[:2]
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/database/scan",
                    json={"rule_ids": [str(sample_rules[0].id), str(sample_rules[1].id)]}
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["status"] == ScanStatus.COMPLETED.value
            assert data["total_violations"] == 2
            assert data["rules_evaluated"] == 2
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_database_connection_error(
        self, mock_db_session, mock_scanner_service, sample_rules
    ):
        """Test scan when database connection fails during scan."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.scan_for_violations = AsyncMock(
            side_effect=DatabaseConnectionError("Connection lost during scan")
        )
        
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = sample_rules
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Connection lost" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_scan_unexpected_error(
        self, mock_db_session, mock_scanner_service, sample_rules
    ):
        """Test scan when unexpected error occurs."""
        mock_scanner_service.is_connected = True
        mock_scanner_service.scan_for_violations = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = sample_rules
        mock_db_session.execute = AsyncMock(return_value=mock_rules_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        scan_history_id = uuid.uuid4()
        scan_started_at = datetime.now(timezone.utc)
        
        async def mock_refresh(obj):
            if isinstance(obj, ScanHistory):
                obj.id = scan_history_id
                obj.started_at = scan_started_at
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_scanner():
            return mock_scanner_service
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_scanner_service] = override_get_scanner
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/database/scan")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "unexpected error" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestScanPydanticModels:
    """Tests for scan-related Pydantic models."""

    def test_scan_request_model_empty(self):
        """Test ScanRequest model with no parameters."""
        request = ScanRequest()
        assert request.rule_ids is None

    def test_scan_request_model_with_rule_ids(self):
        """Test ScanRequest model with rule IDs."""
        rule_ids = [uuid.uuid4(), uuid.uuid4()]
        request = ScanRequest(rule_ids=rule_ids)
        assert request.rule_ids == rule_ids

    def test_violation_count_by_severity_model(self):
        """Test ViolationCountBySeverity model."""
        counts = ViolationCountBySeverity(
            low=5,
            medium=10,
            high=3,
            critical=1,
        )
        assert counts.low == 5
        assert counts.medium == 10
        assert counts.high == 3
        assert counts.critical == 1

    def test_violation_count_by_severity_defaults(self):
        """Test ViolationCountBySeverity model with defaults."""
        counts = ViolationCountBySeverity()
        assert counts.low == 0
        assert counts.medium == 0
        assert counts.high == 0
        assert counts.critical == 0

    def test_scan_response_model(self):
        """Test ScanResponse model."""
        scan_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        
        response = ScanResponse(
            scan_id=scan_id,
            started_at=now,
            completed_at=now,
            status=ScanStatus.COMPLETED.value,
            total_violations=10,
            new_violations=5,
            violations_by_severity=ViolationCountBySeverity(
                low=2, medium=3, high=4, critical=1
            ),
            rules_evaluated=5,
            message="Scan completed successfully",
        )
        
        assert response.scan_id == scan_id
        assert response.status == ScanStatus.COMPLETED.value
        assert response.total_violations == 10
        assert response.new_violations == 5
        assert response.rules_evaluated == 5
        assert response.violations_by_severity.critical == 1

"""Unit tests for the Rules API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.compliance_rule import ComplianceRule
from app.models.enums import Severity
from app.routers.rules import RuleResponse, RuleUpdateRequest


# Test fixtures

@pytest.fixture
def sample_rule():
    """Create a sample compliance rule for testing."""
    rule = ComplianceRule(
        policy_id=uuid.uuid4(),
        rule_code="DATA-001",
        description="Personal data must be encrypted",
        evaluation_criteria="is_encrypted must be true",
        target_table="user_data",
        generated_sql="SELECT * FROM user_data WHERE is_encrypted = false",
        severity=Severity.HIGH.value,
        is_active=True,
    )
    rule.id = uuid.uuid4()
    rule.created_at = datetime.now(timezone.utc)
    return rule


@pytest.fixture
def sample_rules(sample_rule):
    """Create multiple sample rules for testing."""
    rule2 = ComplianceRule(
        policy_id=sample_rule.policy_id,
        rule_code="DATA-002",
        description="Passwords must be hashed",
        evaluation_criteria="password_hash must not be null",
        target_table="users",
        generated_sql="SELECT * FROM users WHERE password_hash IS NULL",
        severity=Severity.CRITICAL.value,
        is_active=True,
    )
    rule2.id = uuid.uuid4()
    rule2.created_at = datetime.now(timezone.utc)
    
    rule3 = ComplianceRule(
        policy_id=uuid.uuid4(),
        rule_code="DATA-003",
        description="Email addresses must be validated",
        evaluation_criteria="email must match valid format",
        target_table="contacts",
        generated_sql=None,
        severity=Severity.LOW.value,
        is_active=False,
    )
    rule3.id = uuid.uuid4()
    rule3.created_at = datetime.now(timezone.utc)
    
    return [sample_rule, rule2, rule3]


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


class TestListRules:
    """Tests for GET /api/rules endpoint."""

    @pytest.mark.asyncio
    async def test_list_rules_empty(self, mock_db_session):
        """Test listing rules when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/rules")
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_rules_with_data(self, mock_db_session, sample_rules):
        """Test listing rules with existing data."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_rules
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/rules")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 3
            assert data[0]["rule_code"] == "DATA-001"
            assert data[1]["rule_code"] == "DATA-002"
            assert data[2]["rule_code"] == "DATA-003"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_active(self, mock_db_session, sample_rules):
        """Test listing rules filtered by active status."""
        # Return only active rules
        active_rules = [r for r in sample_rules if r.is_active]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = active_rules
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/rules?is_active=true")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert all(r["is_active"] for r in data)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_severity(self, mock_db_session, sample_rules):
        """Test listing rules filtered by severity."""
        # Return only critical rules
        critical_rules = [r for r in sample_rules if r.severity == Severity.CRITICAL.value]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = critical_rules
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/rules?severity=critical")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["severity"] == "critical"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_policy_id(self, mock_db_session, sample_rules):
        """Test listing rules filtered by policy ID."""
        policy_id = sample_rules[0].policy_id
        # Return only rules for the specific policy
        policy_rules = [r for r in sample_rules if r.policy_id == policy_id]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = policy_rules
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/rules?policy_id={policy_id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert all(r["policy_id"] == str(policy_id) for r in data)
        finally:
            app.dependency_overrides.clear()


class TestGetRule:
    """Tests for GET /api/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, mock_db_session, sample_rule):
        """Test getting a specific rule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/rules/{sample_rule.id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["rule_code"] == "DATA-001"
            assert data["description"] == "Personal data must be encrypted"
            assert data["evaluation_criteria"] == "is_encrypted must be true"
            assert data["target_table"] == "user_data"
            assert data["severity"] == "high"
            assert data["is_active"] is True
            assert data["generated_sql"] == "SELECT * FROM user_data WHERE is_encrypted = false"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, mock_db_session):
        """Test getting a non-existent rule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                non_existent_id = uuid.uuid4()
                response = await client.get(f"/api/rules/{non_existent_id}")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestUpdateRule:
    """Tests for PATCH /api/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_rule_enable(self, mock_db_session, sample_rule):
        """Test enabling a rule."""
        sample_rule.is_active = False  # Start with disabled rule
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/rules/{sample_rule.id}",
                    json={"is_active": True}
                )
            
            assert response.status_code == status.HTTP_200_OK
            assert sample_rule.is_active is True
            mock_db_session.flush.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(sample_rule)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_rule_disable(self, mock_db_session, sample_rule):
        """Test disabling a rule."""
        sample_rule.is_active = True  # Start with enabled rule
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/rules/{sample_rule.id}",
                    json={"is_active": False}
                )
            
            assert response.status_code == status.HTTP_200_OK
            assert sample_rule.is_active is False
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self, mock_db_session):
        """Test updating a non-existent rule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                non_existent_id = uuid.uuid4()
                response = await client.patch(
                    f"/api/rules/{non_existent_id}",
                    json={"is_active": True}
                )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_rule_empty_body(self, mock_db_session, sample_rule):
        """Test updating a rule with empty body (no changes)."""
        original_is_active = sample_rule.is_active
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/rules/{sample_rule.id}",
                    json={}
                )
            
            assert response.status_code == status.HTTP_200_OK
            # is_active should remain unchanged
            assert sample_rule.is_active == original_is_active
        finally:
            app.dependency_overrides.clear()


class TestPydanticModels:
    """Tests for Pydantic models."""

    def test_rule_response_model(self, sample_rule):
        """Test RuleResponse model creation."""
        response = RuleResponse(
            id=sample_rule.id,
            policy_id=sample_rule.policy_id,
            rule_code=sample_rule.rule_code,
            description=sample_rule.description,
            evaluation_criteria=sample_rule.evaluation_criteria,
            target_table=sample_rule.target_table,
            generated_sql=sample_rule.generated_sql,
            severity=sample_rule.severity,
            is_active=sample_rule.is_active,
            created_at=sample_rule.created_at,
        )
        
        assert response.rule_code == "DATA-001"
        assert response.severity == "high"
        assert response.is_active is True
        assert response.generated_sql is not None

    def test_rule_response_model_with_null_fields(self):
        """Test RuleResponse model with null optional fields."""
        rule_id = uuid.uuid4()
        policy_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)
        
        response = RuleResponse(
            id=rule_id,
            policy_id=policy_id,
            rule_code="DATA-004",
            description="Test rule",
            evaluation_criteria="Test criteria",
            target_table=None,
            generated_sql=None,
            severity="medium",
            is_active=True,
            created_at=created_at,
        )
        
        assert response.target_table is None
        assert response.generated_sql is None

    def test_rule_update_request_model(self):
        """Test RuleUpdateRequest model creation."""
        request = RuleUpdateRequest(is_active=True)
        assert request.is_active is True
        
        request = RuleUpdateRequest(is_active=False)
        assert request.is_active is False
        
        request = RuleUpdateRequest()
        assert request.is_active is None

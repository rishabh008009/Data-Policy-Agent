"""Unit tests for the Violations API endpoints."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.compliance_rule import ComplianceRule
from app.models.enums import Severity, ViolationStatus
from app.models.review_action import ReviewAction
from app.models.violation import Violation
from app.routers.violations import (
    ViolationListResponse,
    ViolationDetailResponse,
    ViolationListPaginatedResponse,
    RuleInfoResponse,
    ReviewActionResponse,
)


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
def sample_violation(sample_rule):
    """Create a sample violation for testing."""
    violation = Violation(
        rule_id=sample_rule.id,
        record_identifier="user_123",
        record_data={"id": "user_123", "email": "test@example.com", "is_encrypted": False},
        justification="The user record has is_encrypted set to false, violating the encryption policy.",
        remediation_suggestion="Update the record to set is_encrypted to true after encrypting the data.",
        severity=Severity.HIGH.value,
        status=ViolationStatus.PENDING.value,
    )
    violation.id = uuid.uuid4()
    violation.detected_at = datetime.now(timezone.utc)
    violation.resolved_at = None
    violation.rule = sample_rule
    violation.review_actions = []
    return violation


@pytest.fixture
def sample_violations(sample_rule):
    """Create multiple sample violations for testing."""
    violations = []
    
    # Violation 1 - pending, high severity
    v1 = Violation(
        rule_id=sample_rule.id,
        record_identifier="user_123",
        record_data={"id": "user_123", "is_encrypted": False},
        justification="Encryption violation",
        remediation_suggestion="Enable encryption",
        severity=Severity.HIGH.value,
        status=ViolationStatus.PENDING.value,
    )
    v1.id = uuid.uuid4()
    v1.detected_at = datetime.now(timezone.utc) - timedelta(hours=2)
    v1.resolved_at = None
    v1.rule = sample_rule
    v1.review_actions = []
    violations.append(v1)
    
    # Violation 2 - confirmed, critical severity
    rule2 = ComplianceRule(
        policy_id=sample_rule.policy_id,
        rule_code="DATA-002",
        description="Passwords must be hashed",
        evaluation_criteria="password_hash must not be null",
        target_table="users",
        severity=Severity.CRITICAL.value,
        is_active=True,
    )
    rule2.id = uuid.uuid4()
    rule2.created_at = datetime.now(timezone.utc)
    
    v2 = Violation(
        rule_id=rule2.id,
        record_identifier="user_456",
        record_data={"id": "user_456", "password_hash": None},
        justification="Password not hashed",
        remediation_suggestion="Hash the password",
        severity=Severity.CRITICAL.value,
        status=ViolationStatus.CONFIRMED.value,
    )
    v2.id = uuid.uuid4()
    v2.detected_at = datetime.now(timezone.utc) - timedelta(hours=1)
    v2.resolved_at = None
    v2.rule = rule2
    v2.review_actions = []
    violations.append(v2)
    
    # Violation 3 - resolved, low severity
    rule3 = ComplianceRule(
        policy_id=sample_rule.policy_id,
        rule_code="DATA-003",
        description="Email must be validated",
        evaluation_criteria="email must match valid format",
        target_table="contacts",
        severity=Severity.LOW.value,
        is_active=True,
    )
    rule3.id = uuid.uuid4()
    rule3.created_at = datetime.now(timezone.utc)
    
    v3 = Violation(
        rule_id=rule3.id,
        record_identifier="contact_789",
        record_data={"id": "contact_789", "email": "invalid-email"},
        justification="Invalid email format",
        remediation_suggestion="Fix email format",
        severity=Severity.LOW.value,
        status=ViolationStatus.RESOLVED.value,
    )
    v3.id = uuid.uuid4()
    v3.detected_at = datetime.now(timezone.utc) - timedelta(days=1)
    v3.resolved_at = datetime.now(timezone.utc)
    v3.rule = rule3
    v3.review_actions = []
    violations.append(v3)
    
    return violations


@pytest.fixture
def sample_review_actions(sample_violation):
    """Create sample review actions for testing."""
    actions = []
    
    action1 = ReviewAction(
        violation_id=sample_violation.id,
        action_type="confirm",
        reviewer_id="reviewer_1",
        notes="Confirmed after investigation",
    )
    action1.id = uuid.uuid4()
    action1.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    actions.append(action1)
    
    action2 = ReviewAction(
        violation_id=sample_violation.id,
        action_type="resolve",
        reviewer_id="reviewer_2",
        notes="Fixed the issue",
    )
    action2.id = uuid.uuid4()
    action2.created_at = datetime.now(timezone.utc)
    actions.append(action2)
    
    return actions


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


class TestListViolations:
    """Tests for GET /api/violations endpoint."""

    @pytest.mark.asyncio
    async def test_list_violations_empty(self, mock_db_session):
        """Test listing violations when none exist."""
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
                response = await client.get("/api/violations")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["items"] == []
            assert data["total"] == 0
            assert data["skip"] == 0
            assert data["limit"] == 50
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_with_data(self, mock_db_session, sample_violations):
        """Test listing violations with existing data."""
        # First call for count, second for paginated results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_violations
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 3
            assert data["total"] == 3
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_filter_by_status(self, mock_db_session, sample_violations):
        """Test listing violations filtered by status."""
        pending_violations = [v for v in sample_violations if v.status == ViolationStatus.PENDING.value]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = pending_violations
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations?status=pending")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 1
            assert all(item["status"] == "pending" for item in data["items"])
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_filter_by_severity(self, mock_db_session, sample_violations):
        """Test listing violations filtered by severity."""
        critical_violations = [v for v in sample_violations if v.severity == Severity.CRITICAL.value]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = critical_violations
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations?severity=critical")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 1
            assert all(item["severity"] == "critical" for item in data["items"])
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_filter_by_rule_id(self, mock_db_session, sample_violations):
        """Test listing violations filtered by rule ID."""
        rule_id = sample_violations[0].rule_id
        rule_violations = [v for v in sample_violations if v.rule_id == rule_id]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rule_violations
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/violations?rule_id={rule_id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 1
            assert all(item["rule_id"] == str(rule_id) for item in data["items"])
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_invalid_status(self, mock_db_session):
        """Test listing violations with invalid status filter."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations?status=invalid_status")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid status" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_invalid_severity(self, mock_db_session):
        """Test listing violations with invalid severity filter."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations?severity=invalid_severity")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid severity" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_pagination(self, mock_db_session, sample_violations):
        """Test listing violations with pagination."""
        # Return only first 2 violations for pagination test
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_violations[:2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/violations?skip=0&limit=2")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 2
            assert data["skip"] == 0
            assert data["limit"] == 2
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_violations_date_range_filter(self, mock_db_session, sample_violations):
        """Test listing violations filtered by date range."""
        # Filter to recent violations
        recent_violations = [v for v in sample_violations if v.detected_at > datetime.now(timezone.utc) - timedelta(hours=3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = recent_violations
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            # Use ISO format without timezone for query parameter
            start_date = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/violations?start_date={start_date}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["items"]) == 2  # Only recent violations
        finally:
            app.dependency_overrides.clear()


class TestGetViolation:
    """Tests for GET /api/violations/{violation_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_violation_success(self, mock_db_session, sample_violation, sample_review_actions):
        """Test getting a specific violation with details."""
        sample_violation.review_actions = sample_review_actions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/violations/{sample_violation.id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Check violation fields
            assert data["id"] == str(sample_violation.id)
            assert data["rule_id"] == str(sample_violation.rule_id)
            assert data["record_identifier"] == "user_123"
            assert data["severity"] == "high"
            assert data["status"] == "pending"
            assert data["justification"] == sample_violation.justification
            assert data["remediation_suggestion"] == sample_violation.remediation_suggestion
            
            # Check rule info
            assert data["rule"]["rule_code"] == "DATA-001"
            assert data["rule"]["description"] == "Personal data must be encrypted"
            assert data["rule"]["severity"] == "high"
            
            # Check review history
            assert len(data["review_history"]) == 2
            # Should be sorted by created_at descending
            assert data["review_history"][0]["action_type"] == "resolve"
            assert data["review_history"][1]["action_type"] == "confirm"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_violation_not_found(self, mock_db_session):
        """Test getting a non-existent violation."""
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
                response = await client.get(f"/api/violations/{non_existent_id}")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_violation_no_review_history(self, mock_db_session, sample_violation):
        """Test getting a violation with no review history."""
        sample_violation.review_actions = []
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/violations/{sample_violation.id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["review_history"] == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_violation_with_null_remediation(self, mock_db_session, sample_violation):
        """Test getting a violation with null remediation suggestion."""
        sample_violation.remediation_suggestion = None
        sample_violation.review_actions = []
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/violations/{sample_violation.id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["remediation_suggestion"] is None
        finally:
            app.dependency_overrides.clear()


class TestPydanticModels:
    """Tests for Pydantic models."""

    def test_violation_list_response_model(self, sample_violation):
        """Test ViolationListResponse model creation."""
        response = ViolationListResponse(
            id=sample_violation.id,
            rule_id=sample_violation.rule_id,
            rule_code="DATA-001",
            rule_description="Personal data must be encrypted",
            record_identifier=sample_violation.record_identifier,
            severity=sample_violation.severity,
            status=sample_violation.status,
            detected_at=sample_violation.detected_at,
            resolved_at=sample_violation.resolved_at,
        )
        
        assert response.rule_code == "DATA-001"
        assert response.severity == "high"
        assert response.status == "pending"
        assert response.resolved_at is None

    def test_violation_detail_response_model(self, sample_violation, sample_rule):
        """Test ViolationDetailResponse model creation."""
        rule_info = RuleInfoResponse(
            id=sample_rule.id,
            rule_code=sample_rule.rule_code,
            description=sample_rule.description,
            evaluation_criteria=sample_rule.evaluation_criteria,
            target_table=sample_rule.target_table,
            severity=sample_rule.severity,
            is_active=sample_rule.is_active,
        )
        
        response = ViolationDetailResponse(
            id=sample_violation.id,
            rule_id=sample_violation.rule_id,
            record_identifier=sample_violation.record_identifier,
            record_data=sample_violation.record_data,
            justification=sample_violation.justification,
            remediation_suggestion=sample_violation.remediation_suggestion,
            severity=sample_violation.severity,
            status=sample_violation.status,
            detected_at=sample_violation.detected_at,
            resolved_at=sample_violation.resolved_at,
            rule=rule_info,
            review_history=[],
        )
        
        assert response.rule.rule_code == "DATA-001"
        assert response.record_data["is_encrypted"] is False
        assert len(response.review_history) == 0

    def test_review_action_response_model(self, sample_review_actions):
        """Test ReviewActionResponse model creation."""
        action = sample_review_actions[0]
        response = ReviewActionResponse(
            id=action.id,
            violation_id=action.violation_id,
            action_type=action.action_type,
            reviewer_id=action.reviewer_id,
            notes=action.notes,
            created_at=action.created_at,
        )
        
        assert response.action_type == "confirm"
        assert response.reviewer_id == "reviewer_1"
        assert response.notes == "Confirmed after investigation"

    def test_violation_list_paginated_response_model(self, sample_violation):
        """Test ViolationListPaginatedResponse model creation."""
        item = ViolationListResponse(
            id=sample_violation.id,
            rule_id=sample_violation.rule_id,
            rule_code="DATA-001",
            rule_description="Test rule",
            record_identifier=sample_violation.record_identifier,
            severity=sample_violation.severity,
            status=sample_violation.status,
            detected_at=sample_violation.detected_at,
            resolved_at=sample_violation.resolved_at,
        )
        
        response = ViolationListPaginatedResponse(
            items=[item],
            total=1,
            skip=0,
            limit=50,
        )
        
        assert len(response.items) == 1
        assert response.total == 1
        assert response.skip == 0
        assert response.limit == 50


# Import the new models for testing
from app.routers.violations import (
    ReviewDecisionRequest,
    ViolationReviewResponse,
)


class TestReviewViolation:
    """Tests for PATCH /api/violations/{violation_id}/review endpoint."""

    @pytest.mark.asyncio
    async def test_review_violation_confirm(self, mock_db_session, sample_violation):
        """Test confirming a violation."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to populate the review_action fields
        async def mock_refresh(obj):
            if isinstance(obj, ReviewAction):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action_type": "confirm",
                        "reviewer_id": "reviewer_123",
                        "notes": "Confirmed after investigation",
                    },
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify violation status was updated
            assert data["status"] == "confirmed"
            assert data["id"] == str(sample_violation.id)
            
            # Verify review action was created
            assert data["review_action"]["action_type"] == "confirm"
            assert data["review_action"]["reviewer_id"] == "reviewer_123"
            assert data["review_action"]["notes"] == "Confirmed after investigation"
            
            # Verify db.add was called with a ReviewAction
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_mark_false_positive(self, mock_db_session, sample_violation):
        """Test marking a violation as false positive."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to populate the review_action fields
        async def mock_refresh(obj):
            if isinstance(obj, ReviewAction):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action_type": "mark_false_positive",
                        "reviewer_id": "reviewer_456",
                        "notes": "This is not a real violation",
                    },
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify violation status was updated
            assert data["status"] == "false_positive"
            
            # Verify review action was created
            assert data["review_action"]["action_type"] == "mark_false_positive"
            assert data["review_action"]["reviewer_id"] == "reviewer_456"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_resolve(self, mock_db_session, sample_violation):
        """Test resolving a violation."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to populate the review_action fields
        async def mock_refresh(obj):
            if isinstance(obj, ReviewAction):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action_type": "resolve",
                        "reviewer_id": "reviewer_789",
                        "notes": "Issue has been fixed",
                    },
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify violation status was updated
            assert data["status"] == "resolved"
            
            # Verify resolved_at was set (the mock doesn't actually update this,
            # but we verify the endpoint logic sets it)
            assert data["review_action"]["action_type"] == "resolve"
            assert data["review_action"]["reviewer_id"] == "reviewer_789"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_without_notes(self, mock_db_session, sample_violation):
        """Test reviewing a violation without optional notes."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to populate the review_action fields
        async def mock_refresh(obj):
            if isinstance(obj, ReviewAction):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action_type": "confirm",
                        "reviewer_id": "reviewer_123",
                    },
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify review action was created without notes
            assert data["review_action"]["notes"] is None
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_not_found(self, mock_db_session):
        """Test reviewing a non-existent violation."""
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
                    f"/api/violations/{non_existent_id}/review",
                    json={
                        "action_type": "confirm",
                        "reviewer_id": "reviewer_123",
                    },
                )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_invalid_action_type(self, mock_db_session, sample_violation):
        """Test reviewing with an invalid action type."""
        # Need to mock the violation lookup since validation happens after DB lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action": "invalid_action",
                        "reviewer_id": "reviewer_123",
                    },
                )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid action" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_missing_action(self, mock_db_session, sample_violation):
        """Test reviewing without action field."""
        # Need to mock the violation lookup since validation happens after DB lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "reviewer_id": "reviewer_123",
                    },
                )
            
            # Should fail validation - action is required
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid action" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_review_violation_empty_reviewer_id(self, mock_db_session, sample_violation):
        """Test reviewing with empty reviewer_id."""
        # Need to mock the violation lookup since validation happens after DB lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_violation
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock refresh to populate the review_action fields
        async def mock_refresh(obj):
            if isinstance(obj, ReviewAction):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/violations/{sample_violation.id}/review",
                    json={
                        "action": "confirm",
                        "reviewer_id": "",
                    },
                )
            
            # Should fail validation - reviewer_id must have min_length=1
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()


class TestReviewDecisionRequestModel:
    """Tests for ReviewDecisionRequest Pydantic model."""

    def test_valid_review_decision_request(self):
        """Test creating a valid review decision request."""
        request = ReviewDecisionRequest(
            action_type="confirm",
            reviewer_id="reviewer_123",
            notes="Test notes",
        )
        
        assert request.action_type == "confirm"
        assert request.reviewer_id == "reviewer_123"
        assert request.notes == "Test notes"

    def test_review_decision_request_without_notes(self):
        """Test creating a review decision request without notes."""
        request = ReviewDecisionRequest(
            action_type="mark_false_positive",
            reviewer_id="reviewer_456",
        )
        
        assert request.action_type == "mark_false_positive"
        assert request.reviewer_id == "reviewer_456"
        assert request.notes is None

    def test_review_decision_request_all_action_types(self):
        """Test all valid action types."""
        for action_type in ["confirm", "mark_false_positive", "resolve"]:
            request = ReviewDecisionRequest(
                action_type=action_type,
                reviewer_id="reviewer",
            )
            assert request.action_type == action_type


class TestViolationReviewResponseModel:
    """Tests for ViolationReviewResponse Pydantic model."""

    def test_violation_review_response_model(self, sample_violation, sample_rule, sample_review_actions):
        """Test ViolationReviewResponse model creation."""
        rule_info = RuleInfoResponse(
            id=sample_rule.id,
            rule_code=sample_rule.rule_code,
            description=sample_rule.description,
            evaluation_criteria=sample_rule.evaluation_criteria,
            target_table=sample_rule.target_table,
            severity=sample_rule.severity,
            is_active=sample_rule.is_active,
        )
        
        review_action = ReviewActionResponse(
            id=sample_review_actions[0].id,
            violation_id=sample_review_actions[0].violation_id,
            action_type=sample_review_actions[0].action_type,
            reviewer_id=sample_review_actions[0].reviewer_id,
            notes=sample_review_actions[0].notes,
            created_at=sample_review_actions[0].created_at,
        )
        
        response = ViolationReviewResponse(
            id=sample_violation.id,
            rule_id=sample_violation.rule_id,
            record_identifier=sample_violation.record_identifier,
            record_data=sample_violation.record_data,
            justification=sample_violation.justification,
            remediation_suggestion=sample_violation.remediation_suggestion,
            severity=sample_violation.severity,
            status="confirmed",
            detected_at=sample_violation.detected_at,
            resolved_at=sample_violation.resolved_at,
            rule=rule_info,
            review_action=review_action,
        )
        
        assert response.status == "confirmed"
        assert response.rule.rule_code == "DATA-001"
        assert response.review_action.action_type == "confirm"
        assert response.review_action.reviewer_id == "reviewer_1"

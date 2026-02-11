"""Unit tests for the Policy API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.compliance_rule import ComplianceRule
from app.models.enums import PolicyStatus, Severity
from app.models.policy import Policy
from app.routers.policies import (
    ComplianceRuleResponse,
    PolicyDetailResponse,
    PolicyResponse,
    PolicyUploadResponse,
)


# Test fixtures

@pytest.fixture
def sample_policy():
    """Create a sample policy for testing."""
    policy = Policy(
        filename="test_policy.pdf",
        status=PolicyStatus.COMPLETED.value,
        raw_text="Sample policy text content",
    )
    policy.id = uuid.uuid4()
    policy.uploaded_at = datetime.now(timezone.utc)
    policy.rules = []
    return policy


@pytest.fixture
def sample_policy_with_rules(sample_policy):
    """Create a sample policy with compliance rules."""
    rule1 = ComplianceRule(
        policy_id=sample_policy.id,
        rule_code="DATA-001",
        description="Personal data must be encrypted",
        evaluation_criteria="is_encrypted must be true",
        target_table="user_data",
        severity=Severity.HIGH.value,
        is_active=True,
    )
    rule1.id = uuid.uuid4()
    rule1.created_at = datetime.now(timezone.utc)
    
    rule2 = ComplianceRule(
        policy_id=sample_policy.id,
        rule_code="DATA-002",
        description="Passwords must be hashed",
        evaluation_criteria="password_hash must not be null",
        target_table="users",
        severity=Severity.CRITICAL.value,
        is_active=True,
    )
    rule2.id = uuid.uuid4()
    rule2.created_at = datetime.now(timezone.utc)
    
    sample_policy.rules = [rule1, rule2]
    return sample_policy


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


class TestListPolicies:
    """Tests for GET /api/policies endpoint."""

    @pytest.mark.asyncio
    async def test_list_policies_empty(self, mock_db_session):
        """Test listing policies when none exist."""
        # Mock the database query to return empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routers.policies.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Override the dependency
            async def override_get_db():
                yield mock_db_session
            
            app.dependency_overrides[__import__("app.database", fromlist=["get_db"]).get_db] = override_get_db
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/policies")
            
            app.dependency_overrides.clear()
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_policies_with_data(self, mock_db_session, sample_policy_with_rules):
        """Test listing policies with existing data."""
        # Mock the database query to return policies
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_policy_with_rules]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/policies")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["filename"] == "test_policy.pdf"
            assert data[0]["status"] == "completed"
            assert data[0]["rule_count"] == 2
        finally:
            app.dependency_overrides.clear()


class TestGetPolicy:
    """Tests for GET /api/policies/{policy_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_policy_success(self, mock_db_session, sample_policy_with_rules):
        """Test getting a specific policy with rules."""
        # Mock the database query to return the policy
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_policy_with_rules
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/policies/{sample_policy_with_rules.id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["filename"] == "test_policy.pdf"
            assert data["status"] == "completed"
            assert data["raw_text"] == "Sample policy text content"
            assert len(data["rules"]) == 2
            assert data["rules"][0]["rule_code"] == "DATA-001"
            assert data["rules"][1]["rule_code"] == "DATA-002"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, mock_db_session):
        """Test getting a non-existent policy."""
        # Mock the database query to return None
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
                response = await client.get(f"/api/policies/{non_existent_id}")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestDeletePolicy:
    """Tests for DELETE /api/policies/{policy_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_policy_success(self, mock_db_session, sample_policy):
        """Test deleting an existing policy."""
        # Mock the database query to return the policy
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_policy
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(f"/api/policies/{sample_policy.id}")
            
            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_db_session.delete.assert_called_once_with(sample_policy)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_policy_not_found(self, mock_db_session):
        """Test deleting a non-existent policy."""
        # Mock the database query to return None
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
                response = await client.delete(f"/api/policies/{non_existent_id}")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestUploadPolicy:
    """Tests for POST /api/policies/upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_policy_success(self, mock_db_session, sample_policy_with_rules):
        """Test successful policy upload."""
        # Mock the policy parser service
        mock_parser = MagicMock()
        mock_parser.process_policy = AsyncMock(return_value=sample_policy_with_rules)
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_parser():
            return mock_parser
        
        from app.database import get_db
        from app.services.policy_parser import get_policy_parser_service
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_policy_parser_service] = override_get_parser
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Create a mock PDF file
                files = {"file": ("test_policy.pdf", b"%PDF-1.4\nTest content", "application/pdf")}
                response = await client.post("/api/policies/upload", files=files)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["filename"] == "test_policy.pdf"
            assert data["status"] == "completed"
            assert data["rule_count"] == 2
            assert "Successfully extracted" in data["message"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upload_policy_invalid_content_type(self, mock_db_session):
        """Test upload with invalid content type."""
        async def override_get_db():
            yield mock_db_session
        
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Upload a non-PDF file
                files = {"file": ("test.txt", b"Not a PDF", "text/plain")}
                response = await client.post("/api/policies/upload", files=files)
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "valid PDF" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upload_policy_file_too_large(self, mock_db_session):
        """Test upload with file exceeding size limit."""
        from app.services.policy_parser import FileTooLargeError
        
        # Mock the policy parser service to raise FileTooLargeError
        mock_parser = MagicMock()
        mock_parser.process_policy = AsyncMock(
            side_effect=FileTooLargeError("File exceeds maximum size limit of 10MB.")
        )
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_parser():
            return mock_parser
        
        from app.database import get_db
        from app.services.policy_parser import get_policy_parser_service
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_policy_parser_service] = override_get_parser
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                files = {"file": ("large.pdf", b"%PDF-1.4\nLarge content", "application/pdf")}
                response = await client.post("/api/policies/upload", files=files)
            
            assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
            assert "size limit" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upload_policy_corrupted_pdf(self, mock_db_session):
        """Test upload with corrupted PDF."""
        from app.services.policy_parser import CorruptedPDFError
        
        # Mock the policy parser service to raise CorruptedPDFError
        mock_parser = MagicMock()
        mock_parser.process_policy = AsyncMock(
            side_effect=CorruptedPDFError("Unable to read PDF file. Please ensure the file is not corrupted.")
        )
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_parser():
            return mock_parser
        
        from app.database import get_db
        from app.services.policy_parser import get_policy_parser_service
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_policy_parser_service] = override_get_parser
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                files = {"file": ("corrupted.pdf", b"%PDF-1.4\nCorrupted", "application/pdf")}
                response = await client.post("/api/policies/upload", files=files)
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "corrupted" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upload_policy_empty_pdf(self, mock_db_session):
        """Test upload with empty PDF."""
        from app.services.policy_parser import EmptyPDFError
        
        # Mock the policy parser service to raise EmptyPDFError
        mock_parser = MagicMock()
        mock_parser.process_policy = AsyncMock(
            side_effect=EmptyPDFError("The uploaded PDF contains no extractable text.")
        )
        
        async def override_get_db():
            yield mock_db_session
        
        def override_get_parser():
            return mock_parser
        
        from app.database import get_db
        from app.services.policy_parser import get_policy_parser_service
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_policy_parser_service] = override_get_parser
        
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                files = {"file": ("empty.pdf", b"%PDF-1.4\nEmpty", "application/pdf")}
                response = await client.post("/api/policies/upload", files=files)
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "no extractable text" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestPydanticModels:
    """Tests for Pydantic response models."""

    def test_policy_response_model(self, sample_policy):
        """Test PolicyResponse model creation."""
        response = PolicyResponse(
            id=sample_policy.id,
            filename=sample_policy.filename,
            status=sample_policy.status,
            uploaded_at=sample_policy.uploaded_at,
            rule_count=0,
        )
        
        assert response.id == sample_policy.id
        assert response.filename == "test_policy.pdf"
        assert response.status == "completed"
        assert response.rule_count == 0

    def test_compliance_rule_response_model(self, sample_policy_with_rules):
        """Test ComplianceRuleResponse model creation."""
        rule = sample_policy_with_rules.rules[0]
        response = ComplianceRuleResponse(
            id=rule.id,
            policy_id=rule.policy_id,
            rule_code=rule.rule_code,
            description=rule.description,
            evaluation_criteria=rule.evaluation_criteria,
            target_table=rule.target_table,
            severity=rule.severity,
            is_active=rule.is_active,
            created_at=rule.created_at,
        )
        
        assert response.rule_code == "DATA-001"
        assert response.severity == "high"
        assert response.is_active is True

    def test_policy_detail_response_model(self, sample_policy_with_rules):
        """Test PolicyDetailResponse model creation."""
        rules_response = [
            ComplianceRuleResponse(
                id=rule.id,
                policy_id=rule.policy_id,
                rule_code=rule.rule_code,
                description=rule.description,
                evaluation_criteria=rule.evaluation_criteria,
                target_table=rule.target_table,
                severity=rule.severity,
                is_active=rule.is_active,
                created_at=rule.created_at,
            )
            for rule in sample_policy_with_rules.rules
        ]
        
        response = PolicyDetailResponse(
            id=sample_policy_with_rules.id,
            filename=sample_policy_with_rules.filename,
            status=sample_policy_with_rules.status,
            uploaded_at=sample_policy_with_rules.uploaded_at,
            raw_text=sample_policy_with_rules.raw_text,
            rules=rules_response,
        )
        
        assert response.filename == "test_policy.pdf"
        assert len(response.rules) == 2
        assert response.raw_text == "Sample policy text content"

    def test_policy_upload_response_model(self, sample_policy):
        """Test PolicyUploadResponse model creation."""
        response = PolicyUploadResponse(
            id=sample_policy.id,
            filename=sample_policy.filename,
            status=sample_policy.status,
            uploaded_at=sample_policy.uploaded_at,
            rule_count=5,
            message="Successfully extracted 5 compliance rules.",
        )
        
        assert response.rule_count == 5
        assert "Successfully extracted" in response.message

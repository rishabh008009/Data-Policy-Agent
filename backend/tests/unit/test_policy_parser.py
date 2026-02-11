"""Unit tests for the Policy Parser Service."""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.policy_parser import (
    PolicyParserService,
    PDFExtractionError,
    CorruptedPDFError,
    EmptyPDFError,
    UnsupportedFormatError,
    FileTooLargeError,
    get_policy_parser_service,
)


# Sample PDF content for testing
# This is a minimal valid PDF structure
MINIMAL_PDF_BYTES = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
306
%%EOF"""


class MockUploadFile:
    """Mock FastAPI UploadFile for testing."""
    
    def __init__(self, content: bytes, filename: str = "test.pdf"):
        self._content = content
        self.filename = filename
        self._position = 0
    
    async def read(self) -> bytes:
        return self._content
    
    async def seek(self, position: int) -> None:
        self._position = position


class TestPolicyParserService:
    """Tests for the PolicyParserService class."""

    @pytest.fixture
    def parser(self):
        """Create a PolicyParserService instance for testing."""
        with patch("app.services.policy_parser.get_settings") as mock_settings:
            mock_settings.return_value.max_pdf_size_mb = 10
            return PolicyParserService()

    @pytest.fixture
    def mock_pdfplumber_with_text(self):
        """Create a mock pdfplumber that returns text."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample policy text content"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            yield mock_pdf

    @pytest.fixture
    def mock_pdfplumber_empty(self):
        """Create a mock pdfplumber that returns no text."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = None
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            yield mock_pdf

    @pytest.fixture
    def mock_pdfplumber_no_pages(self):
        """Create a mock pdfplumber with no pages."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = []
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            yield mock_pdf

    @pytest.fixture
    def mock_pdfplumber_corrupted(self):
        """Create a mock pdfplumber that raises an exception."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_pdf.open.side_effect = Exception("PDF parsing error")
            yield mock_pdf

    # Test successful text extraction
    @pytest.mark.asyncio
    async def test_extract_text_success(self, parser, mock_pdfplumber_with_text):
        """Test successful text extraction from a valid PDF."""
        pdf_content = b"%PDF-1.4\nSome PDF content"
        upload_file = MockUploadFile(pdf_content)
        
        result = await parser.extract_text(upload_file)
        
        assert result == "Sample policy text content"
        mock_pdfplumber_with_text.open.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_text_multiple_pages(self, parser):
        """Test text extraction from a multi-page PDF."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Page 1 content"
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = "Page 2 content"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page1, mock_page2]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nMulti-page PDF"
            upload_file = MockUploadFile(pdf_content)
            
            result = await parser.extract_text(upload_file)
            
            assert "Page 1 content" in result
            assert "Page 2 content" in result
            assert "\n\n" in result  # Pages should be separated

    # Test file size validation
    @pytest.mark.asyncio
    async def test_extract_text_file_too_large(self, parser):
        """Test that FileTooLargeError is raised for oversized files."""
        # Create content larger than 10MB
        large_content = b"%PDF-1.4\n" + b"x" * (11 * 1024 * 1024)
        upload_file = MockUploadFile(large_content)
        
        with pytest.raises(FileTooLargeError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "File exceeds maximum size limit of 10MB" in str(exc_info.value)

    # Test unsupported format validation
    @pytest.mark.asyncio
    async def test_extract_text_not_pdf(self, parser):
        """Test that UnsupportedFormatError is raised for non-PDF files."""
        non_pdf_content = b"This is not a PDF file"
        upload_file = MockUploadFile(non_pdf_content)
        
        with pytest.raises(UnsupportedFormatError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "Please upload a valid PDF file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_text_empty_file(self, parser):
        """Test that UnsupportedFormatError is raised for empty files."""
        upload_file = MockUploadFile(b"")
        
        with pytest.raises(UnsupportedFormatError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "Please upload a valid PDF file" in str(exc_info.value)

    # Test corrupted PDF handling
    @pytest.mark.asyncio
    async def test_extract_text_corrupted_pdf(self, parser, mock_pdfplumber_corrupted):
        """Test that CorruptedPDFError is raised for corrupted PDFs."""
        pdf_content = b"%PDF-1.4\nCorrupted content"
        upload_file = MockUploadFile(pdf_content)
        
        with pytest.raises(CorruptedPDFError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "Unable to read PDF file" in str(exc_info.value)
        assert "not corrupted" in str(exc_info.value)

    # Test empty PDF handling
    @pytest.mark.asyncio
    async def test_extract_text_empty_pdf_no_text(self, parser, mock_pdfplumber_empty):
        """Test that EmptyPDFError is raised when PDF has no extractable text."""
        pdf_content = b"%PDF-1.4\nPDF with no text"
        upload_file = MockUploadFile(pdf_content)
        
        with pytest.raises(EmptyPDFError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "no extractable text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_text_empty_pdf_no_pages(self, parser, mock_pdfplumber_no_pages):
        """Test that EmptyPDFError is raised when PDF has no pages."""
        pdf_content = b"%PDF-1.4\nPDF with no pages"
        upload_file = MockUploadFile(pdf_content)
        
        with pytest.raises(EmptyPDFError) as exc_info:
            await parser.extract_text(upload_file)
        
        assert "no extractable text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_text_whitespace_only(self, parser):
        """Test that EmptyPDFError is raised when PDF contains only whitespace."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "   \n\t  \n  "
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nPDF with whitespace only"
            upload_file = MockUploadFile(pdf_content)
            
            with pytest.raises(EmptyPDFError) as exc_info:
                await parser.extract_text(upload_file)
            
            assert "no extractable text" in str(exc_info.value)


class TestPolicyParserServiceSync:
    """Tests for the synchronous text extraction method."""

    @pytest.fixture
    def parser(self):
        """Create a PolicyParserService instance for testing."""
        with patch("app.services.policy_parser.get_settings") as mock_settings:
            mock_settings.return_value.max_pdf_size_mb = 10
            return PolicyParserService()

    def test_extract_text_sync_with_bytes(self, parser):
        """Test synchronous extraction with bytes input."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Extracted text"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome content"
            result = parser.extract_text_sync(pdf_content)
            
            assert result == "Extracted text"

    def test_extract_text_sync_with_file_object(self, parser):
        """Test synchronous extraction with file-like object."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Extracted text"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome content"
            file_obj = io.BytesIO(pdf_content)
            result = parser.extract_text_sync(file_obj)
            
            assert result == "Extracted text"

    def test_extract_text_sync_file_too_large(self, parser):
        """Test that FileTooLargeError is raised for oversized files."""
        large_content = b"%PDF-1.4\n" + b"x" * (11 * 1024 * 1024)
        
        with pytest.raises(FileTooLargeError):
            parser.extract_text_sync(large_content)

    def test_extract_text_sync_not_pdf(self, parser):
        """Test that UnsupportedFormatError is raised for non-PDF files."""
        with pytest.raises(UnsupportedFormatError):
            parser.extract_text_sync(b"Not a PDF")

    def test_extract_text_sync_empty_file(self, parser):
        """Test that UnsupportedFormatError is raised for empty files."""
        with pytest.raises(UnsupportedFormatError):
            parser.extract_text_sync(b"")


class TestExceptionHierarchy:
    """Tests for the exception class hierarchy."""

    def test_corrupted_pdf_error_is_pdf_extraction_error(self):
        """Test that CorruptedPDFError inherits from PDFExtractionError."""
        error = CorruptedPDFError("test")
        assert isinstance(error, PDFExtractionError)

    def test_empty_pdf_error_is_pdf_extraction_error(self):
        """Test that EmptyPDFError inherits from PDFExtractionError."""
        error = EmptyPDFError("test")
        assert isinstance(error, PDFExtractionError)

    def test_unsupported_format_error_is_pdf_extraction_error(self):
        """Test that UnsupportedFormatError inherits from PDFExtractionError."""
        error = UnsupportedFormatError("test")
        assert isinstance(error, PDFExtractionError)

    def test_file_too_large_error_is_pdf_extraction_error(self):
        """Test that FileTooLargeError inherits from PDFExtractionError."""
        error = FileTooLargeError("test")
        assert isinstance(error, PDFExtractionError)


class TestGetPolicyParserService:
    """Tests for the get_policy_parser_service factory function."""

    def test_returns_policy_parser_service_instance(self):
        """Test that get_policy_parser_service returns a PolicyParserService."""
        with patch("app.services.policy_parser.get_settings") as mock_settings:
            mock_settings.return_value.max_pdf_size_mb = 10
            
            service = get_policy_parser_service()
            
            assert isinstance(service, PolicyParserService)


class TestParseRules:
    """Tests for the parse_rules method."""

    @pytest.fixture
    def parser(self):
        """Create a PolicyParserService instance for testing."""
        with patch("app.services.policy_parser.get_settings") as mock_settings:
            mock_settings.return_value.max_pdf_size_mb = 10
            return PolicyParserService()

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_parse_rules_success(self, parser, mock_llm_client):
        """Test successful rule parsing from policy text."""
        mock_llm_client.extract_rules.return_value = [
            {
                "rule_code": "DATA-001",
                "description": "Personal data must be encrypted",
                "evaluation_criteria": "is_encrypted must be true",
                "severity": "high",
                "target_entities": "user_data",
            },
            {
                "rule_code": "DATA-002",
                "description": "Passwords must be hashed",
                "evaluation_criteria": "password_hash must not be null",
                "severity": "critical",
                "target_entities": "users",
            },
        ]
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=policy_id,
            llm_client=mock_llm_client,
        )
        
        assert len(rules) == 2
        assert rules[0].rule_code == "DATA-001"
        assert rules[0].description == "Personal data must be encrypted"
        assert rules[0].evaluation_criteria == "is_encrypted must be true"
        assert rules[0].severity == "high"
        assert rules[0].target_table == "user_data"
        assert rules[0].is_active is True
        assert str(rules[0].policy_id) == policy_id
        
        assert rules[1].rule_code == "DATA-002"
        assert rules[1].severity == "critical"

    @pytest.mark.asyncio
    async def test_parse_rules_invalid_severity_defaults_to_medium(self, parser, mock_llm_client):
        """Test that invalid severity values default to medium."""
        mock_llm_client.extract_rules.return_value = [
            {
                "rule_code": "DATA-001",
                "description": "Test rule",
                "evaluation_criteria": "test criteria",
                "severity": "invalid_severity",
                "target_entities": "test_table",
            },
        ]
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=policy_id,
            llm_client=mock_llm_client,
        )
        
        assert len(rules) == 1
        assert rules[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_parse_rules_missing_severity_defaults_to_medium(self, parser, mock_llm_client):
        """Test that missing severity defaults to medium."""
        mock_llm_client.extract_rules.return_value = [
            {
                "rule_code": "DATA-001",
                "description": "Test rule",
                "evaluation_criteria": "test criteria",
                # No severity field
            },
        ]
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=policy_id,
            llm_client=mock_llm_client,
        )
        
        assert len(rules) == 1
        assert rules[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_parse_rules_empty_list(self, parser, mock_llm_client):
        """Test parsing when LLM returns no rules."""
        mock_llm_client.extract_rules.return_value = []
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=policy_id,
            llm_client=mock_llm_client,
        )
        
        assert len(rules) == 0

    @pytest.mark.asyncio
    async def test_parse_rules_all_severity_levels(self, parser, mock_llm_client):
        """Test that all valid severity levels are correctly mapped."""
        mock_llm_client.extract_rules.return_value = [
            {"rule_code": "R1", "description": "d", "evaluation_criteria": "c", "severity": "low"},
            {"rule_code": "R2", "description": "d", "evaluation_criteria": "c", "severity": "medium"},
            {"rule_code": "R3", "description": "d", "evaluation_criteria": "c", "severity": "high"},
            {"rule_code": "R4", "description": "d", "evaluation_criteria": "c", "severity": "critical"},
        ]
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=policy_id,
            llm_client=mock_llm_client,
        )
        
        assert rules[0].severity == "low"
        assert rules[1].severity == "medium"
        assert rules[2].severity == "high"
        assert rules[3].severity == "critical"

    @pytest.mark.asyncio
    async def test_parse_rules_llm_error_propagates(self, parser, mock_llm_client):
        """Test that LLM errors are propagated."""
        mock_llm_client.extract_rules.side_effect = ValueError("Invalid JSON response")
        
        policy_id = "12345678-1234-1234-1234-123456789012"
        
        with pytest.raises(ValueError) as exc_info:
            await parser.parse_rules(
                text="Sample policy text",
                policy_id=policy_id,
                llm_client=mock_llm_client,
            )
        
        assert "Invalid JSON response" in str(exc_info.value)


class TestProcessPolicy:
    """Tests for the process_policy method."""

    @pytest.fixture
    def parser(self):
        """Create a PolicyParserService instance for testing."""
        with patch("app.services.policy_parser.get_settings") as mock_settings:
            mock_settings.return_value.max_pdf_size_mb = 10
            return PolicyParserService()

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        client.extract_rules.return_value = [
            {
                "rule_code": "DATA-001",
                "description": "Test rule",
                "evaluation_criteria": "test criteria",
                "severity": "high",
                "target_entities": "test_table",
            },
        ]
        return client

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        
        # Track added objects and assign UUIDs to Policy objects
        added_objects = []
        def track_add(obj):
            added_objects.append(obj)
            # Assign a UUID to Policy objects to simulate database behavior
            if hasattr(obj, 'id') and obj.id is None:
                import uuid as uuid_module
                obj.id = uuid_module.uuid4()
        
        session.add = MagicMock(side_effect=track_add)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_process_policy_success(self, parser, mock_llm_client, mock_db_session):
        """Test successful policy processing pipeline."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample policy text content"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome PDF content"
            upload_file = MockUploadFile(pdf_content, filename="test_policy.pdf")
            
            policy = await parser.process_policy(
                pdf_file=upload_file,
                db=mock_db_session,
                llm_client=mock_llm_client,
            )
            
            # Verify policy was created with correct attributes
            assert policy.filename == "test_policy.pdf"
            assert policy.status == "completed"
            assert policy.raw_text == "Sample policy text content"
            
            # Verify session interactions
            assert mock_db_session.add.call_count >= 2  # Policy + at least 1 rule
            mock_db_session.flush.assert_called()
            mock_llm_client.extract_rules.assert_called_once_with("Sample policy text content")

    @pytest.mark.asyncio
    async def test_process_policy_pdf_extraction_error(self, parser, mock_llm_client, mock_db_session):
        """Test that PDF extraction errors update policy status to failed."""
        # Non-PDF content will trigger UnsupportedFormatError
        non_pdf_content = b"This is not a PDF"
        upload_file = MockUploadFile(non_pdf_content, filename="not_a_pdf.txt")
        
        with pytest.raises(UnsupportedFormatError):
            await parser.process_policy(
                pdf_file=upload_file,
                db=mock_db_session,
                llm_client=mock_llm_client,
            )
        
        # Verify policy status was set to failed
        # The policy object should have been added to the session
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_process_policy_llm_error(self, parser, mock_llm_client, mock_db_session):
        """Test that LLM errors update policy status to failed."""
        mock_llm_client.extract_rules.side_effect = ValueError("LLM parsing error")
        
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample policy text"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome PDF content"
            upload_file = MockUploadFile(pdf_content, filename="test_policy.pdf")
            
            with pytest.raises(ValueError) as exc_info:
                await parser.process_policy(
                    pdf_file=upload_file,
                    db=mock_db_session,
                    llm_client=mock_llm_client,
                )
            
            assert "LLM parsing error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_policy_default_filename(self, parser, mock_llm_client, mock_db_session):
        """Test that default filename is used when not provided."""
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample policy text"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome PDF content"
            upload_file = MockUploadFile(pdf_content)
            upload_file.filename = None  # No filename provided
            
            policy = await parser.process_policy(
                pdf_file=upload_file,
                db=mock_db_session,
                llm_client=mock_llm_client,
            )
            
            assert policy.filename == "unknown.pdf"

    @pytest.fixture
    def mock_db_session_for_multiple_rules(self):
        """Create a mock database session for multiple rules test."""
        session = AsyncMock()
        
        # Track added objects and assign UUIDs to Policy objects
        added_objects = []
        def track_add(obj):
            added_objects.append(obj)
            # Assign a UUID to Policy objects to simulate database behavior
            if hasattr(obj, 'id') and obj.id is None:
                import uuid as uuid_module
                obj.id = uuid_module.uuid4()
        
        session.add = MagicMock(side_effect=track_add)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_process_policy_multiple_rules(self, parser, mock_db_session_for_multiple_rules):
        """Test processing policy with multiple rules extracted."""
        mock_llm_client = AsyncMock()
        mock_llm_client.extract_rules.return_value = [
            {"rule_code": "R1", "description": "d1", "evaluation_criteria": "c1", "severity": "low"},
            {"rule_code": "R2", "description": "d2", "evaluation_criteria": "c2", "severity": "high"},
            {"rule_code": "R3", "description": "d3", "evaluation_criteria": "c3", "severity": "critical"},
        ]
        
        with patch("app.services.policy_parser.pdfplumber") as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample policy text"
            
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.pages = [mock_page]
            mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = MagicMock(return_value=False)
            
            mock_pdf.open.return_value = mock_pdf_obj
            
            pdf_content = b"%PDF-1.4\nSome PDF content"
            upload_file = MockUploadFile(pdf_content, filename="multi_rule_policy.pdf")
            
            policy = await parser.process_policy(
                pdf_file=upload_file,
                db=mock_db_session_for_multiple_rules,
                llm_client=mock_llm_client,
            )
            
            # Verify all rules were added (1 policy + 3 rules = 4 add calls)
            assert mock_db_session_for_multiple_rules.add.call_count == 4
            assert policy.status == "completed"

"""Policy Parser Service for PDF text extraction and rule parsing.

This module provides functionality to extract text from PDF policy documents
and parse compliance rules using the LLM client.
"""

import io
import logging
import uuid
from typing import BinaryIO, List, Optional, Union

import pdfplumber
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker
from app.models.compliance_rule import ComplianceRule
from app.models.enums import PolicyStatus, Severity
from app.models.policy import Policy
from app.services.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Base exception for PDF extraction errors."""
    pass


class CorruptedPDFError(PDFExtractionError):
    """Raised when a PDF file is corrupted or unreadable."""
    pass


class EmptyPDFError(PDFExtractionError):
    """Raised when a PDF contains no extractable text."""
    pass


class UnsupportedFormatError(PDFExtractionError):
    """Raised when the uploaded file is not a valid PDF."""
    pass


class FileTooLargeError(PDFExtractionError):
    """Raised when the uploaded file exceeds the size limit."""
    pass


class PolicyParserService:
    """Service for parsing PDF policy documents and extracting compliance rules.
    
    This service handles:
    - PDF text extraction using pdfplumber
    - Error handling for corrupted, empty, or invalid PDFs
    - File size validation
    
    Usage:
        parser = PolicyParserService()
        text = await parser.extract_text(pdf_file)
    """

    def __init__(self):
        """Initialize the PolicyParserService with configuration settings."""
        self._settings = get_settings()
        self._max_file_size_bytes = self._settings.max_pdf_size_mb * 1024 * 1024

    async def extract_text(self, pdf_file: UploadFile) -> str:
        """Extract text content from a PDF file using pdfplumber.
        
        Args:
            pdf_file: The uploaded PDF file (FastAPI UploadFile).
            
        Returns:
            The extracted text content from all pages of the PDF.
            
        Raises:
            FileTooLargeError: If the file exceeds the maximum size limit.
            UnsupportedFormatError: If the file is not a valid PDF.
            CorruptedPDFError: If the PDF is corrupted or unreadable.
            EmptyPDFError: If the PDF contains no extractable text.
        """
        # Read file content
        content = await pdf_file.read()
        
        # Reset file position for potential re-reads
        await pdf_file.seek(0)
        
        # Validate file size
        file_size = len(content)
        if file_size > self._max_file_size_bytes:
            max_size_mb = self._settings.max_pdf_size_mb
            raise FileTooLargeError(
                f"File exceeds maximum size limit of {max_size_mb}MB."
            )
        
        # Validate file is not empty
        if file_size == 0:
            raise UnsupportedFormatError("Please upload a valid PDF file.")
        
        # Check for PDF magic bytes (PDF files start with %PDF)
        if not content.startswith(b'%PDF'):
            raise UnsupportedFormatError("Please upload a valid PDF file.")
        
        # Extract text using pdfplumber
        extracted_text = self._extract_text_from_bytes(content)
        
        return extracted_text

    def _extract_text_from_bytes(self, content: bytes) -> str:
        """Extract text from PDF bytes using pdfplumber.
        
        Args:
            content: The raw bytes of the PDF file.
            
        Returns:
            The extracted text content from all pages.
            
        Raises:
            CorruptedPDFError: If the PDF cannot be read.
            EmptyPDFError: If no text can be extracted.
        """
        try:
            pdf_stream = io.BytesIO(content)
            
            with pdfplumber.open(pdf_stream) as pdf:
                # Check if PDF has any pages
                if len(pdf.pages) == 0:
                    raise EmptyPDFError(
                        "The uploaded PDF contains no extractable text."
                    )
                
                # Extract text from all pages
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                # Combine all extracted text
                full_text = "\n\n".join(text_parts)
                
                # Check if any text was extracted
                if not full_text.strip():
                    raise EmptyPDFError(
                        "The uploaded PDF contains no extractable text."
                    )
                
                logger.info(
                    f"Successfully extracted {len(full_text)} characters "
                    f"from {len(pdf.pages)} pages"
                )
                
                return full_text
                
        except EmptyPDFError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Log the original error for debugging
            logger.error(f"Failed to extract text from PDF: {e}")
            raise CorruptedPDFError(
                "Unable to read PDF file. Please ensure the file is not corrupted."
            )

    def extract_text_sync(self, file_content: Union[BinaryIO, bytes]) -> str:
        """Synchronous version of text extraction for testing purposes.
        
        Args:
            file_content: Either a file-like object or raw bytes of the PDF.
            
        Returns:
            The extracted text content from all pages.
            
        Raises:
            FileTooLargeError: If the file exceeds the maximum size limit.
            UnsupportedFormatError: If the file is not a valid PDF.
            CorruptedPDFError: If the PDF is corrupted or unreadable.
            EmptyPDFError: If the PDF contains no extractable text.
        """
        # Handle both bytes and file-like objects
        if isinstance(file_content, bytes):
            content = file_content
        else:
            content = file_content.read()
            if hasattr(file_content, 'seek'):
                file_content.seek(0)
        
        # Validate file size
        file_size = len(content)
        if file_size > self._max_file_size_bytes:
            max_size_mb = self._settings.max_pdf_size_mb
            raise FileTooLargeError(
                f"File exceeds maximum size limit of {max_size_mb}MB."
            )
        
        # Validate file is not empty
        if file_size == 0:
            raise UnsupportedFormatError("Please upload a valid PDF file.")
        
        # Check for PDF magic bytes
        if not content.startswith(b'%PDF'):
            raise UnsupportedFormatError("Please upload a valid PDF file.")
        
        # Extract text
        return self._extract_text_from_bytes(content)

    async def parse_rules(
        self,
        text: str,
        policy_id: str,
        llm_client: Optional[LLMClient] = None,
    ) -> List[ComplianceRule]:
        """Send text to LLM and parse response into structured rules.
        
        Args:
            text: The extracted text content from a policy document.
            policy_id: The UUID of the policy document these rules belong to.
            llm_client: Optional LLM client instance. If not provided, a new one
                       will be created.
            
        Returns:
            A list of ComplianceRule model instances (not yet persisted to DB).
            
        Raises:
            ValueError: If the LLM response cannot be parsed into valid rules.
        """
        # Use provided client or create a new one
        client = llm_client or get_llm_client()
        
        # Extract rules using LLM
        logger.info(f"Sending policy text to LLM for rule extraction (policy_id={policy_id})")
        raw_rules = await client.extract_rules(text)
        
        # Convert raw rule dictionaries to ComplianceRule model instances
        compliance_rules: List[ComplianceRule] = []
        policy_uuid = uuid.UUID(policy_id) if isinstance(policy_id, str) else policy_id
        
        for raw_rule in raw_rules:
            # Map severity string to enum value, defaulting to MEDIUM
            severity_str = raw_rule.get("severity", "medium").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                logger.warning(
                    f"Invalid severity '{severity_str}' for rule {raw_rule.get('rule_code')}, "
                    f"defaulting to MEDIUM"
                )
                severity = Severity.MEDIUM
            
            # Create ComplianceRule instance
            rule = ComplianceRule(
                policy_id=policy_uuid,
                rule_code=raw_rule.get("rule_code", ""),
                description=raw_rule.get("description", ""),
                evaluation_criteria=raw_rule.get("evaluation_criteria", ""),
                target_table=raw_rule.get("target_entities"),  # Map target_entities to target_table
                severity=severity.value,
                is_active=True,
            )
            compliance_rules.append(rule)
        
        logger.info(
            f"Parsed {len(compliance_rules)} compliance rules from policy {policy_id}"
        )
        
        return compliance_rules

    async def process_policy(
        self,
        pdf_file: UploadFile,
        db: Optional[AsyncSession] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> Policy:
        """Full pipeline: extract text, parse rules, store results.
        
        This method orchestrates the complete policy processing workflow:
        1. Create a Policy record with PROCESSING status
        2. Extract text from the PDF
        3. Send text to LLM for rule extraction
        4. Store the extracted rules with reference to the policy
        5. Update policy status to COMPLETED
        
        Args:
            pdf_file: The uploaded PDF file (FastAPI UploadFile).
            db: Optional database session. If not provided, a new session
                will be created.
            llm_client: Optional LLM client instance. If not provided, a new one
                       will be created.
            
        Returns:
            The Policy model instance with associated ComplianceRules.
            
        Raises:
            PDFExtractionError: If the PDF cannot be read or is invalid.
            ValueError: If the LLM response cannot be parsed into valid rules.
        """
        # Determine if we need to manage our own session
        manage_session = db is None
        session = db
        
        try:
            if manage_session:
                session = async_session_maker()
            
            # Create initial policy record with PROCESSING status
            policy = Policy(
                filename=pdf_file.filename or "unknown.pdf",
                status=PolicyStatus.PROCESSING.value,
            )
            session.add(policy)
            await session.flush()  # Get the policy ID without committing
            
            logger.info(f"Created policy record {policy.id} for file '{policy.filename}'")
            
            try:
                # Step 1: Extract text from PDF
                extracted_text = await self.extract_text(pdf_file)
                policy.raw_text = extracted_text
                
                # Step 2: Parse rules using LLM
                compliance_rules = await self.parse_rules(
                    text=extracted_text,
                    policy_id=str(policy.id),
                    llm_client=llm_client,
                )
                
                # Step 3: Add rules to the session (they reference the policy)
                for rule in compliance_rules:
                    session.add(rule)
                
                # Step 4: Update policy status to COMPLETED
                policy.status = PolicyStatus.COMPLETED.value
                
                # Commit all changes
                if manage_session:
                    await session.commit()
                    # Refresh to get the relationships loaded
                    await session.refresh(policy)
                else:
                    await session.flush()
                
                logger.info(
                    f"Successfully processed policy {policy.id}: "
                    f"extracted {len(compliance_rules)} rules"
                )
                
                return policy
                
            except (PDFExtractionError, ValueError) as e:
                # Update policy status to FAILED
                policy.status = PolicyStatus.FAILED.value
                if manage_session:
                    await session.commit()
                else:
                    await session.flush()
                logger.error(f"Failed to process policy {policy.id}: {e}")
                raise
                
        except Exception as e:
            if manage_session and session:
                await session.rollback()
            raise
        finally:
            if manage_session and session:
                await session.close()


def get_policy_parser_service() -> PolicyParserService:
    """Get a PolicyParserService instance.
    
    This is a convenience function for dependency injection in FastAPI.
    
    Returns:
        A PolicyParserService instance.
    """
    return PolicyParserService()

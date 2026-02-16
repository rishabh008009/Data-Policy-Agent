"""Policy management API routes.

This module provides FastAPI endpoints for managing policy documents:
- Upload PDF policy documents
- List all policies
- Get policy details with rules
- Delete policies
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance_rule import ComplianceRule
from app.models.enums import Severity
from app.models.policy import Policy
from app.services.policy_parser import (
    CorruptedPDFError,
    EmptyPDFError,
    FileTooLargeError,
    PolicyParserService,
    UnsupportedFormatError,
    get_policy_parser_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/policies", tags=["Policies"])


# Pydantic Response Models

class ComplianceRuleResponse(BaseModel):
    """Response model for a compliance rule."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    policy_id: UUID
    rule_code: str
    description: str
    evaluation_criteria: str
    target_table: Optional[str] = None
    severity: str
    is_active: bool
    created_at: datetime


class PolicyResponse(BaseModel):
    """Response model for a policy document."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    status: str
    uploaded_at: datetime
    rule_count: int


class PolicyDetailResponse(BaseModel):
    """Response model for policy details including rules."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    status: str
    uploaded_at: datetime
    raw_text: Optional[str] = None
    rules: List[ComplianceRuleResponse]


class PolicyUploadResponse(BaseModel):
    """Response model for policy upload result."""
    
    id: UUID
    filename: str
    status: str
    uploaded_at: datetime
    rule_count: int
    message: str


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


# API Endpoints

@router.post(
    "/upload",
    response_model=PolicyUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PDF file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Upload PDF policy document",
    description="Upload a PDF policy document for parsing. The system will extract text "
                "and use AI/LLM to identify compliance rules.",
)
async def upload_policy(
    file: UploadFile = File(..., description="PDF policy document to upload"),
    db: AsyncSession = Depends(get_db),
    parser: PolicyParserService = Depends(get_policy_parser_service),
) -> PolicyUploadResponse:
    """Upload and process a PDF policy document.
    
    This endpoint:
    1. Validates the uploaded file is a valid PDF
    2. Extracts text content from the PDF
    3. Uses AI/LLM to parse compliance rules from the text
    4. Stores the policy and extracted rules in the database
    
    Args:
        file: The PDF file to upload
        db: Database session (injected)
        parser: Policy parser service (injected)
        
    Returns:
        PolicyUploadResponse with the created policy details
        
    Raises:
        HTTPException: 400 for invalid PDF, 413 for file too large, 500 for server errors
    """
    # Validate content type - be lenient, rely on magic bytes check in parser
    logger.info(f"Upload attempt: filename={file.filename}, content_type={file.content_type}, size={file.size}")
    if file.content_type and file.content_type not in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        None,
    ):
        # Also allow if filename ends with .pdf
        if not (file.filename and file.filename.lower().endswith(".pdf")):
            logger.warning(f"Invalid content type: {file.content_type}, filename: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Please upload a valid PDF file. Received content type: {file.content_type}",
            )
    
    try:
        # Process the policy document
        policy = await parser.process_policy(pdf_file=file, db=db)
        
        # Get the rule count
        rule_count = len(policy.rules) if policy.rules else 0
        
        logger.info(
            f"Successfully uploaded policy '{policy.filename}' "
            f"with {rule_count} rules"
        )
        
        return PolicyUploadResponse(
            id=policy.id,
            filename=policy.filename,
            status=policy.status,
            uploaded_at=policy.uploaded_at,
            rule_count=rule_count,
            message=f"Successfully extracted {rule_count} compliance rules from the policy document.",
        )
        
    except FileTooLargeError as e:
        logger.warning(f"File too large: {e}")
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(e),
        )
    except UnsupportedFormatError as e:
        logger.warning(f"Unsupported format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CorruptedPDFError as e:
        logger.warning(f"Corrupted PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except EmptyPDFError as e:
        logger.warning(f"Empty PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error processing policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the policy document.",
        )


@router.get(
    "",
    response_model=List[PolicyResponse],
    summary="List all policies",
    description="Retrieve a list of all uploaded policy documents with their rule counts.",
)
async def list_policies(
    db: AsyncSession = Depends(get_db),
) -> List[PolicyResponse]:
    """List all policy documents.
    
    Args:
        db: Database session (injected)
        
    Returns:
        List of PolicyResponse objects
    """
    # Query all policies with their rules loaded
    result = await db.execute(
        select(Policy).options(selectinload(Policy.rules)).order_by(Policy.uploaded_at.desc())
    )
    policies = result.scalars().all()
    
    # Convert to response models with rule counts
    return [
        PolicyResponse(
            id=policy.id,
            filename=policy.filename,
            status=policy.status,
            uploaded_at=policy.uploaded_at,
            rule_count=len(policy.rules) if policy.rules else 0,
        )
        for policy in policies
    ]


@router.get(
    "/{policy_id}",
    response_model=PolicyDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Policy not found"},
    },
    summary="Get policy details",
    description="Retrieve detailed information about a specific policy including all extracted rules.",
)
async def get_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PolicyDetailResponse:
    """Get a specific policy with its rules.
    
    Args:
        policy_id: The UUID of the policy to retrieve
        db: Database session (injected)
        
    Returns:
        PolicyDetailResponse with full policy details and rules
        
    Raises:
        HTTPException: 404 if policy not found
    """
    # Query the policy with rules
    result = await db.execute(
        select(Policy)
        .options(selectinload(Policy.rules))
        .where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found.",
        )
    
    # Convert rules to response models
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
        for rule in (policy.rules or [])
    ]
    
    return PolicyDetailResponse(
        id=policy.id,
        filename=policy.filename,
        status=policy.status,
        uploaded_at=policy.uploaded_at,
        raw_text=policy.raw_text,
        rules=rules_response,
    )


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Policy not found"},
    },
    summary="Delete a policy",
    description="Remove a policy document and all its associated compliance rules.",
)
async def delete_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a policy and its associated rules.
    
    This will cascade delete all compliance rules associated with the policy.
    
    Args:
        policy_id: The UUID of the policy to delete
        db: Database session (injected)
        
    Raises:
        HTTPException: 404 if policy not found
    """
    # Query the policy
    result = await db.execute(
        select(Policy).where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found.",
        )
    
    # Delete the policy (cascade will delete associated rules)
    await db.delete(policy)
    
    logger.info(f"Deleted policy '{policy.filename}' (ID: {policy_id})")

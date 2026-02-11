"""Violations management API routes.

This module provides FastAPI endpoints for managing compliance violations:
- List violations with filtering (status, severity, rule, date range)
- Get violation details with associated rule information and review history
- Submit review decisions (confirm, mark_false_positive, resolve)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance_rule import ComplianceRule
from app.models.enums import ReviewActionType, Severity, ViolationStatus
from app.models.review_action import ReviewAction
from app.models.violation import Violation


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/violations", tags=["Violations"])


# Pydantic Models

class ReviewActionResponse(BaseModel):
    """Response model for a review action."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    violation_id: UUID
    action_type: str
    reviewer_id: str
    notes: Optional[str] = None
    created_at: datetime


class RuleInfoResponse(BaseModel):
    """Response model for rule information in violation context."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    rule_code: str
    description: str
    evaluation_criteria: str
    target_table: Optional[str] = None
    severity: str
    is_active: bool


class ViolationListResponse(BaseModel):
    """Response model for violation list items."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    rule_id: UUID
    rule_code: str
    rule_description: str
    record_identifier: str
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None


class ViolationDetailResponse(BaseModel):
    """Response model for detailed violation information."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    rule_id: UUID
    record_identifier: str
    record_data: Dict[str, Any]
    justification: str
    remediation_suggestion: Optional[str] = None
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    rule: RuleInfoResponse
    review_history: List[ReviewActionResponse]


class ViolationListPaginatedResponse(BaseModel):
    """Response model for paginated violation list."""
    
    items: List[ViolationListResponse]
    total: int
    skip: int
    limit: int


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


class ReviewDecisionRequest(BaseModel):
    """Request model for submitting a review decision."""
    
    action: str = Field(
        default=None,
        description="The review action to take: 'confirm', 'false_positive', or 'resolve'",
    )
    action_type: str = Field(
        default=None,
        description="Alternative field name for action (deprecated, use 'action')",
    )
    reviewer_id: str = Field(
        default="anonymous",
        min_length=1,
        max_length=255,
        description="Identifier for the reviewer submitting the decision",
    )
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional notes explaining the review decision",
    )
    
    @property
    def effective_action(self) -> str:
        """Get the effective action, preferring 'action' over 'action_type'."""
        return self.action or self.action_type or ""


class ViolationReviewResponse(BaseModel):
    """Response model for a violation after review."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    rule_id: UUID
    record_identifier: str
    record_data: Dict[str, Any]
    justification: str
    remediation_suggestion: Optional[str] = None
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    rule: RuleInfoResponse
    review_action: ReviewActionResponse


# API Endpoints

@router.get(
    "",
    response_model=ViolationListPaginatedResponse,
    summary="List violations with filtering",
    description="Retrieve a paginated list of violations with optional filters for status, "
                "severity, rule, and date range.",
)
async def list_violations(
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by violation status (pending, confirmed, false_positive, resolved)",
    ),
    severity: Optional[str] = Query(
        None,
        description="Filter by severity level (low, medium, high, critical)",
    ),
    rule_id: Optional[UUID] = Query(
        None,
        description="Filter by specific rule ID",
    ),
    start_date: Optional[datetime] = Query(
        None,
        description="Filter violations detected on or after this date",
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter violations detected on or before this date",
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
) -> ViolationListPaginatedResponse:
    """List violations with optional filtering and pagination.
    
    Args:
        db: Database session (injected)
        status_filter: Filter by violation status (optional)
        severity: Filter by severity level (optional)
        rule_id: Filter by specific rule ID (optional)
        start_date: Filter violations detected on or after this date (optional)
        end_date: Filter violations detected on or before this date (optional)
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        
    Returns:
        ViolationListPaginatedResponse with filtered violations and pagination info
    """
    # Validate status filter if provided
    if status_filter is not None:
        valid_statuses = [s.value for s in ViolationStatus]
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{status_filter}'. Valid values are: {', '.join(valid_statuses)}",
            )
    
    # Validate severity filter if provided
    if severity is not None:
        valid_severities = [s.value for s in Severity]
        if severity not in valid_severities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity '{severity}'. Valid values are: {', '.join(valid_severities)}",
            )
    
    # Build filter conditions
    conditions = []
    
    if status_filter is not None:
        conditions.append(Violation.status == status_filter)
    
    if severity is not None:
        conditions.append(Violation.severity == severity)
    
    if rule_id is not None:
        conditions.append(Violation.rule_id == rule_id)
    
    if start_date is not None:
        conditions.append(Violation.detected_at >= start_date)
    
    if end_date is not None:
        conditions.append(Violation.detected_at <= end_date)
    
    # Build base query with rule relationship for rule_code and description
    base_query = (
        select(Violation)
        .options(selectinload(Violation.rule))
        .order_by(Violation.detected_at.desc())
    )
    
    if conditions:
        base_query = base_query.where(and_(*conditions))
    
    # Get total count
    count_query = select(Violation)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    paginated_query = base_query.offset(skip).limit(limit)
    result = await db.execute(paginated_query)
    violations = result.scalars().all()
    
    # Build response items
    items = []
    for violation in violations:
        rule = violation.rule
        items.append(
            ViolationListResponse(
                id=violation.id,
                rule_id=violation.rule_id,
                rule_code=rule.rule_code if rule else "Unknown",
                rule_description=rule.description if rule else "Unknown rule",
                record_identifier=violation.record_identifier,
                severity=violation.severity,
                status=violation.status,
                detected_at=violation.detected_at,
                resolved_at=violation.resolved_at,
            )
        )
    
    logger.info(
        f"Listed {len(items)} violations (total: {total}, skip: {skip}, limit: {limit})"
    )
    
    return ViolationListPaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{violation_id}",
    response_model=ViolationDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Violation not found"},
    },
    summary="Get violation details",
    description="Retrieve detailed information about a specific violation including "
                "associated rule information and review history.",
)
async def get_violation(
    violation_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ViolationDetailResponse:
    """Get detailed information about a specific violation.
    
    Args:
        violation_id: The UUID of the violation to retrieve
        db: Database session (injected)
        
    Returns:
        ViolationDetailResponse with full violation details, rule info, and review history
        
    Raises:
        HTTPException: 404 if violation not found
    """
    # Query violation with rule and review actions
    result = await db.execute(
        select(Violation)
        .options(
            selectinload(Violation.rule),
            selectinload(Violation.review_actions),
        )
        .where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()
    
    if violation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation with ID '{violation_id}' not found.",
        )
    
    # Build rule info response
    rule = violation.rule
    rule_info = RuleInfoResponse(
        id=rule.id,
        rule_code=rule.rule_code,
        description=rule.description,
        evaluation_criteria=rule.evaluation_criteria,
        target_table=rule.target_table,
        severity=rule.severity,
        is_active=rule.is_active,
    )
    
    # Build review history response (sorted by created_at descending)
    review_history = sorted(
        [
            ReviewActionResponse(
                id=action.id,
                violation_id=action.violation_id,
                action_type=action.action_type,
                reviewer_id=action.reviewer_id,
                notes=action.notes,
                created_at=action.created_at,
            )
            for action in violation.review_actions
        ],
        key=lambda x: x.created_at,
        reverse=True,
    )
    
    logger.info(f"Retrieved violation details for ID: {violation_id}")
    
    return ViolationDetailResponse(
        id=violation.id,
        rule_id=violation.rule_id,
        record_identifier=violation.record_identifier,
        record_data=violation.record_data,
        justification=violation.justification,
        remediation_suggestion=violation.remediation_suggestion,
        severity=violation.severity,
        status=violation.status,
        detected_at=violation.detected_at,
        resolved_at=violation.resolved_at,
        rule=rule_info,
        review_history=review_history,
    )


# Mapping from action_type to ViolationStatus
ACTION_TO_STATUS_MAP = {
    ReviewActionType.CONFIRM.value: ViolationStatus.CONFIRMED.value,
    ReviewActionType.FALSE_POSITIVE.value: ViolationStatus.FALSE_POSITIVE.value,
    ReviewActionType.RESOLVE.value: ViolationStatus.RESOLVED.value,
    # Also support alternative naming conventions
    "confirm": ViolationStatus.CONFIRMED.value,
    "mark_false_positive": ViolationStatus.FALSE_POSITIVE.value,
    "resolve": ViolationStatus.RESOLVED.value,
}


@router.patch(
    "/{violation_id}/review",
    response_model=ViolationReviewResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid review action"},
        404: {"model": ErrorResponse, "description": "Violation not found"},
    },
    summary="Submit a review decision",
    description="Submit a review decision for a violation. Creates an audit entry and "
                "updates the violation status based on the action type.",
)
async def review_violation(
    violation_id: UUID,
    review_decision: ReviewDecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> ViolationReviewResponse:
    """Submit a review decision for a violation.
    
    This endpoint allows reviewers to:
    - Confirm a violation (status -> confirmed)
    - Mark as false positive (status -> false_positive)
    - Resolve a violation (status -> resolved, sets resolved_at timestamp)
    
    Each review action creates an audit entry in the ReviewAction table.
    
    Args:
        violation_id: The UUID of the violation to review
        review_decision: The review decision containing action_type, reviewer_id, and optional notes
        db: Database session (injected)
        
    Returns:
        ViolationReviewResponse with updated violation and the new review action
        
    Raises:
        HTTPException: 400 if invalid action_type, 404 if violation not found
    """
    # Validate action_type
    valid_actions = ["confirm", "false_positive", "mark_false_positive", "resolve"]
    action = review_decision.effective_action
    if action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{action}'. "
                   f"Valid values are: {', '.join(valid_actions)}",
        )
    
    # Query violation with rule relationship
    result = await db.execute(
        select(Violation)
        .options(selectinload(Violation.rule))
        .where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()
    
    if violation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation with ID '{violation_id}' not found.",
        )
    
    # Determine new status based on action
    # Normalize false_positive to mark_false_positive for the mapping
    normalized_action = "mark_false_positive" if action == "false_positive" else action
    new_status = ACTION_TO_STATUS_MAP[normalized_action]
    
    # Update violation status
    violation.status = new_status
    
    # Set resolved_at timestamp if resolving
    if action == "resolve":
        violation.resolved_at = datetime.now(timezone.utc)
    
    # Create ReviewAction audit entry
    review_action = ReviewAction(
        violation_id=violation_id,
        action_type=action,
        reviewer_id=review_decision.reviewer_id,
        notes=review_decision.notes,
    )
    db.add(review_action)
    
    # Commit changes
    await db.commit()
    await db.refresh(violation)
    await db.refresh(review_action)
    
    # Build rule info response
    rule = violation.rule
    rule_info = RuleInfoResponse(
        id=rule.id,
        rule_code=rule.rule_code,
        description=rule.description,
        evaluation_criteria=rule.evaluation_criteria,
        target_table=rule.target_table,
        severity=rule.severity,
        is_active=rule.is_active,
    )
    
    # Build review action response
    review_action_response = ReviewActionResponse(
        id=review_action.id,
        violation_id=review_action.violation_id,
        action_type=review_action.action_type,
        reviewer_id=review_action.reviewer_id,
        notes=review_action.notes,
        created_at=review_action.created_at,
    )
    
    logger.info(
        f"Reviewed violation {violation_id}: action={action}, "
        f"reviewer={review_decision.reviewer_id}, new_status={new_status}"
    )
    
    return ViolationReviewResponse(
        id=violation.id,
        rule_id=violation.rule_id,
        record_identifier=violation.record_identifier,
        record_data=violation.record_data,
        justification=violation.justification,
        remediation_suggestion=violation.remediation_suggestion,
        severity=violation.severity,
        status=violation.status,
        detected_at=violation.detected_at,
        resolved_at=violation.resolved_at,
        rule=rule_info,
        review_action=review_action_response,
    )

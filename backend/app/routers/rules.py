"""Compliance rules management API routes.

This module provides FastAPI endpoints for managing compliance rules:
- List all extracted rules
- Get rule details
- Enable/disable rules
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance_rule import ComplianceRule


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rules"])


# Pydantic Models

class RuleResponse(BaseModel):
    """Response model for a compliance rule."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    policy_id: UUID
    rule_code: str
    description: str
    evaluation_criteria: str
    target_table: Optional[str] = None
    generated_sql: Optional[str] = None
    severity: str
    is_active: bool
    created_at: datetime


class RuleUpdateRequest(BaseModel):
    """Request model for updating a rule."""
    
    is_active: Optional[bool] = Field(None, description="Enable or disable the rule")


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


# API Endpoints

@router.get(
    "",
    response_model=List[RuleResponse],
    summary="List all compliance rules",
    description="Retrieve a list of all extracted compliance rules across all policies.",
)
async def list_rules(
    db: AsyncSession = Depends(get_db),
    is_active: Optional[bool] = None,
    severity: Optional[str] = None,
    policy_id: Optional[UUID] = None,
) -> List[RuleResponse]:
    """List all compliance rules with optional filtering.
    
    Args:
        db: Database session (injected)
        is_active: Filter by active status (optional)
        severity: Filter by severity level (optional)
        policy_id: Filter by policy ID (optional)
        
    Returns:
        List of RuleResponse objects
    """
    # Build query with optional filters
    query = select(ComplianceRule).order_by(ComplianceRule.created_at.desc())
    
    if is_active is not None:
        query = query.where(ComplianceRule.is_active == is_active)
    
    if severity is not None:
        query = query.where(ComplianceRule.severity == severity)
    
    if policy_id is not None:
        query = query.where(ComplianceRule.policy_id == policy_id)
    
    result = await db.execute(query)
    rules = result.scalars().all()
    
    return [
        RuleResponse(
            id=rule.id,
            policy_id=rule.policy_id,
            rule_code=rule.rule_code,
            description=rule.description,
            evaluation_criteria=rule.evaluation_criteria,
            target_table=rule.target_table,
            generated_sql=rule.generated_sql,
            severity=rule.severity,
            is_active=rule.is_active,
            created_at=rule.created_at,
        )
        for rule in rules
    ]


@router.get(
    "/{rule_id}",
    response_model=RuleResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Rule not found"},
    },
    summary="Get rule details",
    description="Retrieve detailed information about a specific compliance rule.",
)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    """Get a specific compliance rule by ID.
    
    Args:
        rule_id: The UUID of the rule to retrieve
        db: Database session (injected)
        
    Returns:
        RuleResponse with full rule details
        
    Raises:
        HTTPException: 404 if rule not found
    """
    result = await db.execute(
        select(ComplianceRule).where(ComplianceRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID '{rule_id}' not found.",
        )
    
    return RuleResponse(
        id=rule.id,
        policy_id=rule.policy_id,
        rule_code=rule.rule_code,
        description=rule.description,
        evaluation_criteria=rule.evaluation_criteria,
        target_table=rule.target_table,
        generated_sql=rule.generated_sql,
        severity=rule.severity,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


@router.patch(
    "/{rule_id}",
    response_model=RuleResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Rule not found"},
    },
    summary="Update a rule",
    description="Update a compliance rule. Currently supports enabling/disabling rules.",
)
async def update_rule(
    rule_id: UUID,
    update_data: RuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    """Update a compliance rule (enable/disable).
    
    Args:
        rule_id: The UUID of the rule to update
        update_data: The update data containing fields to modify
        db: Database session (injected)
        
    Returns:
        RuleResponse with updated rule details
        
    Raises:
        HTTPException: 404 if rule not found
    """
    result = await db.execute(
        select(ComplianceRule).where(ComplianceRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID '{rule_id}' not found.",
        )
    
    # Update fields if provided
    if update_data.is_active is not None:
        rule.is_active = update_data.is_active
        logger.info(
            f"Rule '{rule.rule_code}' (ID: {rule_id}) "
            f"{'enabled' if update_data.is_active else 'disabled'}"
        )
    
    # The session will be committed by the get_db dependency
    await db.flush()
    await db.refresh(rule)
    
    return RuleResponse(
        id=rule.id,
        policy_id=rule.policy_id,
        rule_code=rule.rule_code,
        description=rule.description,
        evaluation_criteria=rule.evaluation_criteria,
        target_table=rule.target_table,
        generated_sql=rule.generated_sql,
        severity=rule.severity,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )

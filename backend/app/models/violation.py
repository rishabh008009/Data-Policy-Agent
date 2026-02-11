"""Violation model for storing detected compliance violations."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Severity, ViolationStatus

if TYPE_CHECKING:
    from app.models.compliance_rule import ComplianceRule
    from app.models.review_action import ReviewAction


class Violation(Base):
    """SQLAlchemy model for compliance violations.
    
    Stores detected violations with justifications and remediation suggestions.
    Each violation is linked to a compliance rule and can have review actions.
    """
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    record_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    justification: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    remediation_suggestion: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default=Severity.MEDIUM.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ViolationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    rule: Mapped["ComplianceRule"] = relationship(
        "ComplianceRule",
        back_populates="violations",
    )
    review_actions: Mapped[List["ReviewAction"]] = relationship(
        "ReviewAction",
        back_populates="violation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Violation(id={self.id}, record_identifier='{self.record_identifier}', status='{self.status}')>"

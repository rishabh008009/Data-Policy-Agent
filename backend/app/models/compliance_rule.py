"""ComplianceRule model for storing extracted compliance rules."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Severity

if TYPE_CHECKING:
    from app.models.policy import Policy
    from app.models.violation import Violation


class ComplianceRule(Base):
    """SQLAlchemy model for compliance rules.
    
    Stores rules extracted from policy documents by the LLM.
    Each rule defines evaluation criteria and can trigger violations.
    """
    __tablename__ = "compliance_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    evaluation_criteria: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_table: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    generated_sql: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default=Severity.MEDIUM.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    policy: Mapped["Policy"] = relationship(
        "Policy",
        back_populates="rules",
    )
    violations: Mapped[List["Violation"]] = relationship(
        "Violation",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ComplianceRule(id={self.id}, rule_code='{self.rule_code}', severity='{self.severity}')>"

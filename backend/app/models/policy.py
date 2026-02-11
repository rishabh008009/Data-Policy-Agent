"""Policy model for storing uploaded policy documents."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PolicyStatus

if TYPE_CHECKING:
    from app.models.compliance_rule import ComplianceRule


class Policy(Base):
    """SQLAlchemy model for policy documents.
    
    Stores uploaded PDF policy documents and their extracted text content.
    Each policy can have multiple associated compliance rules.
    """
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=PolicyStatus.PENDING.value,
        nullable=False,
    )

    # Relationships
    rules: Mapped[List["ComplianceRule"]] = relationship(
        "ComplianceRule",
        back_populates="policy",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, filename='{self.filename}', status='{self.status}')>"

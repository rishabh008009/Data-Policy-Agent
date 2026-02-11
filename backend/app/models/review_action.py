"""ReviewAction model for storing human review decisions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.violation import Violation


class ReviewAction(Base):
    """SQLAlchemy model for review actions.
    
    Stores audit log of human review decisions on violations.
    Each action records the reviewer, action type, and optional notes.
    """
    __tablename__ = "review_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    violation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("violations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    violation: Mapped["Violation"] = relationship(
        "Violation",
        back_populates="review_actions",
    )

    def __repr__(self) -> str:
        return f"<ReviewAction(id={self.id}, action_type='{self.action_type}', reviewer_id='{self.reviewer_id}')>"

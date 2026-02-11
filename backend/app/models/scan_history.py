"""ScanHistory model for storing compliance scan execution history."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ScanStatus


class ScanHistory(Base):
    """SQLAlchemy model for scan history.
    
    Stores records of compliance scan executions including
    timing, results, and any error messages.
    """
    __tablename__ = "scan_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ScanStatus.RUNNING.value,
        nullable=False,
    )
    violations_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    new_violations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ScanHistory(id={self.id}, status='{self.status}', violations_found={self.violations_found})>"

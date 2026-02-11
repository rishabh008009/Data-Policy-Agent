"""MonitoringConfig model for storing scheduled scan configuration."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MonitoringConfig(Base):
    """SQLAlchemy model for monitoring configuration.
    
    Stores the configuration for scheduled compliance scans
    including interval, enabled status, and timing information.
    """
    __tablename__ = "monitoring_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    interval_minutes: Mapped[int] = mapped_column(
        Integer,
        default=360,  # 6 hours default
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<MonitoringConfig(id={self.id}, interval_minutes={self.interval_minutes}, is_enabled={self.is_enabled})>"

"""DatabaseConnection model for storing target database connection configurations."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DatabaseConnection(Base):
    """SQLAlchemy model for database connections.
    
    Stores connection configurations for target PostgreSQL databases
    that will be scanned for compliance violations.
    """
    __tablename__ = "database_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=5432,
        nullable=False,
    )
    database_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    encrypted_password: Mapped[str] = mapped_column(
        Text,
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

    def __repr__(self) -> str:
        return f"<DatabaseConnection(id={self.id}, host='{self.host}', database='{self.database_name}')>"

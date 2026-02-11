"""Enum definitions for the Data Policy Agent models."""

from enum import Enum


class ViolationStatus(str, Enum):
    """Status of a compliance violation."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class Severity(str, Enum):
    """Severity level for compliance rules and violations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyStatus(str, Enum):
    """Status of a policy document processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanStatus(str, Enum):
    """Status of a compliance scan."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewActionType(str, Enum):
    """Type of review action taken on a violation."""
    CONFIRM = "confirm"
    FALSE_POSITIVE = "false_positive"
    RESOLVE = "resolve"

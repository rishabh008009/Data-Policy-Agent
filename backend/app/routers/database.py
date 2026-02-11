"""Database connection and scanning API routes.

This module provides FastAPI endpoints for managing database connections:
- Test and save database connection credentials
- Retrieve target database schema
- Trigger manual compliance scans
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance_rule import ComplianceRule
from app.models.database_connection import DatabaseConnection
from app.models.enums import ScanStatus, Severity
from app.models.scan_history import ScanHistory
from app.services.db_scanner import (
    AuthenticationError,
    ColumnInfo,
    ConnectionTimeoutError,
    DatabaseConnectionError,
    DatabaseNotFoundError,
    DatabaseSchema,
    DatabaseScannerService,
    DBConnectionConfig,
    HostUnreachableError,
    SSLError,
    TableInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/database", tags=["Database"])


# Singleton scanner service instance
_scanner_service: Optional[DatabaseScannerService] = None


def get_scanner_service() -> DatabaseScannerService:
    """Get or create the database scanner service singleton."""
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = DatabaseScannerService()
    return _scanner_service


# Pydantic Request/Response Models

class DatabaseConnectRequest(BaseModel):
    """Request model for database connection."""
    
    host: str = Field(..., description="Database server hostname or IP address")
    port: int = Field(default=5432, ge=1, le=65535, description="Database server port")
    database: str = Field(..., description="Name of the database to connect to")
    username: str = Field(..., description="Database user for authentication")
    password: str = Field(..., description="Password for authentication")
    ssl: bool = Field(default=False, description="Whether to use SSL/TLS connection")


class DatabaseConnectResponse(BaseModel):
    """Response model for successful database connection."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    host: str
    port: int
    database_name: str
    username: str
    is_active: bool
    created_at: datetime
    message: str


class ColumnInfoResponse(BaseModel):
    """Response model for column information."""
    
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    default_value: Optional[str] = None


class TableInfoResponse(BaseModel):
    """Response model for table information."""
    
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    schema_name: str
    columns: List[ColumnInfoResponse]
    row_count: Optional[int] = None


class DatabaseSchemaResponse(BaseModel):
    """Response model for database schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    database_name: str
    tables: List[TableInfoResponse]
    version: Optional[str] = None


class ErrorResponse(BaseModel):
    """Response model for error messages."""
    
    detail: str


class ScanRequest(BaseModel):
    """Request model for triggering a compliance scan.
    
    All fields are optional - if not provided, the scan will use
    all active rules and the currently connected database.
    """
    
    rule_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Optional list of specific rule IDs to scan. If not provided, all active rules are used."
    )


class ViolationCountBySeverity(BaseModel):
    """Violation counts grouped by severity level."""
    
    low: int = Field(default=0, description="Count of low severity violations")
    medium: int = Field(default=0, description="Count of medium severity violations")
    high: int = Field(default=0, description="Count of high severity violations")
    critical: int = Field(default=0, description="Count of critical severity violations")


class ScanResponse(BaseModel):
    """Response model for compliance scan results."""
    
    model_config = ConfigDict(from_attributes=True)
    
    scan_id: UUID = Field(..., description="Unique identifier for this scan")
    started_at: datetime = Field(..., description="When the scan started")
    completed_at: datetime = Field(..., description="When the scan completed")
    status: str = Field(..., description="Scan status (completed, failed)")
    total_violations: int = Field(..., description="Total number of violations found")
    new_violations: int = Field(..., description="Number of new violations (not previously detected)")
    violations_by_severity: ViolationCountBySeverity = Field(
        ..., description="Violation counts grouped by severity"
    )
    rules_evaluated: int = Field(..., description="Number of rules that were evaluated")
    message: str = Field(..., description="Human-readable summary of the scan results")


# API Endpoints

@router.post(
    "/connect",
    response_model=DatabaseConnectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid connection parameters"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Database not found"},
        408: {"model": ErrorResponse, "description": "Connection timeout"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Test and save database connection",
    description="Test connection to a PostgreSQL database and save the connection "
                "configuration if successful.",
)
async def connect_database(
    request: DatabaseConnectRequest,
    db: AsyncSession = Depends(get_db),
    scanner: DatabaseScannerService = Depends(get_scanner_service),
) -> DatabaseConnectResponse:
    """Test and save a database connection.
    
    This endpoint:
    1. Validates the connection parameters
    2. Attempts to connect to the target PostgreSQL database
    3. If successful, saves the connection configuration to the database
    4. Returns the saved connection details
    
    Args:
        request: The database connection parameters
        db: Application database session (injected)
        scanner: Database scanner service (injected)
        
    Returns:
        DatabaseConnectResponse with the saved connection details
        
    Raises:
        HTTPException: Various status codes for different connection errors
    """
    # Create connection config from request
    connection_config = DBConnectionConfig(
        host=request.host,
        port=request.port,
        database=request.database,
        username=request.username,
        password=request.password,
        ssl=request.ssl,
    )
    
    try:
        # Test the connection
        logger.info(
            f"Testing connection to database '{request.database}' "
            f"at {request.host}:{request.port}"
        )
        
        await scanner.connect(connection_config)
        
        # Connection successful - save to database
        # First, deactivate any existing active connections
        existing_result = await db.execute(
            select(DatabaseConnection).where(DatabaseConnection.is_active == True)
        )
        existing_connections = existing_result.scalars().all()
        for existing in existing_connections:
            existing.is_active = False
        
        # Create new connection record
        # Note: In production, password should be properly encrypted
        # For hackathon demo, we store it as-is (not recommended for production)
        db_connection = DatabaseConnection(
            host=request.host,
            port=request.port,
            database_name=request.database,
            username=request.username,
            encrypted_password=request.password,  # TODO: Encrypt in production
            is_active=True,
        )
        
        db.add(db_connection)
        await db.flush()
        await db.refresh(db_connection)
        
        logger.info(
            f"Successfully connected and saved connection to database "
            f"'{request.database}' (ID: {db_connection.id})"
        )
        
        return DatabaseConnectResponse(
            id=db_connection.id,
            host=db_connection.host,
            port=db_connection.port,
            database_name=db_connection.database_name,
            username=db_connection.username,
            is_active=db_connection.is_active,
            created_at=db_connection.created_at,
            message=f"Successfully connected to database '{request.database}'.",
        )
        
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
        
    except DatabaseNotFoundError as e:
        logger.warning(f"Database not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
        
    except ConnectionTimeoutError as e:
        logger.warning(f"Connection timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=str(e),
        )
        
    except HostUnreachableError as e:
        logger.warning(f"Host unreachable: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except SSLError as e:
        logger.warning(f"SSL error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
        
    except Exception as e:
        logger.error(f"Unexpected error connecting to database: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while connecting to the database.",
        )


@router.get(
    "/schema",
    response_model=DatabaseSchemaResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Not connected to a database"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get target database schema",
    description="Retrieve the schema (tables, columns, data types) from the connected "
                "target database.",
)
async def get_database_schema(
    scanner: DatabaseScannerService = Depends(get_scanner_service),
) -> DatabaseSchemaResponse:
    """Retrieve the schema from the connected database.
    
    This endpoint returns the complete schema of the target database including:
    - All tables in user schemas (excluding system schemas)
    - Column names, data types, and constraints for each table
    - Estimated row counts for each table
    
    Args:
        scanner: Database scanner service (injected)
        
    Returns:
        DatabaseSchemaResponse with the complete database schema
        
    Raises:
        HTTPException: 400 if not connected, 500 for server errors
    """
    try:
        # Check if connected
        if not scanner.is_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not connected to a database. Please connect first using POST /api/database/connect.",
            )
        
        # Retrieve schema
        logger.info("Retrieving database schema")
        schema = await scanner.get_schema()
        
        # Convert to response model
        tables_response = [
            TableInfoResponse(
                name=table.name,
                schema_name=table.schema_name,
                columns=[
                    ColumnInfoResponse(
                        name=col.name,
                        data_type=col.data_type,
                        is_nullable=col.is_nullable,
                        is_primary_key=col.is_primary_key,
                        default_value=col.default_value,
                    )
                    for col in table.columns
                ],
                row_count=table.row_count,
            )
            for table in schema.tables
        ]
        
        logger.info(f"Retrieved schema with {len(tables_response)} tables")
        
        return DatabaseSchemaResponse(
            database_name=schema.database_name,
            tables=tables_response,
            version=schema.version,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except Exception as e:
        logger.error(f"Unexpected error retrieving schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the database schema.",
        )


@router.post(
    "/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Not connected to a database or no active rules"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Trigger manual compliance scan",
    description="Trigger a manual compliance scan against the connected database. "
                "Evaluates all active compliance rules and returns violation counts.",
)
async def trigger_scan(
    request: Optional[ScanRequest] = None,
    db: AsyncSession = Depends(get_db),
    scanner: DatabaseScannerService = Depends(get_scanner_service),
) -> ScanResponse:
    """Trigger a manual compliance scan.
    
    This endpoint:
    1. Fetches all active compliance rules from the database
    2. Executes scan_for_violations() to detect violations
    3. Creates a ScanHistory record to track the scan
    4. Returns scan results with violation counts by severity
    
    Args:
        request: Optional scan request with specific rule IDs to scan
        db: Application database session (injected)
        scanner: Database scanner service (injected)
        
    Returns:
        ScanResponse with scan results and violation counts
        
    Raises:
        HTTPException: 400 if not connected or no rules, 500 for server errors
    """
    # Check if connected to target database
    if not scanner.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not connected to a database. Please connect first using POST /api/database/connect.",
        )
    
    # Create scan history record
    scan_history = ScanHistory(
        status=ScanStatus.RUNNING.value,
        violations_found=0,
        new_violations=0,
    )
    db.add(scan_history)
    await db.flush()
    await db.refresh(scan_history)
    
    scan_id = scan_history.id
    started_at = scan_history.started_at
    
    logger.info(f"Starting compliance scan (ID: {scan_id})")
    
    try:
        # Fetch compliance rules
        if request and request.rule_ids:
            # Fetch specific rules by ID
            rules_result = await db.execute(
                select(ComplianceRule).where(
                    ComplianceRule.id.in_(request.rule_ids),
                    ComplianceRule.is_active == True
                )
            )
        else:
            # Fetch all active rules
            rules_result = await db.execute(
                select(ComplianceRule).where(ComplianceRule.is_active == True)
            )
        
        rules = list(rules_result.scalars().all())
        
        if not rules:
            # Update scan history with no rules found
            scan_history.status = ScanStatus.COMPLETED.value
            scan_history.completed_at = datetime.now(timezone.utc)
            await db.commit()
            
            logger.warning("No active compliance rules found for scan")
            
            return ScanResponse(
                scan_id=scan_id,
                started_at=started_at,
                completed_at=scan_history.completed_at,
                status=ScanStatus.COMPLETED.value,
                total_violations=0,
                new_violations=0,
                violations_by_severity=ViolationCountBySeverity(),
                rules_evaluated=0,
                message="No active compliance rules found. Please add rules before scanning.",
            )
        
        logger.info(f"Found {len(rules)} active rules to evaluate")
        
        # Execute the scan
        violations = await scanner.scan_for_violations(
            rules=rules,
            db_session=db,
            llm_client=None,  # Will use default LLM client
        )
        
        # Count violations by severity
        severity_counts: Dict[str, int] = {
            Severity.LOW.value: 0,
            Severity.MEDIUM.value: 0,
            Severity.HIGH.value: 0,
            Severity.CRITICAL.value: 0,
        }
        
        for violation in violations:
            severity = violation.severity
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Update scan history
        completed_at = datetime.now(timezone.utc)
        scan_history.status = ScanStatus.COMPLETED.value
        scan_history.completed_at = completed_at
        scan_history.violations_found = len(violations)
        scan_history.new_violations = len(violations)  # All violations are new in manual scan
        
        await db.commit()
        
        logger.info(
            f"Scan completed (ID: {scan_id}): found {len(violations)} violations"
        )
        
        # Build response
        violations_by_severity = ViolationCountBySeverity(
            low=severity_counts[Severity.LOW.value],
            medium=severity_counts[Severity.MEDIUM.value],
            high=severity_counts[Severity.HIGH.value],
            critical=severity_counts[Severity.CRITICAL.value],
        )
        
        # Generate summary message
        if len(violations) == 0:
            message = f"Scan completed successfully. No violations found across {len(rules)} rules."
        else:
            message = (
                f"Scan completed. Found {len(violations)} violation(s) across {len(rules)} rules. "
                f"Critical: {severity_counts[Severity.CRITICAL.value]}, "
                f"High: {severity_counts[Severity.HIGH.value]}, "
                f"Medium: {severity_counts[Severity.MEDIUM.value]}, "
                f"Low: {severity_counts[Severity.LOW.value]}."
            )
        
        return ScanResponse(
            scan_id=scan_id,
            started_at=started_at,
            completed_at=completed_at,
            status=ScanStatus.COMPLETED.value,
            total_violations=len(violations),
            new_violations=len(violations),
            violations_by_severity=violations_by_severity,
            rules_evaluated=len(rules),
            message=message,
        )
        
    except DatabaseConnectionError as e:
        # Update scan history with failure
        scan_history.status = ScanStatus.FAILED.value
        scan_history.completed_at = datetime.now(timezone.utc)
        scan_history.error_message = str(e)
        await db.commit()
        
        logger.error(f"Scan failed due to database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database connection error during scan: {e}",
        )
        
    except Exception as e:
        # Update scan history with failure
        scan_history.status = ScanStatus.FAILED.value
        scan_history.completed_at = datetime.now(timezone.utc)
        scan_history.error_message = str(e)
        await db.commit()
        
        logger.error(f"Unexpected error during scan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the compliance scan.",
        )

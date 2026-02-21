"""Database Scanner Service for connecting to and scanning PostgreSQL databases.

This module provides functionality to connect to target PostgreSQL databases,
retrieve schema information, generate SQL queries for compliance rules,
and scan for compliance violations.
"""

import logging
import re
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.compliance_rule import ComplianceRule
    from app.models.violation import Violation
    from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


# Pydantic Models for Database Scanner

class DBConnectionConfig(BaseModel):
    """Configuration for connecting to a target PostgreSQL database.
    
    Attributes:
        host: Database server hostname or IP address.
        port: Database server port (default: 5432).
        database: Name of the database to connect to.
        username: Database user for authentication.
        password: Password for authentication.
        ssl: Whether to use SSL/TLS for the connection (default: False).
    """
    host: str = Field(..., description="Database server hostname or IP address")
    port: int = Field(default=5432, ge=1, le=65535, description="Database server port")
    database: str = Field(..., description="Name of the database to connect to")
    username: str = Field(..., description="Database user for authentication")
    password: str = Field(..., description="Password for authentication")
    ssl: bool = Field(default=False, description="Whether to use SSL/TLS connection")


class ColumnInfo(BaseModel):
    """Information about a database column.
    
    Attributes:
        name: Column name.
        data_type: PostgreSQL data type of the column.
        is_nullable: Whether the column allows NULL values.
        is_primary_key: Whether the column is part of the primary key.
        default_value: Default value for the column, if any.
    """
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="PostgreSQL data type")
    is_nullable: bool = Field(default=True, description="Whether column allows NULL")
    is_primary_key: bool = Field(default=False, description="Whether column is primary key")
    default_value: Optional[str] = Field(default=None, description="Default value if any")


class TableInfo(BaseModel):
    """Information about a database table.
    
    Attributes:
        name: Table name.
        schema_name: Schema name (default: 'public').
        columns: List of columns in the table.
        row_count: Estimated number of rows (optional).
    """
    name: str = Field(..., description="Table name")
    schema_name: str = Field(default="public", description="Schema name")
    columns: list[ColumnInfo] = Field(default_factory=list, description="Table columns")
    row_count: Optional[int] = Field(default=None, description="Estimated row count")


class DatabaseSchema(BaseModel):
    """Complete schema information for a database.
    
    Attributes:
        database_name: Name of the database.
        tables: List of tables in the database.
        version: PostgreSQL server version.
    """
    database_name: str = Field(..., description="Database name")
    tables: list[TableInfo] = Field(default_factory=list, description="Database tables")
    version: Optional[str] = Field(default=None, description="PostgreSQL version")


# Custom Exceptions for Database Connection Errors

class DatabaseConnectionError(Exception):
    """Base exception for database connection errors."""
    pass


class AuthenticationError(DatabaseConnectionError):
    """Raised when database authentication fails."""
    def __init__(self, message: str = "Authentication failed. Please check username and password."):
        super().__init__(message)


class HostUnreachableError(DatabaseConnectionError):
    """Raised when the database host cannot be reached."""
    def __init__(self, message: str = "Unable to connect to database host. Please verify the hostname and port."):
        super().__init__(message)


class DatabaseNotFoundError(DatabaseConnectionError):
    """Raised when the specified database does not exist."""
    def __init__(self, database_name: str):
        message = f"Database '{database_name}' not found on the server."
        super().__init__(message)
        self.database_name = database_name


class ConnectionTimeoutError(DatabaseConnectionError):
    """Raised when the connection times out."""
    def __init__(self, message: str = "Connection timed out. Please try again."):
        super().__init__(message)


class SSLError(DatabaseConnectionError):
    """Raised when SSL/TLS connection fails."""
    def __init__(self, message: str = "Secure connection failed. Please check SSL configuration."):
        super().__init__(message)


class SQLGenerationError(Exception):
    """Raised when SQL query generation fails for a compliance rule.
    
    This exception indicates that a rule cannot be translated to a valid SQL query
    and should be flagged for human review.
    """
    def __init__(self, rule_code: str, reason: str):
        message = f"Failed to generate SQL for rule '{rule_code}': {reason}"
        super().__init__(message)
        self.rule_code = rule_code
        self.reason = reason
        self.needs_human_review = True


class DatabaseScannerService:
    """Service for connecting to and scanning PostgreSQL databases.
    
    This service handles:
    - Establishing connections to target PostgreSQL databases
    - Retrieving database schema information (tables, columns, types)
    - Error handling with diagnostic messages
    
    Usage:
        scanner = DatabaseScannerService()
        connected = await scanner.connect(config)
        if connected:
            schema = await scanner.get_schema()
    """

    def __init__(self):
        """Initialize the DatabaseScannerService."""
        self._connection: Optional[asyncpg.Connection] = None
        self._config: Optional[DBConnectionConfig] = None

    @property
    def is_connected(self) -> bool:
        """Check if there is an active database connection."""
        return self._connection is not None and not self._connection.is_closed()

    async def connect(self, connection_config: DBConnectionConfig) -> bool:
        """Establish connection to target PostgreSQL database.
        
        Args:
            connection_config: Configuration containing connection details.
            
        Returns:
            True if connection was successful.
            
        Raises:
            AuthenticationError: If username/password is invalid.
            HostUnreachableError: If the database host cannot be reached.
            DatabaseNotFoundError: If the specified database doesn't exist.
            ConnectionTimeoutError: If the connection times out.
            SSLError: If SSL/TLS connection fails.
        """
        # Close any existing connection
        await self.disconnect()
        
        self._config = connection_config
        
        try:
            # Build connection parameters
            ssl_context = "require" if connection_config.ssl else False
            
            logger.info(
                f"Attempting to connect to PostgreSQL database "
                f"'{connection_config.database}' at {connection_config.host}:{connection_config.port}"
            )
            
            # Establish connection with timeout
            self._connection = await asyncpg.connect(
                host=connection_config.host,
                port=connection_config.port,
                database=connection_config.database,
                user=connection_config.username,
                password=connection_config.password,
                ssl=ssl_context,
                timeout=30,  # 30 second connection timeout
            )
            
            logger.info(
                f"Successfully connected to database '{connection_config.database}'"
            )
            return True
            
        except asyncpg.InvalidPasswordError:
            logger.error("Database authentication failed: invalid password")
            raise AuthenticationError()
            
        except asyncpg.InvalidAuthorizationSpecificationError:
            logger.error("Database authentication failed: invalid authorization")
            raise AuthenticationError()
            
        except asyncpg.InvalidCatalogNameError:
            logger.error(f"Database '{connection_config.database}' not found")
            raise DatabaseNotFoundError(connection_config.database)
            
        except asyncpg.PostgresConnectionError as e:
            error_msg = str(e).lower()
            if "ssl" in error_msg or "tls" in error_msg:
                logger.error(f"SSL/TLS connection error: {e}")
                raise SSLError()
            else:
                logger.error(f"PostgreSQL connection error: {e}")
                raise HostUnreachableError()
                
        except TimeoutError:
            logger.error("Database connection timed out")
            raise ConnectionTimeoutError()
            
        except OSError as e:
            # OSError covers network-related errors like connection refused
            error_msg = str(e).lower()
            if "timed out" in error_msg or "timeout" in error_msg:
                logger.error(f"Connection timeout: {e}")
                raise ConnectionTimeoutError()
            else:
                logger.error(f"Network error connecting to database: {e}")
                raise HostUnreachableError()
                
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error connecting to database: {e}")
            raise DatabaseConnectionError(f"Failed to connect to database: {e}")

    async def disconnect(self) -> None:
        """Close the database connection if open."""
        if self._connection is not None and not self._connection.is_closed():
            await self._connection.close()
            logger.info("Database connection closed")
        self._connection = None

    async def get_schema(self) -> DatabaseSchema:
        """Retrieve table and column metadata from target database.
        
        Returns:
            DatabaseSchema containing all tables and their columns.
            
        Raises:
            DatabaseConnectionError: If not connected to a database.
        """
        if not self.is_connected or self._config is None:
            raise DatabaseConnectionError("Not connected to a database. Call connect() first.")
        
        logger.info(f"Retrieving schema for database '{self._config.database}'")
        
        # Get PostgreSQL version
        version_result = await self._connection.fetchval("SELECT version()")
        
        # Query to get all tables in the public schema (and other user schemas)
        tables_query = """
            SELECT 
                t.table_schema,
                t.table_name,
                (SELECT reltuples::bigint 
                 FROM pg_class c 
                 JOIN pg_namespace n ON n.oid = c.relnamespace 
                 WHERE c.relname = t.table_name 
                 AND n.nspname = t.table_schema) as estimated_rows
            FROM information_schema.tables t
            WHERE t.table_type = 'BASE TABLE'
            AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY t.table_schema, t.table_name
        """
        
        tables_result = await self._connection.fetch(tables_query)
        
        tables: list[TableInfo] = []
        
        for table_row in tables_result:
            schema_name = table_row['table_schema']
            table_name = table_row['table_name']
            estimated_rows = table_row['estimated_rows']
            
            # Get columns for this table
            columns_query = """
                SELECT 
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name, kcu.table_name, kcu.table_schema
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) pk ON pk.column_name = c.column_name 
                    AND pk.table_name = c.table_name 
                    AND pk.table_schema = c.table_schema
                WHERE c.table_schema = $1 AND c.table_name = $2
                ORDER BY c.ordinal_position
            """
            
            columns_result = await self._connection.fetch(
                columns_query, schema_name, table_name
            )
            
            columns: list[ColumnInfo] = []
            for col_row in columns_result:
                column = ColumnInfo(
                    name=col_row['column_name'],
                    data_type=col_row['data_type'],
                    is_nullable=col_row['is_nullable'] == 'YES',
                    is_primary_key=col_row['is_primary_key'],
                    default_value=col_row['column_default'],
                )
                columns.append(column)
            
            table_info = TableInfo(
                name=table_name,
                schema_name=schema_name,
                columns=columns,
                row_count=int(estimated_rows) if estimated_rows is not None else None,
            )
            tables.append(table_info)
        
        schema = DatabaseSchema(
            database_name=self._config.database,
            tables=tables,
            version=version_result,
        )
        
        logger.info(
            f"Retrieved schema with {len(tables)} tables from database '{self._config.database}'"
        )
        
        return schema

    def schema_to_dict(self, schema: DatabaseSchema) -> dict[str, Any]:
        """Convert DatabaseSchema to a dictionary format suitable for LLM prompts.
        
        Args:
            schema: The database schema to convert.
            
        Returns:
            A dictionary representation of the schema.
        """
        return {
            "database_name": schema.database_name,
            "tables": [
                {
                    "name": table.name,
                    "schema": table.schema_name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "nullable": col.is_nullable,
                            "primary_key": col.is_primary_key,
                        }
                        for col in table.columns
                    ]
                }
                for table in schema.tables
            ]
        }

    def _validate_sql_syntax(self, sql: str) -> tuple[bool, str]:
        """Perform basic SQL syntax validation.
        
        This performs basic validation to catch obvious syntax errors before
        attempting to execute the query. It does NOT guarantee the SQL is valid
        PostgreSQL - that can only be determined by the database.
        
        Args:
            sql: The SQL query string to validate.
            
        Returns:
            A tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query"
        
        sql_upper = sql.upper().strip()
        
        # Must be a SELECT query (we don't allow INSERT, UPDATE, DELETE, etc.)
        if not sql_upper.startswith("SELECT"):
            return False, "Query must be a SELECT statement"
        
        # Check for dangerous operations that shouldn't be in a compliance query
        dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", 
                            "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE"]
        for keyword in dangerous_keywords:
            # Check for keyword as a standalone word (not part of column name)
            pattern = rf'\b{keyword}\b'
            if re.search(pattern, sql_upper):
                return False, f"Query contains forbidden keyword: {keyword}"
        
        # Basic structure validation - must have FROM clause
        if "FROM" not in sql_upper:
            return False, "Query must have a FROM clause"
        
        # Check for balanced parentheses
        open_parens = sql.count("(")
        close_parens = sql.count(")")
        if open_parens != close_parens:
            return False, "Unbalanced parentheses in query"
        
        # Check for balanced quotes (single quotes for strings)
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            return False, "Unbalanced single quotes in query"
        
        return True, ""

    async def generate_query(
        self, 
        rule: "ComplianceRule", 
        schema: DatabaseSchema,
        llm_client: Optional["LLMClient"] = None
    ) -> str:
        """Use LLM to generate SQL query for rule evaluation.
        
        This method generates a SQL query that identifies records violating
        the given compliance rule. The generated SQL is validated for basic
        syntax correctness before being returned.
        
        Args:
            rule: The compliance rule to generate a query for.
            schema: The database schema to use for query generation.
            llm_client: Optional LLM client instance. If not provided,
                       a new instance will be created.
            
        Returns:
            The generated SQL query string.
            
        Raises:
            SQLGenerationError: If the query cannot be generated or fails
                               validation. The rule should be flagged for
                               human review.
        """
        from app.services.llm_client import LLMClient, get_llm_client
        
        rule_code = rule.rule_code
        
        logger.info(f"Generating SQL query for rule '{rule_code}'")
        
        # Validate rule has required fields
        if not rule.evaluation_criteria or not rule.evaluation_criteria.strip():
            logger.warning(f"Rule '{rule_code}' has no evaluation criteria")
            raise SQLGenerationError(
                rule_code, 
                "Rule has no evaluation criteria defined"
            )
        
        # Get or create LLM client
        if llm_client is None:
            try:
                llm_client = get_llm_client()
            except ValueError as e:
                logger.error(f"Failed to create LLM client: {e}")
                raise SQLGenerationError(rule_code, f"LLM client unavailable: {e}")
        
        # Prepare rule data for LLM
        rule_dict = {
            "rule_code": rule.rule_code,
            "description": rule.description,
            "evaluation_criteria": rule.evaluation_criteria,
            "target_table": rule.target_table,
        }
        
        # Convert schema to dict format for LLM
        schema_dict = self.schema_to_dict(schema)
        
        try:
            # Generate SQL using LLM
            generated_sql = await llm_client.generate_sql(rule_dict, schema_dict)
            
            if not generated_sql:
                logger.warning(f"LLM returned empty SQL for rule '{rule_code}'")
                raise SQLGenerationError(rule_code, "LLM returned empty response")
            
            # Validate the generated SQL
            is_valid, error_message = self._validate_sql_syntax(generated_sql)
            
            if not is_valid:
                logger.warning(
                    f"Generated SQL for rule '{rule_code}' failed validation: {error_message}"
                )
                raise SQLGenerationError(rule_code, f"SQL validation failed: {error_message}")
            
            logger.info(f"Successfully generated SQL for rule '{rule_code}'")
            
            # Store the generated SQL in the rule (caller should persist this)
            rule.generated_sql = generated_sql
            
            return generated_sql
            
        except SQLGenerationError:
            # Re-raise SQLGenerationError as-is
            raise
        except Exception as e:
            # Wrap any other exceptions in SQLGenerationError
            logger.error(f"Error generating SQL for rule '{rule_code}': {e}")
            raise SQLGenerationError(rule_code, str(e))

    async def scan_for_violations(
        self,
        rules: list["ComplianceRule"],
        db_session: AsyncSession,
        llm_client: Optional["LLMClient"] = None,
    ) -> list["Violation"]:
        """Execute queries for each active rule and collect violations.
        
        This method scans the target database for compliance violations by:
        1. Filtering to only active rules
        2. Generating SQL queries for rules that don't have one
        3. Executing each query against the target database
        4. Creating Violation records for each violating record found
        5. Generating justifications and remediation suggestions using LLM
        
        Args:
            rules: List of compliance rules to evaluate.
            db_session: SQLAlchemy async session for persisting violations.
            llm_client: Optional LLM client instance. If not provided,
                       a new instance will be created.
            
        Returns:
            List of Violation objects that were created and persisted.
            
        Raises:
            DatabaseConnectionError: If not connected to a database.
        """
        from app.models.violation import Violation
        from app.models.enums import ViolationStatus
        from app.services.llm_client import get_llm_client
        
        if not self.is_connected:
            raise DatabaseConnectionError("Not connected to a database. Call connect() first.")
        
        # Get or create LLM client
        if llm_client is None:
            try:
                llm_client = get_llm_client()
            except ValueError as e:
                logger.error(f"Failed to create LLM client: {e}")
                llm_client = None
        
        # Get database schema for query generation
        schema = await self.get_schema()
        
        violations: list[Violation] = []
        
        # Filter to only active rules
        active_rules = [rule for rule in rules if rule.is_active]
        
        logger.info(f"Scanning {len(active_rules)} active rules for violations")
        
        MAX_VIOLATIONS_PER_RULE = 50  # Limit to avoid overwhelming the system
        
        for rule in active_rules:
            try:
                # Generate SQL if not already present
                sql_query = rule.generated_sql
                if not sql_query:
                    try:
                        sql_query = await self.generate_query(rule, schema, llm_client)
                    except SQLGenerationError as e:
                        logger.warning(f"Skipping rule '{rule.rule_code}': {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"Skipping rule '{rule.rule_code}' (SQL gen failed): {e}")
                        continue
                
                # Execute the query against the target database
                logger.info(f"Executing query for rule '{rule.rule_code}'")
                
                try:
                    records = await self._connection.fetch(sql_query)
                except Exception as e:
                    logger.error(f"Query execution failed for rule '{rule.rule_code}': {e}")
                    continue
                
                logger.info(f"Found {len(records)} potential violations for rule '{rule.rule_code}'")
                
                # Limit violations per rule
                capped_records = records[:MAX_VIOLATIONS_PER_RULE]
                
                # Create violations for each violating record (no LLM calls for speed)
                for record in capped_records:
                    record_data = dict(record)
                    record_identifier = self._get_record_identifier(record_data)
                    
                    # Use template-based justification (fast, no LLM)
                    justification = (
                        f"Record violates rule '{rule.rule_code}': {rule.description}. "
                        f"Evaluation criteria: {rule.evaluation_criteria}"
                    )
                    remediation = f"Review record '{record_identifier}' and ensure compliance with rule '{rule.rule_code}'."
                    
                    violation = Violation(
                        rule_id=rule.id,
                        record_identifier=record_identifier,
                        record_data=record_data,
                        justification=justification,
                        remediation_suggestion=remediation,
                        severity=rule.severity,
                        status=ViolationStatus.PENDING.value,
                    )
                    
                    db_session.add(violation)
                    violations.append(violation)
                    
            except Exception as e:
                logger.error(f"Error processing rule '{rule.rule_code}': {e}")
                continue
        
        # Commit all violations to the database
        if violations:
            await db_session.commit()
            logger.info(f"Created {len(violations)} violations")
        
        return violations

    def _get_record_identifier(self, record_data: dict[str, Any]) -> str:
        """Extract a unique identifier from a record.
        
        Attempts to find a suitable identifier in the following order:
        1. 'id' field
        2. Any field ending with '_id'
        3. First field in the record
        
        Args:
            record_data: Dictionary containing the record's data.
            
        Returns:
            A string identifier for the record.
        """
        # Try 'id' field first
        if 'id' in record_data:
            return str(record_data['id'])
        
        # Try any field ending with '_id'
        for key, value in record_data.items():
            if key.endswith('_id'):
                return str(value)
        
        # Fall back to first field
        if record_data:
            first_key = next(iter(record_data))
            return str(record_data[first_key])
        
        return "unknown"

    async def generate_justification(
        self,
        rule: "ComplianceRule",
        record_data: dict[str, Any],
        llm_client: Optional["LLMClient"] = None,
    ) -> str:
        """Generate human-readable explanation for why a record violates a rule.
        
        Uses the LLM to generate a clear, concise explanation suitable for
        compliance review. The explanation references specific field values
        and explains what the expected condition should be.
        
        Args:
            rule: The compliance rule that was violated.
            record_data: Dictionary containing the violating record's data.
            llm_client: Optional LLM client instance. If not provided,
                       a new instance will be created.
            
        Returns:
            A human-readable justification string explaining the violation.
            If LLM is unavailable, returns a default message.
        """
        from app.services.llm_client import get_llm_client
        
        # Get or create LLM client
        if llm_client is None:
            try:
                llm_client = get_llm_client()
            except ValueError as e:
                logger.warning(f"LLM client unavailable for justification: {e}")
                return f"Record violates rule '{rule.rule_code}': {rule.description}"
        
        # Prepare rule data for LLM
        rule_dict = {
            "description": rule.description,
            "evaluation_criteria": rule.evaluation_criteria,
        }
        
        try:
            justification = await llm_client.explain_violation(rule_dict, record_data)
            return justification if justification else f"Record violates rule '{rule.rule_code}': {rule.description}"
        except Exception as e:
            logger.error(f"Error generating justification: {e}")
            return f"Record violates rule '{rule.rule_code}': {rule.description}"

    async def generate_remediation(
        self,
        rule: "ComplianceRule",
        record_data: dict[str, Any],
        justification: str,
        llm_client: Optional["LLMClient"] = None,
    ) -> Optional[str]:
        """Generate remediation suggestion for a violation.
        
        Uses the LLM to generate specific, actionable steps to resolve
        the compliance violation. If the LLM cannot generate a suggestion,
        returns None to indicate manual review is required.
        
        Args:
            rule: The compliance rule that was violated.
            record_data: Dictionary containing the violating record's data.
            justification: The explanation of why the record violates the rule.
            llm_client: Optional LLM client instance. If not provided,
                       a new instance will be created.
            
        Returns:
            Actionable remediation steps, or None if manual review is required.
        """
        from app.services.llm_client import get_llm_client
        
        # Get or create LLM client
        if llm_client is None:
            try:
                llm_client = get_llm_client()
            except ValueError as e:
                logger.warning(f"LLM client unavailable for remediation: {e}")
                return None  # Manual review required
        
        # Prepare violation data for LLM
        violation_dict = {
            "rule_description": rule.description,
            "justification": justification,
            "record_data": record_data,
        }
        
        try:
            remediation = await llm_client.suggest_remediation(violation_dict)
            return remediation if remediation else None
        except Exception as e:
            logger.error(f"Error generating remediation: {e}")
            return None  # Manual review required

    async def __aenter__(self) -> "DatabaseScannerService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures connection is closed."""
        await self.disconnect()


def get_database_scanner_service() -> DatabaseScannerService:
    """Get a DatabaseScannerService instance.
    
    This is a convenience function for dependency injection in FastAPI.
    
    Returns:
        A DatabaseScannerService instance.
    """
    return DatabaseScannerService()

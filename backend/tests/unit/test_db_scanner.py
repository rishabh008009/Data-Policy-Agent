"""Unit tests for the Database Scanner Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.db_scanner import (
    DatabaseScannerService,
    DBConnectionConfig,
    DatabaseSchema,
    TableInfo,
    ColumnInfo,
    AuthenticationError,
    HostUnreachableError,
    DatabaseNotFoundError,
    ConnectionTimeoutError,
    SSLError,
    DatabaseConnectionError,
    get_database_scanner_service,
)


class TestDBConnectionConfig:
    """Tests for the DBConnectionConfig Pydantic model."""

    def test_valid_config_with_defaults(self):
        """Test creating a config with default values."""
        config = DBConnectionConfig(
            host="localhost",
            database="testdb",
            username="user",
            password="pass"
        )
        
        assert config.host == "localhost"
        assert config.port == 5432  # default
        assert config.database == "testdb"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.ssl is False  # default

    def test_valid_config_with_custom_port(self):
        """Test creating a config with custom port."""
        config = DBConnectionConfig(
            host="localhost",
            port=5433,
            database="testdb",
            username="user",
            password="pass"
        )
        
        assert config.port == 5433

    def test_valid_config_with_ssl(self):
        """Test creating a config with SSL enabled."""
        config = DBConnectionConfig(
            host="localhost",
            database="testdb",
            username="user",
            password="pass",
            ssl=True
        )
        
        assert config.ssl is True

    def test_invalid_port_too_low(self):
        """Test that port validation rejects values below 1."""
        with pytest.raises(ValueError):
            DBConnectionConfig(
                host="localhost",
                port=0,
                database="testdb",
                username="user",
                password="pass"
            )

    def test_invalid_port_too_high(self):
        """Test that port validation rejects values above 65535."""
        with pytest.raises(ValueError):
            DBConnectionConfig(
                host="localhost",
                port=70000,
                database="testdb",
                username="user",
                password="pass"
            )


class TestDatabaseSchema:
    """Tests for the DatabaseSchema Pydantic model."""

    def test_empty_schema(self):
        """Test creating an empty schema."""
        schema = DatabaseSchema(database_name="testdb")
        
        assert schema.database_name == "testdb"
        assert schema.tables == []
        assert schema.version is None

    def test_schema_with_tables(self):
        """Test creating a schema with tables."""
        columns = [
            ColumnInfo(name="id", data_type="integer", is_primary_key=True),
            ColumnInfo(name="name", data_type="varchar", is_nullable=True),
        ]
        tables = [
            TableInfo(name="users", columns=columns, row_count=100)
        ]
        schema = DatabaseSchema(
            database_name="testdb",
            tables=tables,
            version="PostgreSQL 15.0"
        )
        
        assert schema.database_name == "testdb"
        assert len(schema.tables) == 1
        assert schema.tables[0].name == "users"
        assert len(schema.tables[0].columns) == 2
        assert schema.version == "PostgreSQL 15.0"


class TestDatabaseScannerService:
    """Tests for the DatabaseScannerService class."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def valid_config(self):
        """Create a valid connection config for testing."""
        return DBConnectionConfig(
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass"
        )

    def test_initial_state(self, scanner):
        """Test that scanner starts with no connection."""
        assert scanner.is_connected is False
        assert scanner._connection is None
        assert scanner._config is None

    @pytest.mark.asyncio
    async def test_connect_success(self, scanner, valid_config):
        """Test successful database connection."""
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            result = await scanner.connect(valid_config)
            
            assert result is True
            assert scanner.is_connected is True
            mock_connect.assert_called_once_with(
                host="localhost",
                port=5432,
                database="testdb",
                user="user",
                password="pass",
                ssl=False,
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_connect_with_ssl(self, scanner):
        """Test connection with SSL enabled."""
        config = DBConnectionConfig(
            host="localhost",
            database="testdb",
            username="user",
            password="pass",
            ssl=True
        )
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            await scanner.connect(config)
            
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["ssl"] == "require"

    @pytest.mark.asyncio
    async def test_connect_invalid_password(self, scanner, valid_config):
        """Test that invalid password raises AuthenticationError."""
        import asyncpg
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncpg.InvalidPasswordError("Invalid password")
            
            with pytest.raises(AuthenticationError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "Authentication failed" in str(exc_info.value)
            assert "username and password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_invalid_authorization(self, scanner, valid_config):
        """Test that invalid authorization raises AuthenticationError."""
        import asyncpg
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncpg.InvalidAuthorizationSpecificationError("Invalid auth")
            
            with pytest.raises(AuthenticationError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_database_not_found(self, scanner, valid_config):
        """Test that missing database raises DatabaseNotFoundError."""
        import asyncpg
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncpg.InvalidCatalogNameError("Database not found")
            
            with pytest.raises(DatabaseNotFoundError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "testdb" in str(exc_info.value)
            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_host_unreachable(self, scanner, valid_config):
        """Test that unreachable host raises HostUnreachableError."""
        import asyncpg
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncpg.PostgresConnectionError("Connection refused")
            
            with pytest.raises(HostUnreachableError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "Unable to connect" in str(exc_info.value)
            assert "hostname and port" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_ssl_error(self, scanner, valid_config):
        """Test that SSL errors raise SSLError."""
        import asyncpg
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncpg.PostgresConnectionError("SSL connection failed")
            
            with pytest.raises(SSLError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "Secure connection failed" in str(exc_info.value)
            assert "SSL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_timeout(self, scanner, valid_config):
        """Test that timeout raises ConnectionTimeoutError."""
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = TimeoutError("Connection timed out")
            
            with pytest.raises(ConnectionTimeoutError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_os_error_timeout(self, scanner, valid_config):
        """Test that OS timeout error raises ConnectionTimeoutError."""
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = OSError("Connection timed out")
            
            with pytest.raises(ConnectionTimeoutError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_os_error_network(self, scanner, valid_config):
        """Test that OS network error raises HostUnreachableError."""
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = OSError("Network is unreachable")
            
            with pytest.raises(HostUnreachableError) as exc_info:
                await scanner.connect(valid_config)
            
            assert "Unable to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, scanner, valid_config):
        """Test disconnecting from database."""
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.close = AsyncMock()
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            await scanner.connect(valid_config)
            assert scanner.is_connected is True
            
            await scanner.disconnect()
            
            mock_connection.close.assert_called_once()
            assert scanner._connection is None

    @pytest.mark.asyncio
    async def test_reconnect_closes_existing(self, scanner, valid_config):
        """Test that reconnecting closes existing connection first."""
        mock_connection1 = MagicMock()
        mock_connection1.is_closed.return_value = False
        mock_connection1.close = AsyncMock()
        
        mock_connection2 = MagicMock()
        mock_connection2.is_closed.return_value = False
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = [mock_connection1, mock_connection2]
            
            await scanner.connect(valid_config)
            await scanner.connect(valid_config)
            
            mock_connection1.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_schema_not_connected(self, scanner):
        """Test that get_schema raises error when not connected."""
        with pytest.raises(DatabaseConnectionError) as exc_info:
            await scanner.get_schema()
        
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_schema_success(self, scanner, valid_config):
        """Test successful schema retrieval."""
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.close = AsyncMock()
        
        # Mock version query
        mock_connection.fetchval = AsyncMock(return_value="PostgreSQL 15.0")
        
        # Mock tables query
        tables_result = [
            {"table_schema": "public", "table_name": "users", "estimated_rows": 100}
        ]
        
        # Mock columns query
        columns_result = [
            {
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": "NO",
                "column_default": None,
                "is_primary_key": True
            },
            {
                "column_name": "name",
                "data_type": "character varying",
                "is_nullable": "YES",
                "column_default": None,
                "is_primary_key": False
            }
        ]
        
        mock_connection.fetch = AsyncMock(side_effect=[tables_result, columns_result])
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            await scanner.connect(valid_config)
            schema = await scanner.get_schema()
            
            assert schema.database_name == "testdb"
            assert schema.version == "PostgreSQL 15.0"
            assert len(schema.tables) == 1
            assert schema.tables[0].name == "users"
            assert schema.tables[0].schema_name == "public"
            assert len(schema.tables[0].columns) == 2
            
            # Check column details
            id_col = schema.tables[0].columns[0]
            assert id_col.name == "id"
            assert id_col.data_type == "integer"
            assert id_col.is_nullable is False
            assert id_col.is_primary_key is True
            
            name_col = schema.tables[0].columns[1]
            assert name_col.name == "name"
            assert name_col.data_type == "character varying"
            assert name_col.is_nullable is True
            assert name_col.is_primary_key is False

    @pytest.mark.asyncio
    async def test_get_schema_multiple_tables(self, scanner, valid_config):
        """Test schema retrieval with multiple tables."""
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.close = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value="PostgreSQL 15.0")
        
        tables_result = [
            {"table_schema": "public", "table_name": "users", "estimated_rows": 100},
            {"table_schema": "public", "table_name": "orders", "estimated_rows": 500}
        ]
        
        users_columns = [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO", 
             "column_default": None, "is_primary_key": True}
        ]
        orders_columns = [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO",
             "column_default": None, "is_primary_key": True},
            {"column_name": "user_id", "data_type": "integer", "is_nullable": "NO",
             "column_default": None, "is_primary_key": False}
        ]
        
        mock_connection.fetch = AsyncMock(
            side_effect=[tables_result, users_columns, orders_columns]
        )
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            await scanner.connect(valid_config)
            schema = await scanner.get_schema()
            
            assert len(schema.tables) == 2
            assert schema.tables[0].name == "users"
            assert schema.tables[1].name == "orders"
            assert len(schema.tables[1].columns) == 2

    def test_schema_to_dict(self, scanner):
        """Test converting schema to dictionary format."""
        columns = [
            ColumnInfo(name="id", data_type="integer", is_primary_key=True, is_nullable=False),
            ColumnInfo(name="name", data_type="varchar", is_nullable=True),
        ]
        tables = [TableInfo(name="users", schema_name="public", columns=columns)]
        schema = DatabaseSchema(database_name="testdb", tables=tables)
        
        result = scanner.schema_to_dict(schema)
        
        assert result["database_name"] == "testdb"
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"
        assert result["tables"][0]["schema"] == "public"
        assert len(result["tables"][0]["columns"]) == 2
        assert result["tables"][0]["columns"][0]["name"] == "id"
        assert result["tables"][0]["columns"][0]["type"] == "integer"
        assert result["tables"][0]["columns"][0]["primary_key"] is True

    @pytest.mark.asyncio
    async def test_context_manager(self, valid_config):
        """Test using scanner as async context manager."""
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.close = AsyncMock()
        
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection
            
            async with DatabaseScannerService() as scanner:
                await scanner.connect(valid_config)
                assert scanner.is_connected is True
            
            # Connection should be closed after exiting context
            mock_connection.close.assert_called_once()


class TestGetDatabaseScannerService:
    """Tests for the get_database_scanner_service factory function."""

    def test_returns_scanner_instance(self):
        """Test that factory returns a DatabaseScannerService instance."""
        scanner = get_database_scanner_service()
        
        assert isinstance(scanner, DatabaseScannerService)
        assert scanner.is_connected is False


class TestSQLValidation:
    """Tests for the _validate_sql_syntax method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    def test_valid_select_query(self, scanner):
        """Test that a valid SELECT query passes validation."""
        sql = "SELECT id, name FROM users WHERE status = 'active'"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is True
        assert error == ""

    def test_valid_select_with_join(self, scanner):
        """Test that a SELECT with JOIN passes validation."""
        sql = """
            SELECT u.id, u.name, o.total 
            FROM users u 
            JOIN orders o ON u.id = o.user_id 
            WHERE o.total > 100
        """
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is True
        assert error == ""

    def test_valid_select_with_subquery(self, scanner):
        """Test that a SELECT with subquery passes validation."""
        sql = """
            SELECT * FROM users 
            WHERE id IN (SELECT user_id FROM orders WHERE total > 100)
        """
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is True
        assert error == ""

    def test_empty_query_fails(self, scanner):
        """Test that empty query fails validation."""
        is_valid, error = scanner._validate_sql_syntax("")
        
        assert is_valid is False
        assert "Empty SQL query" in error

    def test_whitespace_only_fails(self, scanner):
        """Test that whitespace-only query fails validation."""
        is_valid, error = scanner._validate_sql_syntax("   \n\t  ")
        
        assert is_valid is False
        assert "Empty SQL query" in error

    def test_non_select_fails(self, scanner):
        """Test that non-SELECT queries fail validation."""
        is_valid, error = scanner._validate_sql_syntax("UPDATE users SET name = 'test'")
        
        assert is_valid is False
        assert "SELECT statement" in error

    def test_insert_keyword_fails(self, scanner):
        """Test that INSERT keyword fails validation."""
        sql = "SELECT * FROM users; INSERT INTO users VALUES (1, 'test')"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "INSERT" in error

    def test_delete_keyword_fails(self, scanner):
        """Test that DELETE keyword fails validation."""
        sql = "SELECT * FROM users; DELETE FROM users"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "DELETE" in error

    def test_drop_keyword_fails(self, scanner):
        """Test that DROP keyword fails validation."""
        sql = "SELECT * FROM users; DROP TABLE users"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "DROP" in error

    def test_truncate_keyword_fails(self, scanner):
        """Test that TRUNCATE keyword fails validation."""
        sql = "SELECT * FROM users; TRUNCATE TABLE users"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "TRUNCATE" in error

    def test_missing_from_clause_fails(self, scanner):
        """Test that query without FROM clause fails validation."""
        sql = "SELECT 1 + 1"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "FROM clause" in error

    def test_unbalanced_parentheses_fails(self, scanner):
        """Test that unbalanced parentheses fail validation."""
        sql = "SELECT * FROM users WHERE (status = 'active'"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "parentheses" in error

    def test_unbalanced_quotes_fails(self, scanner):
        """Test that unbalanced quotes fail validation."""
        sql = "SELECT * FROM users WHERE name = 'test"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is False
        assert "quotes" in error

    def test_case_insensitive_select(self, scanner):
        """Test that lowercase SELECT is accepted."""
        sql = "select id from users"
        is_valid, error = scanner._validate_sql_syntax(sql)
        
        assert is_valid is True
        assert error == ""


class TestGenerateQuery:
    """Tests for the generate_query method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule for testing."""
        rule = MagicMock()
        rule.rule_code = "DATA-001"
        rule.description = "Personal data must be encrypted"
        rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        rule.target_table = "users"
        rule.generated_sql = None
        return rule

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        columns = [
            ColumnInfo(name="id", data_type="integer", is_primary_key=True),
            ColumnInfo(name="email", data_type="varchar", is_nullable=False),
            ColumnInfo(name="is_encrypted", data_type="boolean", is_nullable=False),
        ]
        tables = [TableInfo(name="users", schema_name="public", columns=columns)]
        return DatabaseSchema(database_name="testdb", tables=tables)

    @pytest.mark.asyncio
    async def test_generate_query_success(self, scanner, mock_rule, sample_schema):
        """Test successful SQL query generation."""
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(
            return_value="SELECT id, email FROM users WHERE is_encrypted = false"
        )
        
        result = await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert result == "SELECT id, email FROM users WHERE is_encrypted = false"
        assert mock_rule.generated_sql == result
        mock_llm.generate_sql.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_query_stores_sql_in_rule(self, scanner, mock_rule, sample_schema):
        """Test that generated SQL is stored in the rule object."""
        expected_sql = "SELECT * FROM users WHERE is_encrypted = false"
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(return_value=expected_sql)
        
        await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert mock_rule.generated_sql == expected_sql

    @pytest.mark.asyncio
    async def test_generate_query_empty_criteria_fails(self, scanner, sample_schema):
        """Test that rule with empty evaluation criteria raises error."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_rule = MagicMock()
        mock_rule.rule_code = "DATA-001"
        mock_rule.evaluation_criteria = ""
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema)
        
        assert "no evaluation criteria" in str(exc_info.value)
        assert exc_info.value.needs_human_review is True

    @pytest.mark.asyncio
    async def test_generate_query_whitespace_criteria_fails(self, scanner, sample_schema):
        """Test that rule with whitespace-only criteria raises error."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_rule = MagicMock()
        mock_rule.rule_code = "DATA-001"
        mock_rule.evaluation_criteria = "   \n\t  "
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema)
        
        assert "no evaluation criteria" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_query_llm_returns_empty(self, scanner, mock_rule, sample_schema):
        """Test that empty LLM response raises error."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(return_value="")
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert "empty response" in str(exc_info.value)
        assert exc_info.value.needs_human_review is True

    @pytest.mark.asyncio
    async def test_generate_query_invalid_sql_fails(self, scanner, mock_rule, sample_schema):
        """Test that invalid SQL from LLM raises error."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_llm = AsyncMock()
        # Return SQL with unbalanced parentheses
        mock_llm.generate_sql = AsyncMock(
            return_value="SELECT * FROM users WHERE (status = 'active'"
        )
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert "validation failed" in str(exc_info.value)
        assert exc_info.value.needs_human_review is True

    @pytest.mark.asyncio
    async def test_generate_query_dangerous_sql_fails(self, scanner, mock_rule, sample_schema):
        """Test that SQL with dangerous keywords raises error."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(
            return_value="SELECT * FROM users; DROP TABLE users"
        )
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert "DROP" in str(exc_info.value)
        assert exc_info.value.needs_human_review is True

    @pytest.mark.asyncio
    async def test_generate_query_llm_exception(self, scanner, mock_rule, sample_schema):
        """Test that LLM exceptions are wrapped in SQLGenerationError."""
        from app.services.db_scanner import SQLGenerationError
        
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(side_effect=Exception("LLM API error"))
        
        with pytest.raises(SQLGenerationError) as exc_info:
            await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        assert "LLM API error" in str(exc_info.value)
        assert exc_info.value.needs_human_review is True

    @pytest.mark.asyncio
    async def test_generate_query_passes_correct_data_to_llm(self, scanner, mock_rule, sample_schema):
        """Test that correct rule and schema data is passed to LLM."""
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(
            return_value="SELECT id FROM users WHERE is_encrypted = false"
        )
        
        await scanner.generate_query(mock_rule, sample_schema, mock_llm)
        
        # Verify the call arguments
        call_args = mock_llm.generate_sql.call_args
        rule_dict = call_args[0][0]
        schema_dict = call_args[0][1]
        
        assert rule_dict["rule_code"] == "DATA-001"
        assert rule_dict["description"] == "Personal data must be encrypted"
        assert rule_dict["evaluation_criteria"] == "Records with PII must have is_encrypted=true"
        assert schema_dict["database_name"] == "testdb"
        assert len(schema_dict["tables"]) == 1
        assert schema_dict["tables"][0]["name"] == "users"


class TestSQLGenerationError:
    """Tests for the SQLGenerationError exception."""

    def test_error_message_format(self):
        """Test that error message is formatted correctly."""
        from app.services.db_scanner import SQLGenerationError
        
        error = SQLGenerationError("DATA-001", "Invalid syntax")
        
        assert "DATA-001" in str(error)
        assert "Invalid syntax" in str(error)
        assert error.rule_code == "DATA-001"
        assert error.reason == "Invalid syntax"

    def test_needs_human_review_flag(self):
        """Test that needs_human_review flag is set."""
        from app.services.db_scanner import SQLGenerationError
        
        error = SQLGenerationError("DATA-001", "Cannot translate")
        
        assert error.needs_human_review is True


class TestViolationScanning:
    """Tests for the violation scanning methods."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule for testing."""
        rule = MagicMock()
        rule.id = "123e4567-e89b-12d3-a456-426614174000"
        rule.rule_code = "DATA-001"
        rule.description = "Personal data must be encrypted"
        rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        rule.target_table = "users"
        rule.generated_sql = "SELECT id, email FROM users WHERE is_encrypted = false"
        rule.severity = "high"
        rule.is_active = True
        return rule

    @pytest.fixture
    def mock_inactive_rule(self):
        """Create a mock inactive compliance rule for testing."""
        rule = MagicMock()
        rule.id = "223e4567-e89b-12d3-a456-426614174001"
        rule.rule_code = "DATA-002"
        rule.description = "Inactive rule"
        rule.evaluation_criteria = "Some criteria"
        rule.target_table = "users"
        rule.generated_sql = "SELECT id FROM users"
        rule.severity = "low"
        rule.is_active = False
        return rule

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        columns = [
            ColumnInfo(name="id", data_type="integer", is_primary_key=True),
            ColumnInfo(name="email", data_type="varchar", is_nullable=False),
            ColumnInfo(name="is_encrypted", data_type="boolean", is_nullable=False),
        ]
        tables = [TableInfo(name="users", columns=columns)]
        return DatabaseSchema(database_name="testdb", tables=tables)


class TestGetRecordIdentifier:
    """Tests for the _get_record_identifier helper method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    def test_returns_id_field_when_present(self, scanner):
        """Test that 'id' field is used when present."""
        record_data = {"id": 123, "name": "test", "email": "test@example.com"}
        
        result = scanner._get_record_identifier(record_data)
        
        assert result == "123"

    def test_returns_field_ending_with_id_when_no_id(self, scanner):
        """Test that field ending with '_id' is used when no 'id' field."""
        record_data = {"user_id": 456, "name": "test", "email": "test@example.com"}
        
        result = scanner._get_record_identifier(record_data)
        
        assert result == "456"

    def test_returns_first_field_when_no_id_fields(self, scanner):
        """Test that first field is used when no id-like fields exist."""
        record_data = {"name": "test", "email": "test@example.com"}
        
        result = scanner._get_record_identifier(record_data)
        
        assert result == "test"

    def test_returns_unknown_for_empty_record(self, scanner):
        """Test that 'unknown' is returned for empty records."""
        record_data = {}
        
        result = scanner._get_record_identifier(record_data)
        
        assert result == "unknown"

    def test_converts_uuid_to_string(self, scanner):
        """Test that UUID values are converted to strings."""
        import uuid
        test_uuid = uuid.uuid4()
        record_data = {"id": test_uuid, "name": "test"}
        
        result = scanner._get_record_identifier(record_data)
        
        assert result == str(test_uuid)


class TestGenerateJustification:
    """Tests for the generate_justification method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule for testing."""
        rule = MagicMock()
        rule.rule_code = "DATA-001"
        rule.description = "Personal data must be encrypted"
        rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        return rule

    @pytest.mark.asyncio
    async def test_returns_llm_justification(self, scanner, mock_rule):
        """Test that LLM-generated justification is returned."""
        mock_llm = AsyncMock()
        mock_llm.explain_violation = AsyncMock(
            return_value="The record has is_encrypted=false but contains PII data."
        )
        record_data = {"id": 1, "email": "test@example.com", "is_encrypted": False}
        
        result = await scanner.generate_justification(mock_rule, record_data, mock_llm)
        
        assert result == "The record has is_encrypted=false but contains PII data."
        mock_llm.explain_violation.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_default_when_llm_unavailable(self, scanner, mock_rule):
        """Test that default message is returned when LLM is unavailable."""
        record_data = {"id": 1, "email": "test@example.com"}
        
        with patch("app.services.llm_client.get_llm_client") as mock_get_client:
            mock_get_client.side_effect = ValueError("No API key configured")
            
            result = await scanner.generate_justification(mock_rule, record_data)
        
        assert "DATA-001" in result
        assert "Personal data must be encrypted" in result

    @pytest.mark.asyncio
    async def test_returns_default_when_llm_returns_empty(self, scanner, mock_rule):
        """Test that default message is returned when LLM returns empty."""
        mock_llm = AsyncMock()
        mock_llm.explain_violation = AsyncMock(return_value="")
        record_data = {"id": 1, "email": "test@example.com"}
        
        result = await scanner.generate_justification(mock_rule, record_data, mock_llm)
        
        assert "DATA-001" in result
        assert "Personal data must be encrypted" in result

    @pytest.mark.asyncio
    async def test_returns_default_when_llm_raises_exception(self, scanner, mock_rule):
        """Test that default message is returned when LLM raises exception."""
        mock_llm = AsyncMock()
        mock_llm.explain_violation = AsyncMock(side_effect=Exception("API error"))
        record_data = {"id": 1, "email": "test@example.com"}
        
        result = await scanner.generate_justification(mock_rule, record_data, mock_llm)
        
        assert "DATA-001" in result
        assert "Personal data must be encrypted" in result


class TestGenerateRemediation:
    """Tests for the generate_remediation method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule for testing."""
        rule = MagicMock()
        rule.rule_code = "DATA-001"
        rule.description = "Personal data must be encrypted"
        rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        return rule

    @pytest.mark.asyncio
    async def test_returns_llm_remediation(self, scanner, mock_rule):
        """Test that LLM-generated remediation is returned."""
        mock_llm = AsyncMock()
        mock_llm.suggest_remediation = AsyncMock(
            return_value="1. Enable encryption for the record\n2. Verify encryption status"
        )
        record_data = {"id": 1, "email": "test@example.com", "is_encrypted": False}
        justification = "Record has is_encrypted=false"
        
        result = await scanner.generate_remediation(mock_rule, record_data, justification, mock_llm)
        
        assert result == "1. Enable encryption for the record\n2. Verify encryption status"
        mock_llm.suggest_remediation.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_unavailable(self, scanner, mock_rule):
        """Test that None is returned when LLM is unavailable (manual review required)."""
        record_data = {"id": 1, "email": "test@example.com"}
        justification = "Record has is_encrypted=false"
        
        with patch("app.services.llm_client.get_llm_client") as mock_get_client:
            mock_get_client.side_effect = ValueError("No API key configured")
            
            result = await scanner.generate_remediation(mock_rule, record_data, justification)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_returns_empty(self, scanner, mock_rule):
        """Test that None is returned when LLM returns empty (manual review required)."""
        mock_llm = AsyncMock()
        mock_llm.suggest_remediation = AsyncMock(return_value="")
        record_data = {"id": 1, "email": "test@example.com"}
        justification = "Record has is_encrypted=false"
        
        result = await scanner.generate_remediation(mock_rule, record_data, justification, mock_llm)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_raises_exception(self, scanner, mock_rule):
        """Test that None is returned when LLM raises exception (manual review required)."""
        mock_llm = AsyncMock()
        mock_llm.suggest_remediation = AsyncMock(side_effect=Exception("API error"))
        record_data = {"id": 1, "email": "test@example.com"}
        justification = "Record has is_encrypted=false"
        
        result = await scanner.generate_remediation(mock_rule, record_data, justification, mock_llm)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_passes_correct_data_to_llm(self, scanner, mock_rule):
        """Test that correct violation data is passed to LLM."""
        mock_llm = AsyncMock()
        mock_llm.suggest_remediation = AsyncMock(return_value="Fix the issue")
        record_data = {"id": 1, "email": "test@example.com"}
        justification = "Record has is_encrypted=false"
        
        await scanner.generate_remediation(mock_rule, record_data, justification, mock_llm)
        
        call_args = mock_llm.suggest_remediation.call_args[0][0]
        assert call_args["rule_description"] == "Personal data must be encrypted"
        assert call_args["justification"] == "Record has is_encrypted=false"
        assert call_args["record_data"] == {"id": 1, "email": "test@example.com"}


class TestScanForViolations:
    """Tests for the scan_for_violations method."""

    @pytest.fixture
    def scanner(self):
        """Create a DatabaseScannerService instance for testing."""
        return DatabaseScannerService()

    @pytest.fixture
    def mock_rule(self):
        """Create a mock compliance rule for testing."""
        rule = MagicMock()
        rule.id = "123e4567-e89b-12d3-a456-426614174000"
        rule.rule_code = "DATA-001"
        rule.description = "Personal data must be encrypted"
        rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        rule.target_table = "users"
        rule.generated_sql = "SELECT id, email FROM users WHERE is_encrypted = false"
        rule.severity = "high"
        rule.is_active = True
        return rule

    @pytest.fixture
    def mock_inactive_rule(self):
        """Create a mock inactive compliance rule for testing."""
        rule = MagicMock()
        rule.id = "223e4567-e89b-12d3-a456-426614174001"
        rule.rule_code = "DATA-002"
        rule.description = "Inactive rule"
        rule.evaluation_criteria = "Some criteria"
        rule.target_table = "users"
        rule.generated_sql = "SELECT id FROM users"
        rule.severity = "low"
        rule.is_active = False
        return rule

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        columns = [
            ColumnInfo(name="id", data_type="integer", is_primary_key=True),
            ColumnInfo(name="email", data_type="varchar", is_nullable=False),
            ColumnInfo(name="is_encrypted", data_type="boolean", is_nullable=False),
        ]
        tables = [TableInfo(name="users", columns=columns)]
        return DatabaseSchema(database_name="testdb", tables=tables)

    @pytest.mark.asyncio
    async def test_raises_error_when_not_connected(self, scanner, mock_rule):
        """Test that error is raised when not connected to database."""
        mock_session = AsyncMock()
        
        with pytest.raises(DatabaseConnectionError) as exc_info:
            await scanner.scan_for_violations([mock_rule], mock_session)
        
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_filters_inactive_rules(self, scanner, mock_rule, mock_inactive_rule, sample_schema):
        """Test that inactive rules are filtered out."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(return_value=[])
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                await scanner.scan_for_violations([mock_rule, mock_inactive_rule], mock_session, mock_llm)
        
        # Only the active rule should have its query executed
        assert mock_connection.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_creates_violations_with_correct_fields(self, scanner, mock_rule, sample_schema):
        """Test that violations are created with all required fields."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(return_value=[
            {"id": 1, "email": "test@example.com", "is_encrypted": False}
        ])
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.explain_violation = AsyncMock(return_value="Record is not encrypted")
        mock_llm.suggest_remediation = AsyncMock(return_value="Enable encryption")
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                with patch("app.models.violation.Violation") as MockViolation:
                    violations = await scanner.scan_for_violations([mock_rule], mock_session, mock_llm)
        
        # Verify Violation was created with correct fields
        MockViolation.assert_called_once()
        call_kwargs = MockViolation.call_args[1]
        assert call_kwargs["rule_id"] == mock_rule.id
        assert call_kwargs["record_identifier"] == "1"
        assert call_kwargs["severity"] == "high"  # Inherited from rule
        assert call_kwargs["status"] == "pending"  # Initial status
        assert call_kwargs["justification"] == "Record is not encrypted"
        assert call_kwargs["remediation_suggestion"] == "Enable encryption"
        
        # Verify Violation was created with correct fields
        MockViolation.assert_called_once()
        call_kwargs = MockViolation.call_args[1]
        assert call_kwargs["rule_id"] == mock_rule.id
        assert call_kwargs["record_identifier"] == "1"
        assert call_kwargs["severity"] == "high"  # Inherited from rule
        assert call_kwargs["status"] == "pending"  # Initial status
        assert call_kwargs["justification"] == "Record is not encrypted"
        assert call_kwargs["remediation_suggestion"] == "Enable encryption"

    @pytest.mark.asyncio
    async def test_commits_violations_to_session(self, scanner, mock_rule, sample_schema):
        """Test that violations are committed to the database session."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(return_value=[
            {"id": 1, "email": "test@example.com"}
        ])
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.explain_violation = AsyncMock(return_value="Violation explanation")
        mock_llm.suggest_remediation = AsyncMock(return_value="Fix it")
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                with patch("app.models.violation.Violation"):
                    await scanner.scan_for_violations([mock_rule], mock_session, mock_llm)
        
        # Verify session.add and session.commit were called
        assert mock_session.add.called
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_query_execution_error(self, scanner, mock_rule, sample_schema):
        """Test that query execution errors are handled gracefully."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(side_effect=Exception("Query failed"))
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                # Should not raise, just skip the rule
                violations = await scanner.scan_for_violations([mock_rule], mock_session, mock_llm)
        
        assert violations == []

    @pytest.mark.asyncio
    async def test_generates_sql_when_not_present(self, scanner, sample_schema):
        """Test that SQL is generated when rule doesn't have generated_sql."""
        # Create rule without generated_sql
        mock_rule = MagicMock()
        mock_rule.id = "123e4567-e89b-12d3-a456-426614174000"
        mock_rule.rule_code = "DATA-001"
        mock_rule.description = "Personal data must be encrypted"
        mock_rule.evaluation_criteria = "Records with PII must have is_encrypted=true"
        mock_rule.target_table = "users"
        mock_rule.generated_sql = None  # No SQL yet
        mock_rule.severity = "high"
        mock_rule.is_active = True
        
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(return_value=[])
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.generate_sql = AsyncMock(return_value="SELECT id FROM users WHERE is_encrypted = false")
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                await scanner.scan_for_violations([mock_rule], mock_session, mock_llm)
        
        # Verify generate_sql was called
        mock_llm.generate_sql.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_violations(self, scanner, mock_rule, sample_schema):
        """Test that empty list is returned when no violations found."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        mock_connection.fetch = AsyncMock(return_value=[])  # No violations
        scanner._connection = mock_connection
        scanner._config = MagicMock()
        scanner._config.database = "testdb"
        
        mock_session = AsyncMock()
        mock_llm = AsyncMock()
        
        with patch.object(scanner, "get_schema", return_value=sample_schema):
            with patch("app.services.llm_client.get_llm_client", return_value=mock_llm):
                violations = await scanner.scan_for_violations([mock_rule], mock_session, mock_llm)
        
        assert violations == []
        mock_session.commit.assert_not_called()

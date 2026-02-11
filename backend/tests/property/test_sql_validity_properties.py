"""Property-based tests for Generated SQL Validity.

Feature: data-policy-agent, Property 5: Generated SQL Validity

This module contains property-based tests that verify:
- The SQL validation logic correctly validates valid SQL SELECT statements
- Invalid SQL patterns are rejected
- Dangerous SQL keywords are detected and rejected

**Validates: Requirements 2.4**

Note: Since we can't actually call the LLM in property tests, we test the SQL
validation logic by:
1. Generating random valid SQL SELECT statements
2. Verifying the _validate_sql_syntax() method correctly validates them
3. Testing that invalid SQL patterns are rejected
4. Testing that dangerous SQL keywords are detected and rejected
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.services.db_scanner import DatabaseScannerService


# Dangerous SQL keywords that should be rejected
DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE"
}


def is_safe_identifier(name: str) -> bool:
    """Check if an identifier doesn't contain dangerous SQL keywords."""
    upper_name = name.upper()
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in upper_name:
            return False
    return True


class TestSQLValidityProperty:
    """Property tests for Generated SQL Validity.

    Feature: data-policy-agent, Property 5: Generated SQL Validity
    **Validates: Requirements 2.4**
    """

    # Strategies for generating valid SQL components

    # Valid table names (PostgreSQL identifiers) - excluding dangerous keywords
    valid_table_name = st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() != "" and not x[0].isdigit() and x.isidentifier() and is_safe_identifier(x))

    # Valid column names - excluding dangerous keywords
    valid_column_name = st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() != "" and not x[0].isdigit() and x.isidentifier() and is_safe_identifier(x))

    # Valid schema names
    valid_schema_name = st.sampled_from(["public", "app", "data", "schema1"])

    # Dangerous SQL keywords that should be rejected
    dangerous_keywords = st.sampled_from([
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
        "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE"
    ])

    # Safe string values for WHERE clauses - excluding dangerous keywords
    safe_string_value = st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))
    ).filter(lambda x: is_safe_identifier(x))

    @given(
        table=valid_table_name,
        columns=st.lists(valid_column_name, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_valid_simple_select_passes_validation(self, table: str, columns: list):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid simple SELECT statements should pass validation.
        """
        scanner = DatabaseScannerService()
        columns_str = ", ".join(columns)
        sql = f"SELECT {columns_str} FROM {table}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    @given(
        schema=valid_schema_name,
        table=valid_table_name,
        columns=st.lists(valid_column_name, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_valid_select_with_schema_passes_validation(self, schema: str, table: str, columns: list):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with schema-qualified table names should pass validation.
        """
        scanner = DatabaseScannerService()
        columns_str = ", ".join(columns)
        sql = f"SELECT {columns_str} FROM {schema}.{table}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL with schema should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    @given(
        table=valid_table_name,
        column=valid_column_name,
        value=st.integers(min_value=-1000, max_value=1000),
    )
    @settings(max_examples=100)
    def test_valid_select_with_where_clause_passes_validation(self, table: str, column: str, value: int):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with WHERE clauses should pass validation.
        """
        scanner = DatabaseScannerService()
        sql = f"SELECT * FROM {table} WHERE {column} = {value}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL with WHERE should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    @given(
        table=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_valid_select_with_null_check_passes_validation(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with IS NULL/IS NOT NULL should pass validation.
        """
        scanner = DatabaseScannerService()

        # Test IS NULL
        sql_null = f"SELECT * FROM {table} WHERE {column} IS NULL"
        is_valid, error_message = scanner._validate_sql_syntax(sql_null)
        assert is_valid, f"Valid SQL with IS NULL should pass: {sql_null}, error: {error_message}"

        # Test IS NOT NULL
        sql_not_null = f"SELECT * FROM {table} WHERE {column} IS NOT NULL"
        is_valid, error_message = scanner._validate_sql_syntax(sql_not_null)
        assert is_valid, f"Valid SQL with IS NOT NULL should pass: {sql_not_null}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
        limit=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_valid_select_with_limit_passes_validation(self, table: str, column: str, limit: int):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with LIMIT should pass validation.
        """
        scanner = DatabaseScannerService()
        sql = f"SELECT {column} FROM {table} LIMIT {limit}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL with LIMIT should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    @given(
        table=valid_table_name,
        subquery_table=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_valid_select_with_subquery_passes_validation(self, table: str, subquery_table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with subqueries should pass validation.
        """
        scanner = DatabaseScannerService()
        sql = f"SELECT * FROM {table} WHERE {column} IN (SELECT {column} FROM {subquery_table})"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL with subquery should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    @given(
        table1=valid_table_name,
        table2=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_valid_select_with_join_passes_validation(self, table1: str, table2: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Valid SELECT statements with JOINs should pass validation.
        """
        scanner = DatabaseScannerService()
        sql = f"SELECT * FROM {table1} JOIN {table2} ON {table1}.{column} = {table2}.{column}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"Valid SQL with JOIN should pass validation: {sql}, error: {error_message}"
        assert error_message == ""

    # Tests for invalid SQL patterns

    @given(dangerous_keyword=dangerous_keywords, table=valid_table_name)
    @settings(max_examples=100)
    def test_dangerous_keywords_are_rejected(self, dangerous_keyword: str, table: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SQL containing dangerous keywords (INSERT, UPDATE, DELETE, etc.) should be rejected.
        """
        scanner = DatabaseScannerService()

        # Test dangerous keyword at the start
        sql = f"{dangerous_keyword} INTO {table} VALUES (1)"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"Dangerous SQL should be rejected: {sql}"
        # Either it fails because it's not SELECT or because it contains forbidden keyword
        assert "SELECT" in error_message or "forbidden keyword" in error_message.lower()

    @given(table=valid_table_name, dangerous_keyword=dangerous_keywords)
    @settings(max_examples=100)
    def test_dangerous_keywords_in_select_are_rejected(self, table: str, dangerous_keyword: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT statements containing dangerous keywords should be rejected.
        """
        scanner = DatabaseScannerService()

        # Construct a SELECT that tries to sneak in a dangerous operation
        sql = f"SELECT * FROM {table}; {dangerous_keyword} FROM {table}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"SQL with dangerous keyword should be rejected: {sql}"
        assert "forbidden keyword" in error_message.lower()

    @given(table=valid_table_name)
    @settings(max_examples=100)
    def test_empty_sql_is_rejected(self, table: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Empty SQL queries should be rejected.
        """
        scanner = DatabaseScannerService()

        # Test empty string
        is_valid, error_message = scanner._validate_sql_syntax("")
        assert not is_valid, "Empty SQL should be rejected"
        assert "empty" in error_message.lower()

        # Test whitespace only
        is_valid, error_message = scanner._validate_sql_syntax("   ")
        assert not is_valid, "Whitespace-only SQL should be rejected"
        assert "empty" in error_message.lower()

    @given(table=valid_table_name, column=valid_column_name)
    @settings(max_examples=100)
    def test_sql_without_from_clause_is_rejected(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT statements without FROM clause should be rejected.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT {column}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"SQL without FROM should be rejected: {sql}"
        assert "FROM" in error_message

    @given(table=valid_table_name, column=valid_column_name)
    @settings(max_examples=100)
    def test_unbalanced_parentheses_are_rejected(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SQL with unbalanced parentheses should be rejected.
        """
        scanner = DatabaseScannerService()

        # Missing closing parenthesis
        sql = f"SELECT * FROM {table} WHERE ({column} = 1"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"SQL with unbalanced parentheses should be rejected: {sql}"
        assert "parentheses" in error_message.lower()

        # Missing opening parenthesis
        sql = f"SELECT * FROM {table} WHERE {column} = 1)"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"SQL with unbalanced parentheses should be rejected: {sql}"
        assert "parentheses" in error_message.lower()

    @given(table=valid_table_name, column=valid_column_name)
    @settings(max_examples=100)
    def test_unbalanced_quotes_are_rejected(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SQL with unbalanced single quotes should be rejected.
        """
        scanner = DatabaseScannerService()

        # Missing closing quote
        sql = f"SELECT * FROM {table} WHERE {column} = 'value"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert not is_valid, f"SQL with unbalanced quotes should be rejected: {sql}"
        assert "quotes" in error_message.lower()

    @given(
        table=valid_table_name,
        num_parens=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_balanced_nested_parentheses_pass_validation(self, table: str, num_parens: int):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SQL with properly balanced nested parentheses should pass validation.
        """
        scanner = DatabaseScannerService()

        # Build nested condition with balanced parentheses
        open_parens = "(" * num_parens
        close_parens = ")" * num_parens
        sql = f"SELECT * FROM {table} WHERE {open_parens}1 = 1{close_parens}"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SQL with balanced parentheses should pass: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        string_value=safe_string_value,
    )
    @settings(max_examples=100)
    def test_properly_quoted_strings_pass_validation(self, table: str, string_value: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SQL with properly quoted string literals should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT * FROM {table} WHERE name = '{string_value}'"

        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SQL with properly quoted string should pass: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_non_select_statements_are_rejected(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        Non-SELECT statements should be rejected.
        """
        scanner = DatabaseScannerService()

        # Test various non-SELECT statements
        non_select_statements = [
            f"INSERT INTO {table} ({column}) VALUES (1)",
            f"UPDATE {table} SET {column} = 1",
            f"DELETE FROM {table}",
            f"DROP TABLE {table}",
            f"TRUNCATE TABLE {table}",
            f"ALTER TABLE {table} ADD COLUMN new_col INT",
            f"CREATE TABLE {table} ({column} INT)",
        ]

        for sql in non_select_statements:
            is_valid, error_message = scanner._validate_sql_syntax(sql)
            assert not is_valid, f"Non-SELECT statement should be rejected: {sql}"

    @given(table=valid_table_name)
    @settings(max_examples=100)
    def test_select_star_passes_validation(self, table: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT * queries should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT * FROM {table}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT * should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
        alias=valid_column_name,
    )
    @settings(max_examples=100)
    def test_select_with_alias_passes_validation(self, table: str, column: str, alias: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT with column aliases should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT {column} AS {alias} FROM {table}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT with alias should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_select_with_aggregate_functions_passes_validation(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT with aggregate functions should pass validation.
        """
        scanner = DatabaseScannerService()

        aggregate_queries = [
            f"SELECT COUNT(*) FROM {table}",
            f"SELECT COUNT({column}) FROM {table}",
            f"SELECT SUM({column}) FROM {table}",
            f"SELECT AVG({column}) FROM {table}",
            f"SELECT MIN({column}) FROM {table}",
            f"SELECT MAX({column}) FROM {table}",
        ]

        for sql in aggregate_queries:
            is_valid, error_message = scanner._validate_sql_syntax(sql)
            assert is_valid, f"Aggregate query should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
    )
    @settings(max_examples=100)
    def test_select_distinct_passes_validation(self, table: str, column: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT DISTINCT should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT DISTINCT {column} FROM {table}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT DISTINCT should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
        values=st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_select_with_in_clause_passes_validation(self, table: str, column: str, values: list):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT with IN clause should pass validation.
        """
        scanner = DatabaseScannerService()

        values_str = ", ".join(str(v) for v in values)
        sql = f"SELECT * FROM {table} WHERE {column} IN ({values_str})"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT with IN clause should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
        min_val=st.integers(min_value=1, max_value=50),
        max_val=st.integers(min_value=51, max_value=100),
    )
    @settings(max_examples=100)
    def test_select_with_between_passes_validation(self, table: str, column: str, min_val: int, max_val: int):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT with BETWEEN should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT * FROM {table} WHERE {column} BETWEEN {min_val} AND {max_val}"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT with BETWEEN should pass validation: {sql}, error: {error_message}"

    @given(
        table=valid_table_name,
        column=valid_column_name,
        pattern=safe_string_value,
    )
    @settings(max_examples=100)
    def test_select_with_like_passes_validation(self, table: str, column: str, pattern: str):
        """Feature: data-policy-agent, Property 5: Generated SQL Validity
        **Validates: Requirements 2.4**

        SELECT with LIKE should pass validation.
        """
        scanner = DatabaseScannerService()

        sql = f"SELECT * FROM {table} WHERE {column} LIKE '%{pattern}%'"
        is_valid, error_message = scanner._validate_sql_syntax(sql)

        assert is_valid, f"SELECT with LIKE should pass validation: {sql}, error: {error_message}"

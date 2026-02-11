"""Property-based tests for database schema retrieval accuracy.

Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy

This module contains property-based tests that verify:
- The schema model integrity when representing database structures
- The round-trip accuracy of schema_to_dict() method
- That all table names, column names, and data types are preserved

**Validates: Requirements 2.2**
"""

from typing import Optional

import pytest
from hypothesis import given, strategies as st, settings

from app.services.db_scanner import (
    ColumnInfo,
    TableInfo,
    DatabaseSchema,
    DatabaseScannerService,
)


# Valid PostgreSQL identifier strategy (table/column names)
valid_identifier_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=63
).filter(lambda x: x.strip() != "" and not x[0].isdigit())

# Valid PostgreSQL data types
valid_data_type_strategy = st.sampled_from([
    "integer", "bigint", "smallint", "text", "boolean", "date", "uuid", "jsonb",
])

# Valid schema name strategy
valid_schema_name_strategy = st.sampled_from(["public", "app", "data"])

# Strategy for generating a valid column
valid_column_strategy = st.builds(
    ColumnInfo,
    name=valid_identifier_strategy,
    data_type=valid_data_type_strategy,
    is_nullable=st.booleans(),
    is_primary_key=st.booleans(),
    default_value=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
)

# Strategy for generating a list of columns
valid_columns_list_strategy = st.lists(valid_column_strategy, min_size=1, max_size=10)

# Strategy for generating a valid table
valid_table_strategy = st.builds(
    TableInfo,
    name=valid_identifier_strategy,
    schema_name=valid_schema_name_strategy,
    columns=valid_columns_list_strategy,
    row_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000000)),
)

# Strategy for generating a list of tables
valid_tables_list_strategy = st.lists(valid_table_strategy, min_size=0, max_size=10)

# Strategy for generating a valid database schema
valid_database_schema_strategy = st.builds(
    DatabaseSchema,
    database_name=valid_identifier_strategy,
    tables=valid_tables_list_strategy,
    version=st.one_of(st.none(), st.just("PostgreSQL 15.2")),
)


class TestSchemaRetrievalAccuracy:
    """Property tests for Schema Retrieval Accuracy.
    
    Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
    **Validates: Requirements 2.2**
    """

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_database_name(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        assert schema_dict["database_name"] == schema.database_name

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_table_count(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        assert len(schema_dict["tables"]) == len(schema.tables)

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_all_table_names(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        original_names = {t.name for t in schema.tables}
        dict_names = {t["name"] for t in schema_dict["tables"]}
        assert original_names == dict_names

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_all_column_names(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            orig_cols = {c.name for c in table.columns}
            dict_cols = {c["name"] for c in schema_dict["tables"][i]["columns"]}
            assert orig_cols == dict_cols

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_all_data_types(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            for j, col in enumerate(table.columns):
                assert schema_dict["tables"][i]["columns"][j]["type"] == col.data_type

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_schema_names(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            assert schema_dict["tables"][i]["schema"] == table.schema_name

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_nullable_flags(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            for j, col in enumerate(table.columns):
                assert schema_dict["tables"][i]["columns"][j]["nullable"] == col.is_nullable

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_to_dict_preserves_primary_key_flags(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            for j, col in enumerate(table.columns):
                assert schema_dict["tables"][i]["columns"][j]["primary_key"] == col.is_primary_key


class TestSchemaModelIntegrity:
    """Property tests for schema model integrity.
    
    Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
    **Validates: Requirements 2.2**
    """

    @given(
        name=valid_identifier_strategy,
        data_type=valid_data_type_strategy,
        is_nullable=st.booleans(),
        is_primary_key=st.booleans(),
        default_value=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=100)
    def test_column_info_preserves_all_attributes(
        self, name: str, data_type: str, is_nullable: bool,
        is_primary_key: bool, default_value: Optional[str],
    ):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        column = ColumnInfo(
            name=name, data_type=data_type, is_nullable=is_nullable,
            is_primary_key=is_primary_key, default_value=default_value,
        )
        assert column.name == name
        assert column.data_type == data_type
        assert column.is_nullable == is_nullable
        assert column.is_primary_key == is_primary_key
        assert column.default_value == default_value

    @given(
        name=valid_identifier_strategy,
        schema_name=valid_schema_name_strategy,
        columns=valid_columns_list_strategy,
        row_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000000)),
    )
    @settings(max_examples=100)
    def test_table_info_preserves_all_attributes(
        self, name: str, schema_name: str, columns: list, row_count: Optional[int],
    ):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        table = TableInfo(name=name, schema_name=schema_name, columns=columns, row_count=row_count)
        assert table.name == name
        assert table.schema_name == schema_name
        assert table.columns == columns
        assert table.row_count == row_count

    @given(
        database_name=valid_identifier_strategy,
        tables=valid_tables_list_strategy,
        version=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=100)
    def test_database_schema_preserves_all_attributes(
        self, database_name: str, tables: list, version: Optional[str],
    ):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        schema = DatabaseSchema(database_name=database_name, tables=tables, version=version)
        assert schema.database_name == database_name
        assert schema.tables == tables
        assert schema.version == version


class TestSchemaRoundTripConversion:
    """Property tests for schema round-trip conversion.
    
    Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
    **Validates: Requirements 2.2**
    """

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_can_reconstruct_database_name(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        reconstructed = DatabaseSchema(
            database_name=schema_dict["database_name"], tables=[], version=schema.version,
        )
        assert reconstructed.database_name == schema.database_name

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_can_reconstruct_table_structure(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table_dict in enumerate(schema_dict["tables"]):
            assert table_dict["name"] == schema.tables[i].name
            assert table_dict["schema"] == schema.tables[i].schema_name

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_can_reconstruct_column_structure(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table_dict in enumerate(schema_dict["tables"]):
            for j, col_dict in enumerate(table_dict["columns"]):
                orig_col = schema.tables[i].columns[j]
                reconstructed = ColumnInfo(
                    name=col_dict["name"], data_type=col_dict["type"],
                    is_nullable=col_dict["nullable"], is_primary_key=col_dict["primary_key"],
                )
                assert reconstructed.name == orig_col.name
                assert reconstructed.data_type == orig_col.data_type
                assert reconstructed.is_nullable == orig_col.is_nullable
                assert reconstructed.is_primary_key == orig_col.is_primary_key

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_column_order_preserved(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for i, table in enumerate(schema.tables):
            orig_names = [c.name for c in table.columns]
            dict_names = [c["name"] for c in schema_dict["tables"][i]["columns"]]
            assert orig_names == dict_names

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_table_order_preserved(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        orig_names = [t.name for t in schema.tables]
        dict_names = [t["name"] for t in schema_dict["tables"]]
        assert orig_names == dict_names


class TestSchemaCompleteness:
    """Property tests for schema completeness.
    
    Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
    **Validates: Requirements 2.2**
    """

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_all_tables_have_names(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        for table in schema.tables:
            assert table.name is not None
            assert len(table.name.strip()) > 0

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_all_columns_have_names_and_types(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        for table in schema.tables:
            for col in table.columns:
                assert col.name is not None
                assert len(col.name.strip()) > 0
                assert col.data_type is not None
                assert len(col.data_type.strip()) > 0

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_schema_dict_contains_required_keys(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        assert "database_name" in schema_dict
        assert "tables" in schema_dict

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_table_dicts_contain_required_keys(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for table_dict in schema_dict["tables"]:
            assert "name" in table_dict
            assert "schema" in table_dict
            assert "columns" in table_dict

    @given(schema=valid_database_schema_strategy)
    @settings(max_examples=100)
    def test_column_dicts_contain_required_keys(self, schema: DatabaseSchema):
        """Feature: data-policy-agent, Property 3: Schema Retrieval Accuracy
        **Validates: Requirements 2.2**"""
        scanner = DatabaseScannerService()
        schema_dict = scanner.schema_to_dict(schema)
        for table_dict in schema_dict["tables"]:
            for col_dict in table_dict["columns"]:
                assert "name" in col_dict
                assert "type" in col_dict
                assert "nullable" in col_dict
                assert "primary_key" in col_dict

"""Tests for Delta Lake schema reader."""

import os
from unittest.mock import patch

import pytest

from fabric_hydrate.delta_reader import DeltaSchemaReader, read_delta_schema
from fabric_hydrate.exceptions import DeltaTableError


class TestDeltaSchemaReader:
    """Tests for DeltaSchemaReader class."""

    def test_read_local_delta_table(self, sample_delta_table: str) -> None:
        """Test reading schema from local Delta table."""
        reader = DeltaSchemaReader()
        metadata = reader.read_schema(sample_delta_table)

        assert metadata.name == "delta_table"
        assert len(metadata.columns) == 5

        # Check column names
        col_names = [c.name for c in metadata.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names
        assert "created_at" in col_names
        assert "amount" in col_names

    def test_read_schema_column_types(self, sample_delta_table: str) -> None:
        """Test column types are correctly identified."""
        reader = DeltaSchemaReader()
        metadata = reader.read_schema(sample_delta_table)

        col_map = {c.name: c for c in metadata.columns}

        assert col_map["id"].type == "long"
        assert col_map["name"].type == "string"
        assert col_map["amount"].type == "double"

    def test_read_schema_nullability(self, sample_delta_table: str) -> None:
        """Test nullability is correctly identified."""
        reader = DeltaSchemaReader()
        metadata = reader.read_schema(sample_delta_table)

        col_map = {c.name: c for c in metadata.columns}

        assert col_map["id"].nullable is False
        assert col_map["name"].nullable is True
        assert col_map["email"].nullable is True

    def test_read_invalid_path(self) -> None:
        """Test reading from invalid path raises error."""
        reader = DeltaSchemaReader()

        with pytest.raises(DeltaTableError, match="Failed to open Delta table"):
            reader.read_schema("/nonexistent/path")

    def test_is_remote_path(self) -> None:
        """Test remote path detection."""
        reader = DeltaSchemaReader()

        assert reader._is_remote_path("abfss://container@account.dfs.core.windows.net/path")
        assert reader._is_remote_path("abfs://container@account.dfs.core.windows.net/path")
        assert reader._is_remote_path("az://container/path")
        assert reader._is_remote_path("wasbs://container@account.blob.core.windows.net/path")

        assert not reader._is_remote_path("/local/path")
        assert not reader._is_remote_path("./relative/path")
        assert not reader._is_remote_path("C:\\Windows\\path")

    def test_infer_table_name_from_path(self) -> None:
        """Test table name inference from path."""
        reader = DeltaSchemaReader()

        # Local path
        assert reader._infer_table_name("/data/tables/customers", None) == "customers"

        # OneLake URI
        onelake_uri = (
            "abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/orders"
        )
        assert reader._infer_table_name(onelake_uri, None) == "orders"

        # Metadata name takes precedence
        assert reader._infer_table_name("/any/path", "metadata_name") == "metadata_name"

    def test_infer_table_name_remote_no_tables_dir(self) -> None:
        """Test table name inference from remote path without Tables dir."""
        reader = DeltaSchemaReader()

        uri = "abfss://workspace@storage.dfs.core.windows.net/some/path/mytable"
        assert reader._infer_table_name(uri, None) == "mytable"

    def test_infer_table_name_with_trailing_slash(self) -> None:
        """Test table name inference from path with trailing slash."""
        reader = DeltaSchemaReader()

        onelake_uri = (
            "abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/orders/"
        )
        assert reader._infer_table_name(onelake_uri, None) == "orders"


class TestDeltaSchemaReaderStorageOptions:
    """Tests for storage options handling."""

    @patch.dict(
        os.environ,
        {
            "AZURE_CLIENT_ID": "client-id",
            "AZURE_CLIENT_SECRET": "client-secret",
            "AZURE_TENANT_ID": "tenant-id",
        },
        clear=False,
    )
    def test_service_principal_storage_options(self) -> None:
        """Test storage options with service principal credentials."""
        reader = DeltaSchemaReader()
        options = reader._get_default_storage_options()

        assert options["azure_client_id"] == "client-id"
        assert options["azure_client_secret"] == "client-secret"
        assert options["azure_tenant_id"] == "tenant-id"

    @patch.dict(
        os.environ,
        {
            "AZURE_STORAGE_ACCOUNT_KEY": "account-key",
        },
        clear=True,
    )
    def test_account_key_storage_options(self) -> None:
        """Test storage options with account key."""
        reader = DeltaSchemaReader()
        options = reader._get_default_storage_options()

        assert options["azure_storage_account_key"] == "account-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_fallback_to_azure_cli(self) -> None:
        """Test fallback to Azure CLI credentials."""
        reader = DeltaSchemaReader()
        options = reader._get_default_storage_options()

        assert options.get("azure_use_azure_cli") == "true"

    def test_custom_storage_options(self) -> None:
        """Test custom storage options."""
        custom_options = {"azure_account_name": "myaccount"}
        reader = DeltaSchemaReader(storage_options=custom_options)

        assert reader._storage_options == custom_options


class TestArrowTypeConversion:
    """Tests for Arrow type conversion."""

    def test_arrow_type_string_types(self) -> None:
        """Test string type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("string") == "string"
        assert reader._arrow_type_to_delta_type("utf8") == "string"
        assert reader._arrow_type_to_delta_type("large_string") == "string"

    def test_arrow_type_integer_types(self) -> None:
        """Test integer type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("int8") == "byte"
        assert reader._arrow_type_to_delta_type("int16") == "short"
        assert reader._arrow_type_to_delta_type("int32") == "integer"
        assert reader._arrow_type_to_delta_type("int64") == "long"

    def test_arrow_type_float_types(self) -> None:
        """Test float type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("float") == "float"
        assert reader._arrow_type_to_delta_type("float32") == "float"
        assert reader._arrow_type_to_delta_type("float64") == "double"
        assert reader._arrow_type_to_delta_type("double") == "double"

    def test_arrow_type_boolean(self) -> None:
        """Test boolean type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("bool") == "boolean"
        assert reader._arrow_type_to_delta_type("boolean") == "boolean"

    def test_arrow_type_binary(self) -> None:
        """Test binary type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("binary") == "binary"
        assert reader._arrow_type_to_delta_type("large_binary") == "binary"

    def test_arrow_type_date(self) -> None:
        """Test date type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("date32[day]") == "date"
        assert reader._arrow_type_to_delta_type("date32") == "date"
        assert reader._arrow_type_to_delta_type("date64[ms]") == "date"

    def test_arrow_type_timestamp(self) -> None:
        """Test timestamp type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("timestamp[ns]") == "timestamp_ntz"
        assert reader._arrow_type_to_delta_type("timestamp[us, tz=UTC]") == "timestamp"
        assert reader._arrow_type_to_delta_type("timestamp[ns, tz=utc]") == "timestamp"

    def test_arrow_type_decimal(self) -> None:
        """Test decimal type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("decimal128(10, 2)") == "decimal(10,2)"
        assert reader._arrow_type_to_delta_type("decimal256(38, 18)") == "decimal(38,18)"
        assert reader._arrow_type_to_delta_type("decimal") == "decimal"

    def test_arrow_type_list(self) -> None:
        """Test list/array type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("list<int64>") == "array<int64>"
        assert reader._arrow_type_to_delta_type("large_list<string>") == "array<string>"

    def test_arrow_type_map(self) -> None:
        """Test map type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("map<string, int64>") == "map"

    def test_arrow_type_struct(self) -> None:
        """Test struct type conversion."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("struct<a: int64, b: string>") == "struct"

    def test_arrow_type_arro3_format(self) -> None:
        """Test arro3 type format handling."""
        reader = DeltaSchemaReader()

        assert reader._arrow_type_to_delta_type("arro3.core.datatype<int64>") == "long"
        assert reader._arrow_type_to_delta_type("arro3.core.datatype<string>") == "string"
        assert reader._arrow_type_to_delta_type("arro3.core.datatype<double>") == "double"

    def test_arrow_type_unknown_fallback(self) -> None:
        """Test unknown type fallback."""
        reader = DeltaSchemaReader()

        result = reader._arrow_type_to_delta_type("unknown_type")
        assert result == "unknown_type"


class TestReadDeltaSchemaConvenienceFunction:
    """Tests for read_delta_schema convenience function."""

    def test_read_delta_schema(self, sample_delta_table: str) -> None:
        """Test convenience function."""
        metadata = read_delta_schema(sample_delta_table)

        assert metadata.name == "delta_table"
        assert len(metadata.columns) == 5

    def test_read_delta_schema_invalid_path(self) -> None:
        """Test convenience function with invalid path."""
        with pytest.raises(DeltaTableError):
            read_delta_schema("/nonexistent/path")

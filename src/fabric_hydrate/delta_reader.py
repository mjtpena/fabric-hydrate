"""Delta Lake schema reader module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deltalake import DeltaTable

from fabric_hydrate.exceptions import DeltaTableError, SchemaReadError
from fabric_hydrate.logging import get_logger
from fabric_hydrate.models import ColumnSchema, TableMetadata

logger = get_logger("delta_reader")


class DeltaSchemaReader:
    """Read schema information from Delta Lake tables."""

    def __init__(self, storage_options: dict[str, str] | None = None) -> None:
        """Initialize the reader with optional storage options.

        Args:
            storage_options: Azure storage options for authentication.
                If not provided, will attempt to use environment variables.
        """
        self._storage_options = storage_options or self._get_default_storage_options()

    def _get_default_storage_options(self) -> dict[str, str]:
        """Get default storage options from environment variables."""
        options: dict[str, str] = {}

        # Check for service principal credentials
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        tenant_id = os.environ.get("AZURE_TENANT_ID")

        if client_id and client_secret and tenant_id:
            options["azure_client_id"] = client_id
            options["azure_client_secret"] = client_secret
            options["azure_tenant_id"] = tenant_id

        # Check for storage account key (alternative auth)
        account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        if account_key:
            options["azure_storage_account_key"] = account_key

        # Use Azure CLI credentials if available
        if not options:
            options["azure_use_azure_cli"] = "true"

        return options

    def _is_remote_path(self, path: str) -> bool:
        """Check if the path is a remote storage path."""
        remote_prefixes = ("abfss://", "abfs://", "az://", "wasbs://", "wasb://", "https://")
        return path.startswith(remote_prefixes)

    def read_schema(self, path: str) -> TableMetadata:
        """Read schema from a Delta Lake table.

        Args:
            path: Local file path or OneLake/ADLS URI.

        Returns:
            TableMetadata containing schema information.

        Raises:
            SchemaReadError: If the schema cannot be read from the Delta table.
            DeltaTableError: If the path is not a valid Delta table.
        """
        logger.info(f"Reading schema from: {path}")

        # Determine if we need storage options
        storage_options = self._storage_options if self._is_remote_path(path) else None

        try:
            dt = DeltaTable(path, storage_options=storage_options)
        except Exception as e:
            logger.error(f"Failed to open Delta table: {e}")
            raise DeltaTableError(
                f"Failed to open Delta table at '{path}'",
                str(e),
            ) from e

        try:
            # Extract schema
            schema = dt.schema()
            columns = self._parse_schema_fields(schema.to_arrow())
        except Exception as e:
            logger.error(f"Failed to read schema: {e}")
            raise SchemaReadError(
                f"Failed to read schema from Delta table at '{path}'",
                str(e),
            ) from e

        # Extract metadata
        metadata = dt.metadata()

        # Infer table name from path
        table_name = self._infer_table_name(path, metadata.name)

        result = TableMetadata(
            name=table_name,
            location=path,
            columns=columns,
            partition_columns=list(metadata.partition_columns),
            properties=metadata.configuration,
            description=metadata.description,
            delta_version=dt.version(),
        )

        logger.info(
            f"Successfully read schema for '{table_name}': "
            f"{len(columns)} columns, version {dt.version()}"
        )
        return result

    def _infer_table_name(self, path: str, metadata_name: str | None) -> str:
        """Infer table name from path or metadata.

        Args:
            path: The table path.
            metadata_name: Name from Delta metadata.

        Returns:
            Inferred table name.
        """
        if metadata_name:
            return metadata_name

        # Try to extract from path
        if self._is_remote_path(path):
            # OneLake format: .../Tables/{table_name}
            parts = path.rstrip("/").split("/")
            if "Tables" in parts:
                idx = parts.index("Tables")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            return parts[-1]
        else:
            return Path(path).name

    def _parse_schema_fields(self, arrow_schema: Any) -> list[ColumnSchema]:
        """Parse Arrow schema into ColumnSchema objects.

        Args:
            arrow_schema: Arrow schema object.

        Returns:
            List of ColumnSchema objects.
        """
        columns: list[ColumnSchema] = []

        for field in arrow_schema:
            column = ColumnSchema(
                name=field.name,
                type=self._arrow_type_to_delta_type(field.type),
                nullable=field.nullable,
                metadata=dict(field.metadata) if field.metadata else {},
            )
            columns.append(column)

        return columns

    def _arrow_type_to_delta_type(self, arrow_type: Any) -> str:
        """Convert Arrow type to Delta Lake type string.

        Args:
            arrow_type: Arrow type object.

        Returns:
            Delta Lake type string.
        """
        # Use string representation for type detection (works with both pyarrow and arro3)
        type_str = str(arrow_type).lower().strip()

        # Handle arro3 format: "arro3.core.datatype<int64>" -> extract "int64"
        if "datatype<" in type_str:
            import re

            match = re.search(r"datatype<(.+)>", type_str)
            if match:
                type_str = match.group(1).strip()

        # Handle common types via string matching
        type_mapping = {
            "string": "string",
            "large_string": "string",
            "utf8": "string",
            "int8": "byte",
            "int16": "short",
            "int32": "integer",
            "int64": "long",
            "float": "float",
            "float32": "float",
            "float64": "double",
            "double": "double",
            "bool": "boolean",
            "boolean": "boolean",
            "binary": "binary",
            "large_binary": "binary",
            "date32[day]": "date",
            "date64[ms]": "date",
            "date32": "date",
        }

        # Direct match
        if type_str in type_mapping:
            return type_mapping[type_str]

        # Handle timestamp types
        if "timestamp" in type_str:
            if "tz=" in type_str or "utc" in type_str:
                return "timestamp"
            return "timestamp_ntz"

        # Handle decimal types
        if "decimal" in type_str:
            # Extract precision and scale from string like "decimal128(10, 2)"
            import re

            match = re.search(r"decimal\d*\((\d+),\s*(\d+)\)", type_str)
            if match:
                return f"decimal({match.group(1)},{match.group(2)})"
            return "decimal"

        # Handle list/array types
        if type_str.startswith("list<") or type_str.startswith("large_list<"):
            # Extract inner type
            inner = type_str.split("<", 1)[1].rsplit(">", 1)[0]
            return f"array<{inner}>"

        # Handle map types
        if type_str.startswith("map<"):
            return "map"

        # Handle struct types
        if type_str.startswith("struct<"):
            return "struct"

        # Fallback to cleaned string representation
        return type_str


def read_delta_schema(path: str) -> TableMetadata:
    """Convenience function to read Delta schema.

    Args:
        path: Path to Delta table.

    Returns:
        TableMetadata object.
    """
    reader = DeltaSchemaReader()
    return reader.read_schema(path)

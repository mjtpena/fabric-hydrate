"""Pydantic models for Fabric Hydrate."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeltaType(str, Enum):
    """Delta Lake data types."""

    STRING = "string"
    LONG = "long"
    INTEGER = "integer"
    SHORT = "short"
    BYTE = "byte"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    BINARY = "binary"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIMESTAMP_NTZ = "timestamp_ntz"
    DECIMAL = "decimal"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"


class ColumnSchema(BaseModel):
    """Schema definition for a single column."""

    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Data type (Delta Lake format)")
    nullable: bool = Field(True, description="Whether the column allows null values")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional column metadata")
    description: str | None = Field(None, description="Column description")

    def to_fabric_type(self) -> str:
        """Convert Delta type to Fabric-compatible type string."""
        type_mapping = {
            "string": "String",
            "long": "Int64",
            "integer": "Int32",
            "short": "Int16",
            "byte": "Int8",
            "float": "Single",
            "double": "Double",
            "boolean": "Boolean",
            "binary": "Binary",
            "date": "Date",
            "timestamp": "DateTime",
            "timestamp_ntz": "DateTime",
        }
        base_type = self.type.split("(")[0].lower()
        return type_mapping.get(base_type, self.type)


class TableMetadata(BaseModel):
    """Complete metadata for a Delta Lake table."""

    name: str = Field(..., description="Table name")
    location: str = Field(..., description="Table storage location (path or URI)")
    columns: list[ColumnSchema] = Field(default_factory=list, description="List of column schemas")
    partition_columns: list[str] = Field(default_factory=list, description="Partition column names")
    properties: dict[str, str] = Field(
        default_factory=dict, description="Table properties from Delta metadata"
    )
    description: str | None = Field(None, description="Table description")
    delta_version: int | None = Field(None, description="Current Delta table version")

    @property
    def column_names(self) -> list[str]:
        """Get list of column names."""
        return [col.name for col in self.columns]


class DiffType(str, Enum):
    """Types of schema differences."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    TYPE_CHANGED = "type_changed"
    NULLABILITY_CHANGED = "nullability_changed"


class ColumnDiff(BaseModel):
    """Difference detected in a column."""

    column_name: str = Field(..., description="Name of the column")
    diff_type: DiffType = Field(..., description="Type of difference")
    source_value: str | None = Field(None, description="Value in source schema")
    target_value: str | None = Field(None, description="Value in target schema")
    message: str = Field(..., description="Human-readable description of the diff")


class DiffResult(BaseModel):
    """Result of comparing two table schemas."""

    table_name: str = Field(..., description="Table name")
    source_location: str = Field(..., description="Source schema location")
    target_location: str | None = Field(None, description="Target schema location")
    has_differences: bool = Field(False, description="Whether any differences were found")
    column_diffs: list[ColumnDiff] = Field(
        default_factory=list, description="List of column-level differences"
    )
    summary: str = Field("", description="Summary of all differences")

    @property
    def added_columns(self) -> list[ColumnDiff]:
        """Get columns that were added."""
        return [d for d in self.column_diffs if d.diff_type == DiffType.ADDED]

    @property
    def removed_columns(self) -> list[ColumnDiff]:
        """Get columns that were removed."""
        return [d for d in self.column_diffs if d.diff_type == DiffType.REMOVED]

    @property
    def modified_columns(self) -> list[ColumnDiff]:
        """Get columns that were modified."""
        return [
            d
            for d in self.column_diffs
            if d.diff_type in (DiffType.TYPE_CHANGED, DiffType.NULLABILITY_CHANGED)
        ]


class TableConfig(BaseModel):
    """Configuration for a single table in the hydration config."""

    name: str = Field(..., description="Table name in Fabric")
    source: str = Field(..., description="Source path (local or OneLake URI)")
    description: str | None = Field(None, description="Optional table description")


class OutputConfig(BaseModel):
    """Output configuration settings."""

    format: str = Field("json", description="Output format (json or yaml)")
    path: str = Field("./metadata", description="Output directory path")


class FabricConfig(BaseModel):
    """Main configuration file model."""

    workspace_id: str | None = Field(None, description="Microsoft Fabric workspace ID")
    lakehouse_id: str | None = Field(None, description="Microsoft Fabric lakehouse ID")
    tables: list[TableConfig] = Field(default_factory=list, description="List of tables to process")
    output: OutputConfig = Field(default_factory=OutputConfig, description="Output configuration")

    @classmethod
    def from_yaml(cls, path: str) -> FabricConfig:
        """Load configuration from a YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

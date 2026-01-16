"""Fabric metadata generator module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from fabric_hydrate.models import ColumnSchema, TableMetadata


class FabricColumnMetadata(BaseModel):
    """Fabric-compatible column metadata format."""

    name: str = Field(..., description="Column name")
    dataType: str = Field(..., description="Fabric data type")
    isNullable: bool = Field(True, description="Whether nulls are allowed")
    description: str | None = Field(None, description="Column description")
    displayName: str | None = Field(None, description="Display name for the column")
    semanticType: str | None = Field(None, description="Semantic type hint")


class FabricTableMetadata(BaseModel):
    """Fabric-compatible table metadata format."""

    name: str = Field(..., description="Table name")
    description: str | None = Field(None, description="Table description")
    columns: list[FabricColumnMetadata] = Field(
        default_factory=list, description="Column definitions"
    )
    partitionBy: list[str] = Field(default_factory=list, description="Partition column names")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional properties")
    sourceLocation: str = Field(..., description="Original source location")
    deltaVersion: int | None = Field(None, description="Delta table version")


class FabricMetadataGenerator:
    """Generate Fabric-compatible metadata from Delta Lake schemas."""

    # Mapping from Delta Lake types to Fabric types
    TYPE_MAPPING: dict[str, str] = {
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

    def generate(self, table_metadata: TableMetadata) -> FabricTableMetadata:
        """Generate Fabric-compatible metadata from Delta table metadata.

        Args:
            table_metadata: Source Delta table metadata.

        Returns:
            FabricTableMetadata object.
        """
        columns = [self._convert_column(col) for col in table_metadata.columns]

        return FabricTableMetadata(
            name=table_metadata.name,
            description=table_metadata.description,
            columns=columns,
            partitionBy=table_metadata.partition_columns,
            properties=self._prepare_properties(table_metadata),
            sourceLocation=table_metadata.location,
            deltaVersion=table_metadata.delta_version,
        )

    def _convert_column(self, column: ColumnSchema) -> FabricColumnMetadata:
        """Convert a Delta column schema to Fabric format.

        Args:
            column: Source column schema.

        Returns:
            FabricColumnMetadata object.
        """
        fabric_type = self._convert_type(column.type)
        semantic_type = self._infer_semantic_type(column.name, column.type)

        return FabricColumnMetadata(
            name=column.name,
            dataType=fabric_type,
            isNullable=column.nullable,
            description=column.description,
            displayName=self._generate_display_name(column.name),
            semanticType=semantic_type,
        )

    def _convert_type(self, delta_type: str) -> str:
        """Convert Delta type to Fabric type.

        Args:
            delta_type: Delta Lake type string.

        Returns:
            Fabric type string.
        """
        # Handle base types (without parameters)
        base_type = delta_type.split("(")[0].split("<")[0].lower()

        if base_type in self.TYPE_MAPPING:
            return self.TYPE_MAPPING[base_type]

        # Handle decimal with precision/scale
        if delta_type.startswith("decimal"):
            return f"Decimal{delta_type[7:]}"  # Keep (precision,scale)

        # Handle array types
        if delta_type.startswith("array<"):
            inner_type = delta_type[6:-1]
            fabric_inner = self._convert_type(inner_type)
            return f"Array<{fabric_inner}>"

        # Handle map types
        if delta_type.startswith("map<"):
            # Map to generic Object in Fabric
            return "Object"

        # Handle struct types
        if delta_type.startswith("struct<"):
            # Complex struct - represent as Object
            return "Object"

        # Unknown type - return as-is with capitalization
        return delta_type.capitalize()

    def _infer_semantic_type(self, column_name: str, delta_type: str) -> str | None:
        """Infer semantic type from column name and type.

        Args:
            column_name: Column name.
            delta_type: Delta type string.

        Returns:
            Semantic type hint or None.
        """
        name_lower = column_name.lower()

        # Email patterns
        if "email" in name_lower:
            return "Email"

        # URL patterns
        if any(p in name_lower for p in ["url", "link", "href", "uri"]):
            return "URL"

        # Geographic patterns
        if any(p in name_lower for p in ["latitude", "lat"]):
            return "Latitude"
        if any(p in name_lower for p in ["longitude", "lng", "lon"]):
            return "Longitude"
        if "country" in name_lower:
            return "Country"
        if "city" in name_lower:
            return "City"
        if "zip" in name_lower or "postal" in name_lower:
            return "PostalCode"

        # Date/time patterns
        if any(p in name_lower for p in ["created_at", "updated_at", "modified_at"]):
            return "DateTime"
        if "date" in name_lower and delta_type == "date":
            return "Date"

        # Currency patterns
        if any(p in name_lower for p in ["price", "amount", "cost", "revenue", "total"]):
            return "Currency"

        # Identity patterns
        if name_lower.endswith("_id") or name_lower == "id":
            return "Identifier"

        return None

    def _generate_display_name(self, column_name: str) -> str:
        """Generate a human-readable display name.

        Args:
            column_name: Original column name.

        Returns:
            Display name with spaces and title case.
        """
        # Handle snake_case
        name = column_name.replace("_", " ")

        # Handle camelCase
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0 and name[i - 1].islower():
                result.append(" ")
            result.append(char)
        name = "".join(result)

        return name.title()

    def _prepare_properties(self, table_metadata: TableMetadata) -> dict[str, Any]:
        """Prepare properties dict for Fabric metadata.

        Args:
            table_metadata: Source table metadata.

        Returns:
            Properties dictionary.
        """
        props: dict[str, Any] = {
            "source": "delta-lake",
            "generatedBy": "fabric-hydrate",
        }

        if table_metadata.properties:
            # Include relevant Delta properties
            for key, value in table_metadata.properties.items():
                if key.startswith("delta."):
                    props[key] = value

        return props

"""Tests for Pydantic models."""

from fabric_hydrate.models import (
    ColumnDiff,
    ColumnSchema,
    DiffResult,
    DiffType,
    FabricConfig,
    TableMetadata,
)


class TestColumnSchema:
    """Tests for ColumnSchema model."""

    def test_create_column_schema(self) -> None:
        """Test creating a basic column schema."""
        col = ColumnSchema(name="test_col", type="string", nullable=True)

        assert col.name == "test_col"
        assert col.type == "string"
        assert col.nullable is True
        assert col.metadata == {}
        assert col.description is None

    def test_to_fabric_type_mapping(self) -> None:
        """Test Delta to Fabric type conversion."""
        test_cases = [
            ("string", "String"),
            ("long", "Int64"),
            ("integer", "Int32"),
            ("double", "Double"),
            ("boolean", "Boolean"),
            ("timestamp", "DateTime"),
            ("date", "Date"),
        ]

        for delta_type, expected_fabric_type in test_cases:
            col = ColumnSchema(name="test", type=delta_type)
            assert col.to_fabric_type() == expected_fabric_type

    def test_to_fabric_type_decimal(self) -> None:
        """Test decimal type conversion preserves precision."""
        col = ColumnSchema(name="amount", type="decimal(10,2)")
        # Base type lookup returns the input for unknown types
        assert col.to_fabric_type() == "decimal(10,2)"


class TestTableMetadata:
    """Tests for TableMetadata model."""

    def test_create_table_metadata(self, sample_table_metadata: TableMetadata) -> None:
        """Test creating table metadata."""
        assert sample_table_metadata.name == "test_table"
        assert len(sample_table_metadata.columns) == 5
        assert sample_table_metadata.partition_columns == ["created_at"]

    def test_column_names_property(self, sample_table_metadata: TableMetadata) -> None:
        """Test column_names property."""
        expected = ["id", "name", "email", "created_at", "price"]
        assert sample_table_metadata.column_names == expected


class TestDiffResult:
    """Tests for DiffResult model."""

    def test_empty_diff_result(self) -> None:
        """Test diff result with no differences."""
        result = DiffResult(
            table_name="test",
            source_location="/source",
            target_location="/target",
            has_differences=False,
            column_diffs=[],
            summary="No differences",
        )

        assert result.has_differences is False
        assert result.added_columns == []
        assert result.removed_columns == []
        assert result.modified_columns == []

    def test_diff_result_with_changes(self) -> None:
        """Test diff result with various changes."""
        diffs = [
            ColumnDiff(
                column_name="new_col",
                diff_type=DiffType.ADDED,
                source_value="string",
                target_value=None,
                message="New column",
            ),
            ColumnDiff(
                column_name="old_col",
                diff_type=DiffType.REMOVED,
                source_value=None,
                target_value="integer",
                message="Removed column",
            ),
            ColumnDiff(
                column_name="changed_col",
                diff_type=DiffType.TYPE_CHANGED,
                source_value="long",
                target_value="integer",
                message="Type changed",
            ),
        ]

        result = DiffResult(
            table_name="test",
            source_location="/source",
            target_location="/target",
            has_differences=True,
            column_diffs=diffs,
            summary="3 changes",
        )

        assert len(result.added_columns) == 1
        assert len(result.removed_columns) == 1
        assert len(result.modified_columns) == 1


class TestFabricConfig:
    """Tests for FabricConfig model."""

    def test_load_from_yaml(self, sample_config_file: str) -> None:
        """Test loading config from YAML file."""
        config = FabricConfig.from_yaml(sample_config_file)

        assert config.workspace_id == "test-workspace-id"
        assert config.lakehouse_id == "test-lakehouse-id"
        assert len(config.tables) == 2
        assert config.tables[0].name == "customers"
        assert config.output.format == "json"

    def test_default_output_config(self) -> None:
        """Test default output configuration."""
        config = FabricConfig()

        assert config.output.format == "json"
        assert config.output.path == "./metadata"

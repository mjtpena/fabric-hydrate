"""Tests for schema diff engine."""

from fabric_hydrate.diff_engine import SchemaDiffEngine
from fabric_hydrate.models import ColumnSchema, DiffType, TableMetadata


class TestSchemaDiffEngine:
    """Tests for SchemaDiffEngine class."""

    def test_compare_identical_schemas(self) -> None:
        """Test comparing identical schemas returns no differences."""
        columns = [
            ColumnSchema(name="id", type="long", nullable=False),
            ColumnSchema(name="name", type="string", nullable=True),
        ]

        source = TableMetadata(
            name="test",
            location="/source",
            columns=columns.copy(),
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=columns.copy(),
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is False
        assert len(result.column_diffs) == 0

    def test_detect_added_columns(self) -> None:
        """Test detecting newly added columns."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
                ColumnSchema(name="new_col", type="string", nullable=True),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
            ],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is True
        assert len(result.added_columns) == 1
        assert result.added_columns[0].column_name == "new_col"

    def test_detect_removed_columns(self) -> None:
        """Test detecting removed columns."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
                ColumnSchema(name="old_col", type="string", nullable=True),
            ],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is True
        assert len(result.removed_columns) == 1
        assert result.removed_columns[0].column_name == "old_col"

    def test_detect_type_changes(self) -> None:
        """Test detecting column type changes."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="value", type="long", nullable=True),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[
                ColumnSchema(name="value", type="integer", nullable=True),
            ],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is True
        type_changed = [d for d in result.column_diffs if d.diff_type == DiffType.TYPE_CHANGED]
        assert len(type_changed) == 1
        assert type_changed[0].column_name == "value"
        assert type_changed[0].source_value == "long"
        assert type_changed[0].target_value == "integer"

    def test_detect_nullability_changes(self) -> None:
        """Test detecting nullability changes."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="required_col", type="string", nullable=False),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[
                ColumnSchema(name="required_col", type="string", nullable=True),
            ],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is True
        null_changed = [
            d for d in result.column_diffs if d.diff_type == DiffType.NULLABILITY_CHANGED
        ]
        assert len(null_changed) == 1

    def test_multiple_changes(self) -> None:
        """Test detecting multiple changes at once."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
                ColumnSchema(name="new_col", type="string", nullable=True),
                ColumnSchema(name="changed_type", type="double", nullable=True),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[
                ColumnSchema(name="id", type="long", nullable=False),
                ColumnSchema(name="old_col", type="integer", nullable=True),
                ColumnSchema(name="changed_type", type="float", nullable=True),
            ],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert result.has_differences is True
        assert len(result.added_columns) == 1
        assert len(result.removed_columns) == 1
        assert len(result.modified_columns) == 1

    def test_summary_generation(self) -> None:
        """Test summary message generation."""
        source = TableMetadata(
            name="test",
            location="/source",
            columns=[
                ColumnSchema(name="new1", type="string", nullable=True),
                ColumnSchema(name="new2", type="string", nullable=True),
            ],
        )
        target = TableMetadata(
            name="test",
            location="/target",
            columns=[],
        )

        engine = SchemaDiffEngine()
        result = engine.compare(source, target)

        assert "2 added" in result.summary
        assert "2 difference(s)" in result.summary

    def test_compare_multiple_tables(self) -> None:
        """Test comparing multiple tables."""
        source_tables = [
            TableMetadata(
                name="table1",
                location="/source/table1",
                columns=[ColumnSchema(name="id", type="long", nullable=False)],
            ),
            TableMetadata(
                name="table2",
                location="/source/table2",
                columns=[ColumnSchema(name="id", type="long", nullable=False)],
            ),
        ]
        target_tables = [
            TableMetadata(
                name="table1",
                location="/target/table1",
                columns=[ColumnSchema(name="id", type="long", nullable=False)],
            ),
        ]

        engine = SchemaDiffEngine()
        results = engine.compare_multiple(source_tables, target_tables)

        assert len(results) == 2
        # table1 should have no differences
        assert results[0].has_differences is False
        # table2 is new, all columns are "added"
        assert results[1].has_differences is True

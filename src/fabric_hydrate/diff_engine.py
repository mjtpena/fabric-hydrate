"""Schema diff engine module."""

from __future__ import annotations

from fabric_hydrate.models import (
    ColumnDiff,
    DiffResult,
    DiffType,
    TableMetadata,
)


class SchemaDiffEngine:
    """Compare schemas between two Delta Lake tables."""

    def compare(
        self,
        source: TableMetadata,
        target: TableMetadata,
    ) -> DiffResult:
        """Compare two table schemas and identify differences.

        Args:
            source: Source table metadata (expected/new schema).
            target: Target table metadata (existing schema).

        Returns:
            DiffResult containing all identified differences.
        """
        column_diffs: list[ColumnDiff] = []

        # Build lookup maps
        source_columns = {col.name: col for col in source.columns}
        target_columns = {col.name: col for col in target.columns}

        source_names = set(source_columns.keys())
        target_names = set(target_columns.keys())

        # Find added columns (in source but not in target)
        for name in source_names - target_names:
            col = source_columns[name]
            column_diffs.append(
                ColumnDiff(
                    column_name=name,
                    diff_type=DiffType.ADDED,
                    source_value=col.type,
                    target_value=None,
                    message=f"New column '{name}' ({col.type})",
                )
            )

        # Find removed columns (in target but not in source)
        for name in target_names - source_names:
            col = target_columns[name]
            column_diffs.append(
                ColumnDiff(
                    column_name=name,
                    diff_type=DiffType.REMOVED,
                    source_value=None,
                    target_value=col.type,
                    message=f"Column '{name}' removed (was {col.type})",
                )
            )

        # Find modified columns (in both, but different)
        for name in source_names & target_names:
            source_col = source_columns[name]
            target_col = target_columns[name]

            # Check type changes
            if source_col.type != target_col.type:
                column_diffs.append(
                    ColumnDiff(
                        column_name=name,
                        diff_type=DiffType.TYPE_CHANGED,
                        source_value=source_col.type,
                        target_value=target_col.type,
                        message=f"Type changed: {target_col.type} → {source_col.type}",
                    )
                )

            # Check nullability changes
            if source_col.nullable != target_col.nullable:
                source_null = "nullable" if source_col.nullable else "not nullable"
                target_null = "nullable" if target_col.nullable else "not nullable"
                column_diffs.append(
                    ColumnDiff(
                        column_name=name,
                        diff_type=DiffType.NULLABILITY_CHANGED,
                        source_value=source_null,
                        target_value=target_null,
                        message=f"Nullability changed: {target_null} → {source_null}",
                    )
                )

        # Generate summary
        summary = self._generate_summary(column_diffs)

        return DiffResult(
            table_name=source.name,
            source_location=source.location,
            target_location=target.location,
            has_differences=len(column_diffs) > 0,
            column_diffs=column_diffs,
            summary=summary,
        )

    def _generate_summary(self, diffs: list[ColumnDiff]) -> str:
        """Generate a human-readable summary of differences.

        Args:
            diffs: List of column differences.

        Returns:
            Summary string.
        """
        if not diffs:
            return "No differences found"

        added = sum(1 for d in diffs if d.diff_type == DiffType.ADDED)
        removed = sum(1 for d in diffs if d.diff_type == DiffType.REMOVED)
        type_changed = sum(1 for d in diffs if d.diff_type == DiffType.TYPE_CHANGED)
        null_changed = sum(1 for d in diffs if d.diff_type == DiffType.NULLABILITY_CHANGED)

        parts = []
        if added:
            parts.append(f"{added} added")
        if removed:
            parts.append(f"{removed} removed")
        if type_changed:
            parts.append(f"{type_changed} type changes")
        if null_changed:
            parts.append(f"{null_changed} nullability changes")

        return f"Found {len(diffs)} difference(s): {', '.join(parts)}"

    def compare_multiple(
        self,
        source_tables: list[TableMetadata],
        target_tables: list[TableMetadata],
    ) -> list[DiffResult]:
        """Compare multiple tables by matching names.

        Args:
            source_tables: List of source table metadata.
            target_tables: List of target table metadata.

        Returns:
            List of DiffResult for each matched table.
        """
        results: list[DiffResult] = []

        target_lookup = {t.name: t for t in target_tables}

        for source in source_tables:
            if source.name in target_lookup:
                result = self.compare(source, target_lookup[source.name])
                results.append(result)
            else:
                # Table exists in source but not target - all columns are "added"
                results.append(
                    DiffResult(
                        table_name=source.name,
                        source_location=source.location,
                        target_location=None,
                        has_differences=True,
                        column_diffs=[
                            ColumnDiff(
                                column_name=col.name,
                                diff_type=DiffType.ADDED,
                                source_value=col.type,
                                target_value=None,
                                message=f"New column '{col.name}' ({col.type})",
                            )
                            for col in source.columns
                        ],
                        summary=f"New table with {len(source.columns)} columns",
                    )
                )

        return results

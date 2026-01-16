"""Tests for CLI commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from fabric_hydrate.cli import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_version_option(self) -> None:
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "fabric-hydrate" in result.stdout
        assert "0.1.0" in result.stdout

    def test_help_option(self) -> None:
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Extract" in result.stdout or "hydrate" in result.stdout.lower()

    def test_verbose_flag(self, sample_delta_table: str) -> None:
        """Test --verbose flag enables logging."""
        result = runner.invoke(app, ["--verbose", "schema", "extract", sample_delta_table])
        assert result.exit_code == 0

    def test_debug_flag(self, sample_delta_table: str) -> None:
        """Test --debug flag enables debug logging."""
        result = runner.invoke(app, ["--debug", "schema", "extract", sample_delta_table])
        assert result.exit_code == 0

    def test_schema_extract_local(self, sample_delta_table: str) -> None:
        """Test schema extract command with local Delta table."""
        result = runner.invoke(app, ["schema", "extract", sample_delta_table])

        assert result.exit_code == 0
        # Output should contain valid JSON structure
        assert '"name"' in result.stdout
        assert '"columns"' in result.stdout

    def test_schema_extract_to_file(self, sample_delta_table: str, tmp_path: Path) -> None:
        """Test schema extract command with output file."""
        output_file = tmp_path / "schema.json"

        result = runner.invoke(
            app,
            ["schema", "extract", sample_delta_table, "--output", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify file content
        content = json.loads(output_file.read_text())
        assert "columns" in content

    def test_schema_extract_yaml_format(self, sample_delta_table: str) -> None:
        """Test schema extract with YAML format."""
        result = runner.invoke(
            app,
            ["schema", "extract", sample_delta_table, "--format", "yaml"],
        )

        assert result.exit_code == 0
        # YAML format shouldn't have JSON braces
        assert "{" not in result.stdout.strip()[:20]
        assert "columns:" in result.stdout or "name:" in result.stdout

    def test_schema_extract_invalid_path(self) -> None:
        """Test schema extract with invalid path."""
        result = runner.invoke(app, ["schema", "extract", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_schema_list(self, sample_delta_table: str) -> None:
        """Test schema list command."""
        result = runner.invoke(app, ["schema", "list", sample_delta_table])

        assert result.exit_code == 0
        # Should display column information
        assert "Column" in result.stdout or "id" in result.stdout

    def test_schema_list_invalid_path(self) -> None:
        """Test schema list with invalid path."""
        result = runner.invoke(app, ["schema", "list", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_validate_config(self, sample_config_file: str) -> None:
        """Test validate command with valid config."""
        result = runner.invoke(app, ["validate", sample_config_file])

        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_validate_missing_config(self, tmp_path: Path) -> None:
        """Test validate command with missing config file."""
        result = runner.invoke(app, ["validate", str(tmp_path / "nonexistent.yaml")])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_validate_invalid_config(self, tmp_path: Path) -> None:
        """Test validate command with invalid config content."""
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text("this is not: valid: yaml: content: [")

        result = runner.invoke(app, ["validate", str(invalid_config)])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_hydrate_dry_run(self, sample_delta_table: str) -> None:
        """Test hydrate command with dry-run."""
        result = runner.invoke(
            app,
            ["hydrate", "--source", sample_delta_table, "--dry-run"],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout

    def test_hydrate_with_output(self, sample_delta_table: str, tmp_path: Path) -> None:
        """Test hydrate command writes output files."""
        output_dir = tmp_path / "metadata"

        result = runner.invoke(
            app,
            ["hydrate", "--source", sample_delta_table, "--output", str(output_dir)],
        )

        assert result.exit_code == 0
        assert output_dir.exists()

        # Should have created at least one JSON file
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) > 0

    def test_hydrate_missing_source_and_config(self) -> None:
        """Test hydrate command without source or config."""
        result = runner.invoke(app, ["hydrate"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_hydrate_with_config(
        self, sample_config_file: str, sample_delta_table: str, tmp_path: Path
    ) -> None:
        """Test hydrate command with config file."""
        # sample_config_file fixture ensures config loading works
        _ = sample_config_file  # Mark as used
        # Create config that points to the sample delta table
        # Use forward slashes for YAML compatibility
        source_path = sample_delta_table.replace("\\", "/")
        output_path = str(tmp_path / "output").replace("\\", "/")

        config_path = tmp_path / "config.yaml"
        config_content = f"""workspace_id: "test-workspace"
lakehouse_id: "test-lakehouse"
tables:
  - name: test_table
    source: "{source_path}"
output:
  format: json
  path: "{output_path}"
"""
        config_path.write_text(config_content)

        result = runner.invoke(app, ["hydrate", "--config", str(config_path)])

        assert result.exit_code == 0, f"Output: {result.stdout}"
        assert "Processed" in result.stdout

    def test_hydrate_invalid_source(self) -> None:
        """Test hydrate command with invalid source."""
        result = runner.invoke(
            app,
            ["hydrate", "--source", "/nonexistent/path"],
        )

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_diff_between_tables(self, sample_delta_table: str, tmp_path: Path) -> None:
        """Test diff command between two tables."""
        import pyarrow as pa
        from deltalake import write_deltalake

        # Create a second table with different schema
        table2_path = tmp_path / "table2"
        schema = pa.schema(
            [
                pa.field("id", pa.int64(), nullable=False),
                pa.field("name", pa.string(), nullable=True),
                # Missing email, different columns
                pa.field("new_column", pa.string(), nullable=True),
            ]
        )
        data = pa.table(
            {
                "id": [1],
                "name": ["Test"],
                "new_column": ["value"],
            },
            schema=schema,
        )
        write_deltalake(str(table2_path), data, mode="overwrite")

        result = runner.invoke(app, ["diff", sample_delta_table, str(table2_path)])

        # Should show differences
        assert result.exit_code == 0
        assert "Differences" in result.stdout or "difference" in result.stdout.lower()

    def test_diff_identical_tables(self, sample_delta_table: str) -> None:
        """Test diff command with identical tables."""
        result = runner.invoke(app, ["diff", sample_delta_table, sample_delta_table])

        assert result.exit_code == 0
        assert "identical" in result.stdout.lower()

    def test_diff_missing_target(self, sample_delta_table: str) -> None:
        """Test diff command without target."""
        result = runner.invoke(app, ["diff", sample_delta_table])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_diff_invalid_source(self) -> None:
        """Test diff command with invalid source."""
        result = runner.invoke(app, ["diff", "/nonexistent/path", "/other/path"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_schema_list_with_partition_columns(self, tmp_path: Path) -> None:
        """Test schema list displays partition columns."""
        import pyarrow as pa
        from deltalake import write_deltalake

        # Create partitioned table
        table_path = tmp_path / "partitioned_table"
        schema = pa.schema(
            [
                pa.field("id", pa.int64(), nullable=False),
                pa.field("region", pa.string(), nullable=True),
            ]
        )
        data = pa.table({"id": [1], "region": ["US"]}, schema=schema)
        write_deltalake(str(table_path), data, mode="overwrite", partition_by=["region"])

        result = runner.invoke(app, ["schema", "list", str(table_path)])

        assert result.exit_code == 0
        assert "Partition columns" in result.stdout or "region" in result.stdout

    def test_schema_extract_fabric_hydrate_error(self) -> None:
        """Test schema extract handles FabricHydrateError."""
        result = runner.invoke(app, ["schema", "extract", "/invalid/delta/path"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_schema_extract_unexpected_error(self, sample_delta_table: str) -> None:
        """Test schema extract handles unexpected errors with exit code 2."""
        from unittest.mock import patch

        # Mock the reader to raise an unexpected error (not FabricHydrateError)
        with patch("fabric_hydrate.delta_reader.DeltaSchemaReader.read_schema") as mock_read:
            mock_read.side_effect = RuntimeError("Unexpected error")

            result = runner.invoke(app, ["schema", "extract", sample_delta_table])

            assert result.exit_code == 2
            assert "Unexpected error" in result.stdout

    def test_diff_with_fabric_params(self, sample_delta_table: str) -> None:
        """Test diff command with workspace/lakehouse params instead of target."""
        # This will fail because the OneLake URI won't be accessible,
        # but it exercises the code path
        result = runner.invoke(
            app,
            [
                "diff",
                sample_delta_table,
                "--workspace-id",
                "ws-123",
                "--lakehouse-id",
                "lh-456",
                "--table",
                "my_table",
            ],
        )

        # Will fail to connect to OneLake but exercises the code path
        assert result.exit_code == 1
        assert "Error" in result.stdout

"""CLI interface for Fabric Hydrate."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fabric_hydrate import __version__
from fabric_hydrate.exceptions import FabricHydrateError
from fabric_hydrate.logging import setup_logging

app = typer.Typer(
    name="fabric-hydrate",
    help="Extract, compare, and hydrate Microsoft Fabric Lakehouse metadata from Delta Lake schemas.",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
schema_app = typer.Typer(help="Schema extraction and manipulation commands.")
app.add_typer(schema_app, name="schema")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold blue]fabric-hydrate[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Enable verbose logging output.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug logging output.",
        ),
    ] = False,
) -> None:
    """Fabric Lakehouse Metadata Hydrator CLI."""
    if debug:
        setup_logging("DEBUG")
    elif verbose:
        setup_logging("INFO")
    else:
        setup_logging("WARNING")


@schema_app.command("extract")
def schema_extract(
    source: Annotated[
        str,
        typer.Argument(help="Path to Delta table (local path or OneLake URI)"),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (default: stdout)",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format (json or yaml)",
        ),
    ] = "json",
) -> None:
    """Extract schema from a Delta Lake table."""
    from fabric_hydrate.delta_reader import DeltaSchemaReader

    try:
        reader = DeltaSchemaReader()
        metadata = reader.read_schema(source)

        if format == "json":
            output_str = metadata.model_dump_json(indent=2)
        else:
            import yaml

            output_str = yaml.dump(metadata.model_dump(), default_flow_style=False)

        if output:
            output.write_text(output_str)
            console.print(f"[green]✓[/green] Schema written to {output}")
        else:
            console.print(output_str)

    except FabricHydrateError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=2) from e


@schema_app.command("list")
def schema_list(
    source: Annotated[
        str,
        typer.Argument(help="Path to Delta table (local path or OneLake URI)"),
    ],
) -> None:
    """List columns in a Delta Lake table schema."""
    from fabric_hydrate.delta_reader import DeltaSchemaReader

    try:
        reader = DeltaSchemaReader()
        metadata = reader.read_schema(source)

        table = Table(title=f"Schema: {metadata.name}")
        table.add_column("Column", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Nullable", style="yellow")
        table.add_column("Description", style="dim")

        for col in metadata.columns:
            table.add_row(
                col.name,
                col.type,
                "Yes" if col.nullable else "No",
                col.description or "",
            )

        console.print(table)

        if metadata.partition_columns:
            console.print(
                f"\n[bold]Partition columns:[/bold] {', '.join(metadata.partition_columns)}"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command("diff")
def diff_command(
    source: Annotated[
        str,
        typer.Argument(help="Source Delta table path"),
    ],
    target: Annotated[
        str | None,
        typer.Argument(help="Target Delta table path (or use --workspace-id)"),
    ] = None,
    workspace_id: Annotated[
        str | None,
        typer.Option("--workspace-id", "-w", help="Fabric workspace ID"),
    ] = None,
    lakehouse_id: Annotated[
        str | None,
        typer.Option("--lakehouse-id", "-l", help="Fabric lakehouse ID"),
    ] = None,
    table_name: Annotated[
        str | None,
        typer.Option("--table", "-t", help="Target table name in Fabric"),
    ] = None,
) -> None:
    """Compare schema between source and target Delta tables."""
    from fabric_hydrate.delta_reader import DeltaSchemaReader
    from fabric_hydrate.diff_engine import SchemaDiffEngine

    try:
        reader = DeltaSchemaReader()
        diff_engine = SchemaDiffEngine()

        source_metadata = reader.read_schema(source)

        if target:
            target_metadata = reader.read_schema(target)
        elif workspace_id and lakehouse_id and table_name:
            # Build OneLake URI
            target_uri = (
                f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
                f"{lakehouse_id}.Lakehouse/Tables/{table_name}"
            )
            target_metadata = reader.read_schema(target_uri)
        else:
            msg = (
                "[red]Error:[/red] Provide either a target path or "
                "--workspace-id, --lakehouse-id, and --table"
            )
            console.print(msg)
            raise typer.Exit(code=1) from None

        result = diff_engine.compare(source_metadata, target_metadata)

        if result.has_differences:
            console.print(f"[yellow]⚠[/yellow] Differences found in {result.table_name}:\n")

            diff_table = Table(title="Schema Differences")
            diff_table.add_column("Column", style="cyan")
            diff_table.add_column("Change", style="yellow")
            diff_table.add_column("Details", style="white")

            for diff in result.column_diffs:
                diff_table.add_row(diff.column_name, diff.diff_type.value, diff.message)

            console.print(diff_table)
        else:
            console.print("[green]✓[/green] Schemas are identical")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command("validate")
def validate_command(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to configuration file"),
    ],
) -> None:
    """Validate a fabric-hydrate configuration file."""
    from fabric_hydrate.models import FabricConfig

    try:
        if not config_path.exists():
            console.print(f"[red]Error:[/red] Config file not found: {config_path}")
            raise typer.Exit(code=1) from None

        config = FabricConfig.from_yaml(str(config_path))

        console.print("[green]✓[/green] Configuration is valid\n")
        console.print(f"[bold]Workspace ID:[/bold] {config.workspace_id or 'Not set'}")
        console.print(f"[bold]Lakehouse ID:[/bold] {config.lakehouse_id or 'Not set'}")
        console.print(f"[bold]Tables:[/bold] {len(config.tables)}")

        if config.tables:
            table = Table(title="Configured Tables")
            table.add_column("Name", style="cyan")
            table.add_column("Source", style="green")

            for t in config.tables:
                table.add_row(t.name, t.source)

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command("hydrate")
def hydrate_command(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to configuration file"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Source Delta table path"),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for metadata files"),
    ] = Path("./metadata"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing files"),
    ] = False,
) -> None:
    """Extract and generate metadata from Delta Lake tables."""
    from fabric_hydrate.delta_reader import DeltaSchemaReader
    from fabric_hydrate.metadata_generator import FabricMetadataGenerator
    from fabric_hydrate.models import FabricConfig

    try:
        reader = DeltaSchemaReader()
        generator = FabricMetadataGenerator()

        tables_to_process: list[tuple[str, str]] = []

        if config_path:
            config = FabricConfig.from_yaml(str(config_path))
            for table_config in config.tables:
                tables_to_process.append((table_config.name, table_config.source))
            output_dir = Path(config.output.path)
        elif source:
            # Infer table name from path
            table_name = Path(source).name.replace(".Lakehouse", "")
            tables_to_process.append((table_name, source))
        else:
            console.print("[red]Error:[/red] Provide either --config or --source")
            raise typer.Exit(code=1) from None

        if dry_run:
            console.print("[yellow]DRY RUN[/yellow] - No files will be written\n")

        for table_name, table_source in tables_to_process:
            console.print(f"Processing [cyan]{table_name}[/cyan]...")

            metadata = reader.read_schema(table_source)
            fabric_metadata = generator.generate(metadata)

            if dry_run:
                console.print(fabric_metadata.model_dump_json(indent=2))
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"{table_name}.json"
                output_file.write_text(fabric_metadata.model_dump_json(indent=2))
                console.print(f"  [green]✓[/green] Written to {output_file}")

        console.print(f"\n[green]✓[/green] Processed {len(tables_to_process)} table(s)")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()

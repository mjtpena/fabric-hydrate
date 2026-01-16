"""Test configuration and fixtures."""

import os
from collections.abc import Generator
from pathlib import Path

import pyarrow as pa
import pytest
from deltalake import write_deltalake

from fabric_hydrate.models import ColumnSchema, TableMetadata


@pytest.fixture
def sample_table_metadata() -> TableMetadata:
    """Create sample table metadata for testing."""
    return TableMetadata(
        name="test_table",
        location="/path/to/test_table",
        columns=[
            ColumnSchema(name="id", type="long", nullable=False),
            ColumnSchema(name="name", type="string", nullable=True),
            ColumnSchema(name="email", type="string", nullable=True),
            ColumnSchema(name="created_at", type="timestamp", nullable=False),
            ColumnSchema(name="price", type="decimal(10,2)", nullable=True),
        ],
        partition_columns=["created_at"],
        properties={"delta.minReaderVersion": "1"},
        description="Test table",
        delta_version=5,
    )


@pytest.fixture
def sample_delta_table(tmp_path: Path) -> Generator[str, None, None]:
    """Create a sample Delta Lake table for testing."""
    table_path = tmp_path / "delta_table"

    # Create sample data with PyArrow
    schema = pa.schema(
        [
            pa.field("id", pa.int64(), nullable=False),
            pa.field("name", pa.string(), nullable=True),
            pa.field("email", pa.string(), nullable=True),
            pa.field("created_at", pa.timestamp("us"), nullable=False),
            pa.field("amount", pa.float64(), nullable=True),
        ]
    )

    data = pa.table(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "email": ["alice@test.com", "bob@test.com", None],
            "created_at": [
                pa.scalar(1704067200000000, type=pa.timestamp("us")),
                pa.scalar(1704153600000000, type=pa.timestamp("us")),
                pa.scalar(1704240000000000, type=pa.timestamp("us")),
            ],
            "amount": [100.50, 200.75, None],
        },
        schema=schema,
    )

    write_deltalake(str(table_path), data, mode="overwrite")

    yield str(table_path)


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Generator[str, None, None]:
    """Create a sample configuration file for testing."""
    config = {
        "workspace_id": "test-workspace-id",
        "lakehouse_id": "test-lakehouse-id",
        "tables": [
            {"name": "customers", "source": "./data/customers"},
            {"name": "orders", "source": "./data/orders"},
        ],
        "output": {"format": "json", "path": "./metadata"},
    }

    config_path = tmp_path / "fabric-hydrate.yaml"

    import yaml

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    yield str(config_path)


@pytest.fixture
def mock_env_vars() -> Generator[None, None, None]:
    """Set mock environment variables for testing."""
    original_env = os.environ.copy()

    os.environ["AZURE_CLIENT_ID"] = "test-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "test-client-secret"
    os.environ["AZURE_TENANT_ID"] = "test-tenant-id"

    yield

    os.environ.clear()
    os.environ.update(original_env)

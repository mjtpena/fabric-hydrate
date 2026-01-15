"""Fabric Lakehouse Metadata Hydrator.

A CLI tool to extract, compare, and hydrate Microsoft Fabric Lakehouse
metadata from Delta Lake table schemas.
"""

__version__ = "0.1.0"

from fabric_hydrate.delta_reader import DeltaSchemaReader, read_delta_schema
from fabric_hydrate.diff_engine import SchemaDiffEngine
from fabric_hydrate.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DeltaTableError,
    FabricAPIError,
    FabricHydrateError,
    RateLimitError,
    ResourceNotFoundError,
    SchemaReadError,
    ValidationError,
)
from fabric_hydrate.fabric_client import (
    FabricAPIClient,
    FabricClientConfig,
    FabricLakehouseInfo,
    FabricTable,
    FabricWorkspace,
    async_fabric_client,
    fabric_client,
)
from fabric_hydrate.logging import get_logger, setup_logging
from fabric_hydrate.metadata_generator import (
    FabricColumnMetadata,
    FabricMetadataGenerator,
    FabricTableMetadata,
)
from fabric_hydrate.models import (
    ColumnDiff,
    ColumnSchema,
    DiffResult,
    DiffType,
    FabricConfig,
    TableMetadata,
)
from fabric_hydrate.retry import RetryConfig, async_retry, retry

__all__ = [
    # Version
    "__version__",
    # Core classes
    "DeltaSchemaReader",
    "SchemaDiffEngine",
    "FabricMetadataGenerator",
    "FabricAPIClient",
    # Models
    "ColumnSchema",
    "TableMetadata",
    "DiffResult",
    "DiffType",
    "ColumnDiff",
    "FabricConfig",
    "FabricTable",
    "FabricLakehouseInfo",
    "FabricWorkspace",
    "FabricClientConfig",
    "FabricColumnMetadata",
    "FabricTableMetadata",
    # Exceptions
    "FabricHydrateError",
    "ConfigurationError",
    "AuthenticationError",
    "DeltaTableError",
    "SchemaReadError",
    "FabricAPIError",
    "RateLimitError",
    "ResourceNotFoundError",
    "ValidationError",
    # Utilities
    "setup_logging",
    "get_logger",
    "RetryConfig",
    "retry",
    "async_retry",
    "fabric_client",
    "async_fabric_client",
    "read_delta_schema",
]

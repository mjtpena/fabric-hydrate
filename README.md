# Fabric Lakehouse Metadata Hydrator

[![CI](https://github.com/mjtpena/fabric-hydrate/actions/workflows/ci.yml/badge.svg)](https://github.com/mjtpena/fabric-hydrate/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/fabric-hydrate.svg)](https://badge.fury.io/py/fabric-hydrate)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready CLI tool to extract, compare, and hydrate Microsoft Fabric Lakehouse metadata from Delta Lake table schemas.

## 🎯 Purpose

Microsoft Fabric's REST API provides table-level metadata but doesn't expose column-level schema information. This tool bridges that gap by:

1. **Reading Delta Lake schemas** directly from OneLake/ADLS storage
2. **Generating Fabric-compatible metadata** JSON for documentation and validation
3. **Comparing schemas** between source Delta tables and target Fabric workspaces
4. **Enabling CI/CD workflows** via GitHub Actions integration

## ✨ Features

- **Delta Lake Schema Extraction** - Read schemas from local paths or OneLake (ABFSS)
- **Fabric Metadata Generation** - Convert Delta schemas to Fabric-compatible format
- **Schema Diff Engine** - Compare schemas and detect additions, removals, type changes
- **REST API Client** - Full async support with retry logic and rate limiting
- **Production Ready** - Comprehensive error handling, logging, and retry mechanisms
- **GitHub Actions** - Ready-to-use action for CI/CD pipelines
- **Type Safety** - Full type hints with PEP 561 py.typed marker

## 📦 Installation

```bash
pip install fabric-hydrate
```

For development:

```bash
pip install -e ".[dev]"
```

## 🚀 Quick Start

### Extract Schema from Local Delta Table

```bash
fabric-hydrate schema extract ./path/to/delta/table
```

### Extract Schema from OneLake

```bash
fabric-hydrate schema extract "abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/my_table"
```

### Compare Schemas (Diff)

```bash
fabric-hydrate diff ./local/table --workspace-id <id> --lakehouse-id <id>
```

### Validate Configuration

```bash
fabric-hydrate validate config.yaml
```

## ⚙️ Configuration

Create a `fabric-hydrate.yaml` configuration file:

```yaml
# fabric-hydrate.yaml
workspace_id: "your-workspace-guid"
lakehouse_id: "your-lakehouse-guid"

tables:
  - name: customers
    source: "./data/customers"
  - name: orders
    source: "abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/orders"

output:
  format: json  # or yaml
  path: "./metadata"
```

## 🔐 Authentication

### Interactive (Development)

```bash
az login
fabric-hydrate schema extract <path>
```

### Service Principal (CI/CD)

Set environment variables:

```bash
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

Then run commands as usual - the tool will automatically use service principal authentication.

## 🔧 CI/CD Integration

### GitHub Actions

```yaml
- name: Hydrate Fabric Metadata
  uses: mjtpena/fabric-hydrate@v1
  with:
    workspace-id: ${{ secrets.FABRIC_WORKSPACE_ID }}
    lakehouse-id: ${{ secrets.FABRIC_LAKEHOUSE_ID }}
    config-path: ./fabric-hydrate.yaml
    dry-run: true
```

### Azure DevOps Pipelines

Use the reusable template or run directly:

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      pip install fabric-hydrate
      fabric-hydrate hydrate --config fabric-hydrate.yaml --output ./metadata
    displayName: 'Run Fabric Hydrate'
    env:
      AZURE_CLIENT_ID: $(AZURE_CLIENT_ID)
      AZURE_CLIENT_SECRET: $(AZURE_CLIENT_SECRET)
      AZURE_TENANT_ID: $(AZURE_TENANT_ID)

  - publish: ./metadata
    artifact: 'fabric-metadata'
```

Or use the provided template from `azure-devops/templates/fabric-hydrate.yml`:

```yaml
steps:
  - template: azure-devops/templates/fabric-hydrate.yml
    parameters:
      command: 'hydrate'
      configPath: 'fabric-hydrate.yaml'
      workspaceId: '$(FABRIC_WORKSPACE_ID)'
      lakehouseId: '$(FABRIC_LAKEHOUSE_ID)'
```

See [Azure DevOps README](azure-devops/README.md) for full documentation including the Azure DevOps Marketplace extension.

## 🏭 Production Features

### Logging

Enable verbose or debug logging:

```bash
# Verbose output
fabric-hydrate --verbose schema extract ./data/table

# Debug logging
fabric-hydrate --debug schema extract ./data/table
```

### JSON Logging (for log aggregation)

```python
from fabric_hydrate.logging import setup_logging

# Enable JSON logging for production
logger = setup_logging(level="INFO", json_format=True)
```

### Retry Logic

The Fabric API client includes automatic retry with exponential backoff:

```python
from fabric_hydrate.retry import RetryConfig, retry
from fabric_hydrate.fabric_client import FabricAPIClient

# Custom retry configuration
config = RetryConfig(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    jitter=True
)
```

### Async Support

For high-performance workloads:

```python
from fabric_hydrate.fabric_client import FabricAPIClient

async with FabricAPIClient(workspace_id="...", lakehouse_id="...") as client:
    tables = await client.async_list_tables()
    for table in tables:
        metadata = await client.async_get_table_metadata(table.name)
```

### Custom Exception Handling

```python
from fabric_hydrate.exceptions import (
    FabricAPIError,
    RateLimitError,
    AuthenticationError,
    DeltaTableError,
)

try:
    schema = reader.read_schema("./path/to/table")
except DeltaTableError as e:
    logger.error(f"Failed to read Delta table: {e}")
except FabricAPIError as e:
    if e.status_code == 429:
        logger.warning(f"Rate limited, retry after {e.retry_after}s")
```

## �📊 Output Example

```json
{
  "table_name": "customers",
  "schema": {
    "fields": [
      {
        "name": "customer_id",
        "type": "long",
        "nullable": false,
        "metadata": {}
      },
      {
        "name": "email",
        "type": "string",
        "nullable": true,
        "metadata": {}
      }
    ]
  },
  "partition_columns": ["region"],
  "properties": {
    "delta.minReaderVersion": "1",
    "delta.minWriterVersion": "2"
  }
}
```

## 🛠️ Development

### Setup

```bash
git clone https://github.com/mjtpena/fabric-hydrate.git
cd fabric-hydrate
pip install -e ".[dev]"
pre-commit install
```

### Run Tests

```bash
pytest
```

### Linting

```bash
ruff check .
ruff format .
mypy src/
```

## � Architecture

```
src/fabric_hydrate/
├── __init__.py          # Package exports
├── cli.py               # Typer CLI commands
├── delta_reader.py      # Delta Lake schema extraction
├── diff_engine.py       # Schema comparison engine
├── exceptions.py        # Custom exception hierarchy
├── fabric_client.py     # Fabric REST API client (async + sync)
├── logging.py           # Structured logging configuration
├── metadata_generator.py # Fabric metadata conversion
├── models.py            # Pydantic data models
├── retry.py             # Retry with exponential backoff
└── py.typed             # PEP 561 type marker
```

## 🔒 Security

- Supports Azure CLI, Service Principal, and Managed Identity authentication
- Never logs sensitive credentials
- Uses httpx with secure defaults

## �📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

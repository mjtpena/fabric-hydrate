# Azure DevOps Extension for Fabric Hydrate

This directory contains the Azure DevOps extension for Fabric Lakehouse Metadata Hydrator.

## Building the Extension

### Prerequisites
- Node.js 16+
- Azure DevOps Extension CLI (`tfx-cli`)

### Build Steps

```bash
# Install tfx-cli globally
npm install -g tfx-cli

# Navigate to the task directory
cd azure-devops/tasks/fabric-hydrate

# Install dependencies
npm install

# Go back to extension root
cd ../..

# Create the extension package
tfx extension create --manifest-globs vss-extension.json
```

## Publishing to Azure DevOps Marketplace

1. Create a publisher at https://marketplace.visualstudio.com/manage/createpublisher
2. Update the `publisher` field in `vss-extension.json` with your publisher ID
3. Generate a Personal Access Token (PAT) with Marketplace (Publish) scope
4. Run:
   ```bash
   tfx extension publish --manifest-globs vss-extension.json --token <your-pat>
   ```

## Using in Azure Pipelines

### YAML Pipeline Example

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'
      addToPath: true

  - task: FabricHydrate@1
    displayName: 'Hydrate Fabric Lakehouse Metadata'
    inputs:
      command: 'hydrate'
      authType: 'servicePrincipal'
      azureSubscription: 'your-service-connection'
      workspaceId: '$(FABRIC_WORKSPACE_ID)'
      lakehouseId: '$(FABRIC_LAKEHOUSE_ID)'
      configPath: '$(Build.SourcesDirectory)/fabric-hydrate.yaml'
      outputPath: '$(Build.ArtifactStagingDirectory)/metadata'
      outputFormat: 'yaml'
```

### Classic Pipeline

The task is also available in the classic pipeline editor under the "Utility" category.

## Task Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `command` | Command to run (hydrate, diff, validate, schema) | Yes | hydrate |
| `authType` | Authentication type | Yes | servicePrincipal |
| `azureSubscription` | Azure service connection | No | - |
| `workspaceId` | Fabric Workspace ID | No | - |
| `lakehouseId` | Fabric Lakehouse ID | No | - |
| `configPath` | Path to config file | No | - |
| `sourcePath` | Source Delta table path | No | - |
| `outputPath` | Output directory | No | $(Build.ArtifactStagingDirectory)/metadata |
| `outputFormat` | Output format (yaml/json) | No | yaml |
| `dryRun` | Preview without writing | No | false |
| `verbose` | Enable verbose logging | No | false |

## Output Variables

| Variable | Description |
|----------|-------------|
| `MetadataPath` | Path to generated metadata files |
| `HasChanges` | Whether schema changes were detected |
| `DiffSummary` | Summary of detected differences |

## Alternative: Direct Script Usage

If you prefer not to use the extension, you can run fabric-hydrate directly:

```yaml
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
```

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

### Added
- Initial release of Fabric Lakehouse Metadata Hydrator
- CLI commands: `schema extract`, `diff`, `validate`, `hydrate`
- Delta Lake schema extraction from local paths and OneLake (ABFSS)
- Fabric REST API client with async support and retry logic
- Schema diff engine for detecting additions, removals, and type changes
- Metadata generation in YAML and JSON formats
- GitHub Action for CI/CD integration
- Azure DevOps Pipeline templates and extension
- Comprehensive test suite (184 tests, 99% coverage)
- Support for multiple authentication methods:
  - Azure CLI (interactive)
  - Service Principal
  - Managed Identity
  - Default Azure Credential chain

### Security
- Automatic retry with exponential backoff for rate limiting
- Secure credential handling via Azure Identity SDK

[1.0.0]: https://github.com/mjtpena/fabric-hydrate/releases/tag/v1.0.0

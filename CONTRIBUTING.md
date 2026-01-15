# Contributing to Fabric Hydrate

Thank you for your interest in contributing to Fabric Hydrate! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/mjtpena/fabric-hydrate.git
   cd fabric-hydrate
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Code Style

This project uses:
- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Pytest** for testing

Run the following before submitting a PR:

```bash
# Linting
ruff check .
ruff format .

# Type checking
mypy src/

# Tests
pytest
```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with appropriate tests
3. Ensure all tests pass and linting is clean
4. Update documentation if needed
5. Submit a pull request with a clear description

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs

## Code of Conduct

Be respectful and inclusive. We welcome contributions from everyone.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

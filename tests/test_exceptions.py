"""Tests for exceptions module."""

import pytest

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


class TestFabricHydrateError:
    """Tests for base exception class."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = FabricHydrateError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details is None

    def test_error_with_details(self) -> None:
        """Test error with details."""
        error = FabricHydrateError("Test error", "Additional details")
        assert str(error) == "Test error: Additional details"
        assert error.details == "Additional details"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error(self) -> None:
        """Test configuration error."""
        error = ConfigurationError("Missing config", "workspace_id")
        assert "Missing config" in str(error)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_authentication_error(self) -> None:
        """Test authentication error."""
        error = AuthenticationError("Auth failed", "Invalid token")
        assert "Auth failed" in str(error)
        assert "Invalid token" in str(error)


class TestDeltaTableError:
    """Tests for Delta table errors."""

    def test_delta_table_error(self) -> None:
        """Test Delta table error."""
        error = DeltaTableError("Table not found", "/path/to/table")
        assert "Table not found" in str(error)

    def test_schema_read_error(self) -> None:
        """Test schema read error."""
        error = SchemaReadError("Schema parse failed", "Invalid format")
        assert isinstance(error, DeltaTableError)
        assert "Schema parse failed" in str(error)


class TestFabricAPIError:
    """Tests for Fabric API errors."""

    def test_api_error_basic(self) -> None:
        """Test basic API error."""
        error = FabricAPIError("API call failed")
        assert str(error) == "API call failed"
        assert error.status_code is None

    def test_api_error_with_status(self) -> None:
        """Test API error with status code."""
        error = FabricAPIError("API call failed", status_code=500, response_body="Internal error")
        assert error.status_code == 500
        assert "HTTP 500" in str(error)

    def test_rate_limit_error(self) -> None:
        """Test rate limit error."""
        error = RateLimitError(retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60
        assert "60 seconds" in str(error)

    def test_rate_limit_error_no_retry(self) -> None:
        """Test rate limit error without retry-after."""
        error = RateLimitError()
        assert error.retry_after is None
        assert "rate limit" in str(error).lower()

    def test_resource_not_found_error(self) -> None:
        """Test resource not found error."""
        error = ResourceNotFoundError("Lakehouse", "12345")
        assert error.status_code == 404
        assert "Lakehouse" in str(error)
        assert "12345" in str(error)


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_basic(self) -> None:
        """Test basic validation error."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert error.field is None

    def test_validation_error_with_field(self) -> None:
        """Test validation error with field."""
        error = ValidationError("Required field missing", field="workspace_id")
        assert error.field == "workspace_id"
        assert "workspace_id" in str(error)


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_all_errors_inherit_from_base(self) -> None:
        """Test all errors inherit from FabricHydrateError."""
        errors = [
            ConfigurationError("test"),
            AuthenticationError("test"),
            DeltaTableError("test"),
            SchemaReadError("test"),
            FabricAPIError("test"),
            RateLimitError(),
            ResourceNotFoundError("type", "id"),
            ValidationError("test"),
        ]

        for error in errors:
            assert isinstance(error, FabricHydrateError)

    def test_api_errors_inherit_from_fabric_api_error(self) -> None:
        """Test API errors inherit from FabricAPIError."""
        errors = [
            RateLimitError(),
            ResourceNotFoundError("type", "id"),
        ]

        for error in errors:
            assert isinstance(error, FabricAPIError)

    def test_can_catch_by_base_class(self) -> None:
        """Test catching by base class works."""
        with pytest.raises(FabricHydrateError):
            raise ConfigurationError("test")

        with pytest.raises(FabricAPIError):
            raise RateLimitError()

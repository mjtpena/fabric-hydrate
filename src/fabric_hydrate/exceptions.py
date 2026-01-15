"""Custom exceptions for Fabric Hydrate."""

from __future__ import annotations


class FabricHydrateError(Exception):
    """Base exception for all Fabric Hydrate errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(FabricHydrateError):
    """Raised when configuration is invalid or missing."""

    pass


class AuthenticationError(FabricHydrateError):
    """Raised when authentication fails."""

    pass


class DeltaTableError(FabricHydrateError):
    """Raised when Delta table operations fail."""

    pass


class SchemaReadError(DeltaTableError):
    """Raised when schema cannot be read from Delta table."""

    pass


class FabricAPIError(FabricHydrateError):
    """Raised when Fabric API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        details = None
        if status_code:
            details = f"HTTP {status_code}"
            if response_body:
                details += f" - {response_body[:200]}"
        super().__init__(message, details)


class RateLimitError(FabricAPIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        message = "API rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message, status_code=429)


class ResourceNotFoundError(FabricAPIError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            status_code=404,
        )


class ValidationError(FabricHydrateError):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        details = f"field '{field}'" if field else None
        super().__init__(message, details)

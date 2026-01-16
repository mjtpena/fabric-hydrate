"""Fabric REST API client module with production-ready features."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import httpx
from azure.identity import (
    AzureCliCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
)
from pydantic import BaseModel, Field

from fabric_hydrate.exceptions import (
    AuthenticationError,
    FabricAPIError,
    RateLimitError,
    ResourceNotFoundError,
)
from fabric_hydrate.logging import get_logger
from fabric_hydrate.retry import RetryConfig, async_retry, retry

logger = get_logger("fabric_client")


class FabricTable(BaseModel):
    """Fabric table metadata from API."""

    name: str = Field(..., description="Table name")
    type: str = Field(..., description="Table type")
    location: str = Field(..., description="Table location URI")
    format: str = Field(..., description="Table format (e.g., delta)")


class FabricLakehouseInfo(BaseModel):
    """Fabric lakehouse information."""

    id: str = Field(..., description="Lakehouse ID")
    displayName: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Description")
    workspaceId: str = Field(..., description="Parent workspace ID")


class FabricWorkspace(BaseModel):
    """Fabric workspace information."""

    id: str = Field(..., description="Workspace ID")
    displayName: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Description")
    type: str = Field(..., description="Workspace type")


class FabricClientConfig(BaseModel):
    """Configuration for Fabric API client."""

    base_url: str = Field(
        default="https://api.fabric.microsoft.com/v1",
        description="Fabric API base URL",
    )
    scope: str = Field(
        default="https://api.fabric.microsoft.com/.default",
        description="OAuth scope for authentication",
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_base_delay: float = Field(default=1.0, description="Base retry delay in seconds")


class FabricAPIClient:
    """Client for Microsoft Fabric REST API with production features.

    Features:
    - Automatic token refresh
    - Retry with exponential backoff
    - Rate limit handling
    - Connection pooling
    - Comprehensive error handling
    - Both sync and async support
    """

    def __init__(
        self,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
        credential: Any | None = None,
        config: FabricClientConfig | None = None,
    ) -> None:
        """Initialize the Fabric API client.

        Args:
            workspace_id: Default workspace ID for operations.
            lakehouse_id: Default lakehouse ID for operations.
            credential: Azure credential object. If None, will auto-detect.
            config: Client configuration. Uses defaults if not provided.
        """
        self.workspace_id = workspace_id or os.environ.get("FABRIC_WORKSPACE_ID")
        self.lakehouse_id = lakehouse_id or os.environ.get("FABRIC_LAKEHOUSE_ID")
        self.config = config or FabricClientConfig()
        self._credential = credential or self._get_credential()
        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None
        self._token_cache: dict[str, Any] = {}

        self._retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_base_delay,
        )

        logger.debug(
            f"Initialized FabricAPIClient for workspace={workspace_id}, lakehouse={lakehouse_id}"
        )

    def _get_credential(
        self,
    ) -> ClientSecretCredential | AzureCliCredential | DefaultAzureCredential:
        """Get Azure credential based on environment.

        Returns:
            Azure credential object.

        Raises:
            AuthenticationError: If no valid credentials found.
        """
        # Check for service principal environment variables
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        tenant_id = os.environ.get("AZURE_TENANT_ID")

        if client_id and client_secret and tenant_id:
            logger.info("Using service principal authentication")
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

        # Try Azure CLI credentials first (common in dev)
        try:
            cli_cred = AzureCliCredential()
            cli_cred.get_token(self.config.scope)
            logger.info("Using Azure CLI authentication")
            return cli_cred
        except Exception as e:
            logger.debug(f"Azure CLI auth not available: {e}")

        # Fall back to default credential chain
        try:
            default_cred = DefaultAzureCredential()
            default_cred.get_token(self.config.scope)
            logger.info("Using default Azure credential chain")
            return default_cred
        except Exception as e:
            raise AuthenticationError(
                "Failed to obtain Azure credentials",
                str(e),
            ) from e

    def _get_token(self) -> str:
        """Get access token for Fabric API with caching.

        Returns:
            Access token string.

        Raises:
            AuthenticationError: If token acquisition fails.
        """
        try:
            token = self._credential.get_token(self.config.scope)
            return str(token.token)
        except Exception as e:
            raise AuthenticationError(
                "Failed to acquire access token",
                str(e),
            ) from e

    @property
    def client(self) -> httpx.Client:
        """Get or create synchronous HTTP client.

        Returns:
            HTTPX client instance.
        """
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                ),
            )
        return self._client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client.

        Returns:
            Async HTTPX client instance.
        """
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                ),
            )
        return self._async_client

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication.

        Returns:
            Headers dictionary.
        """
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "User-Agent": "fabric-hydrate/0.1.0",
        }

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate errors.

        Args:
            response: HTTP response object.

        Returns:
            Parsed JSON response.

        Raises:
            RateLimitError: If rate limited.
            ResourceNotFoundError: If resource not found.
            FabricAPIError: For other API errors.
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(int(retry_after) if retry_after else None)

        if response.status_code == 404:
            raise ResourceNotFoundError("Resource", str(response.url.path))

        if response.status_code >= 400:
            raise FabricAPIError(
                f"API request failed: {response.url.path}",
                status_code=response.status_code,
                response_body=response.text,
            )

        if response.status_code == 204:
            return {}

        result: dict[str, Any] = response.json()
        return result

    @retry()
    def list_tables(
        self,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ) -> list[FabricTable]:
        """List tables in a lakehouse.

        Args:
            workspace_id: Workspace ID (uses default if not provided).
            lakehouse_id: Lakehouse ID (uses default if not provided).

        Returns:
            List of FabricTable objects.

        Raises:
            ValueError: If workspace_id or lakehouse_id not provided.
            FabricAPIError: If API request fails.
        """
        ws_id = workspace_id or self.workspace_id
        lh_id = lakehouse_id or self.lakehouse_id

        if not ws_id or not lh_id:
            raise ValueError("workspace_id and lakehouse_id are required")

        logger.info(f"Listing tables in lakehouse {lh_id}")

        url = f"/workspaces/{ws_id}/lakehouses/{lh_id}/tables"
        response = self.client.get(url, headers=self._get_headers())
        data = self._handle_response(response)
        tables = data.get("data", [])

        logger.debug(f"Found {len(tables)} tables")
        return [FabricTable.model_validate(t) for t in tables]

    @retry()
    def get_lakehouse(
        self,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ) -> FabricLakehouseInfo:
        """Get lakehouse information.

        Args:
            workspace_id: Workspace ID (uses default if not provided).
            lakehouse_id: Lakehouse ID (uses default if not provided).

        Returns:
            FabricLakehouseInfo object.

        Raises:
            ValueError: If workspace_id or lakehouse_id not provided.
            FabricAPIError: If API request fails.
        """
        ws_id = workspace_id or self.workspace_id
        lh_id = lakehouse_id or self.lakehouse_id

        if not ws_id or not lh_id:
            raise ValueError("workspace_id and lakehouse_id are required")

        logger.info(f"Getting lakehouse info for {lh_id}")

        url = f"/workspaces/{ws_id}/lakehouses/{lh_id}"
        response = self.client.get(url, headers=self._get_headers())
        data = self._handle_response(response)

        return FabricLakehouseInfo.model_validate(data)

    @retry()
    def list_workspaces(self) -> list[FabricWorkspace]:
        """List all accessible workspaces.

        Returns:
            List of FabricWorkspace objects.
        """
        logger.info("Listing workspaces")

        response = self.client.get("/workspaces", headers=self._get_headers())
        data = self._handle_response(response)
        workspaces = data.get("value", [])

        logger.debug(f"Found {len(workspaces)} workspaces")
        return [FabricWorkspace.model_validate(w) for w in workspaces]

    def build_onelake_uri(
        self,
        table_name: str,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ) -> str:
        """Build OneLake ABFSS URI for a table.

        Args:
            table_name: Table name.
            workspace_id: Workspace ID.
            lakehouse_id: Lakehouse ID.

        Returns:
            ABFSS URI string.
        """
        ws_id = workspace_id or self.workspace_id
        lh_id = lakehouse_id or self.lakehouse_id

        if not ws_id or not lh_id:
            raise ValueError("workspace_id and lakehouse_id are required")

        return (
            f"abfss://{ws_id}@onelake.dfs.fabric.microsoft.com/"
            f"{lh_id}.Lakehouse/Tables/{table_name}"
        )

    # Async methods
    @async_retry()
    async def list_tables_async(
        self,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ) -> list[FabricTable]:
        """Async version of list_tables."""
        ws_id = workspace_id or self.workspace_id
        lh_id = lakehouse_id or self.lakehouse_id

        if not ws_id or not lh_id:
            raise ValueError("workspace_id and lakehouse_id are required")

        logger.info(f"Listing tables in lakehouse {lh_id} (async)")

        url = f"/workspaces/{ws_id}/lakehouses/{lh_id}/tables"
        response = await self.async_client.get(url, headers=self._get_headers())
        data = self._handle_response(response)
        tables = data.get("data", [])

        return [FabricTable.model_validate(t) for t in tables]

    @async_retry()
    async def get_lakehouse_async(
        self,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ) -> FabricLakehouseInfo:
        """Async version of get_lakehouse."""
        ws_id = workspace_id or self.workspace_id
        lh_id = lakehouse_id or self.lakehouse_id

        if not ws_id or not lh_id:
            raise ValueError("workspace_id and lakehouse_id are required")

        url = f"/workspaces/{ws_id}/lakehouses/{lh_id}"
        response = await self.async_client.get(url, headers=self._get_headers())
        data = self._handle_response(response)

        return FabricLakehouseInfo.model_validate(data)

    @async_retry()
    async def list_workspaces_async(self) -> list[FabricWorkspace]:
        """Async version of list_workspaces."""
        response = await self.async_client.get("/workspaces", headers=self._get_headers())
        data = self._handle_response(response)
        workspaces = data.get("value", [])

        return [FabricWorkspace.model_validate(w) for w in workspaces]

    def health_check(self) -> bool:
        """Check if the API is accessible and credentials are valid.

        Returns:
            True if healthy, raises exception otherwise.
        """
        try:
            self._get_token()
            # Try to list workspaces as a health check
            self.list_workspaces()
            logger.info("Health check passed")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    async def health_check_async(self) -> bool:
        """Async version of health_check."""
        try:
            self._get_token()
            await self.list_workspaces_async()
            logger.info("Health check passed (async)")
            return True
        except Exception as e:
            logger.error(f"Health check failed (async): {e}")
            raise

    def close(self) -> None:
        """Close HTTP clients and release resources."""
        if self._client:
            self._client.close()
            self._client = None
        logger.debug("Closed HTTP clients")

    async def aclose(self) -> None:
        """Async close for HTTP clients."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        logger.debug("Closed HTTP clients (async)")

    def __enter__(self) -> FabricAPIClient:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        self.close()

    async def __aenter__(self) -> FabricAPIClient:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self.aclose()


@contextmanager
def fabric_client(
    workspace_id: str | None = None,
    lakehouse_id: str | None = None,
) -> Iterator[FabricAPIClient]:
    """Context manager for creating a Fabric API client.

    Args:
        workspace_id: Workspace ID.
        lakehouse_id: Lakehouse ID.

    Yields:
        Configured FabricAPIClient.
    """
    client = FabricAPIClient(workspace_id=workspace_id, lakehouse_id=lakehouse_id)
    try:
        yield client
    finally:
        client.close()


@asynccontextmanager
async def async_fabric_client(
    workspace_id: str | None = None,
    lakehouse_id: str | None = None,
) -> AsyncIterator[FabricAPIClient]:
    """Async context manager for creating a Fabric API client.

    Args:
        workspace_id: Workspace ID.
        lakehouse_id: Lakehouse ID.

    Yields:
        Configured FabricAPIClient.
    """
    client = FabricAPIClient(workspace_id=workspace_id, lakehouse_id=lakehouse_id)
    try:
        yield client
    finally:
        await client.aclose()

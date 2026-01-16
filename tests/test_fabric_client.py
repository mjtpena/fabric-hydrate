"""Comprehensive tests for fabric_client module."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fabric_hydrate.exceptions import (
    AuthenticationError,
    FabricAPIError,
    RateLimitError,
    ResourceNotFoundError,
)
from fabric_hydrate.fabric_client import (
    FabricAPIClient,
    FabricClientConfig,
    async_fabric_client,
    fabric_client,
)

# Get the actual module for patching (sys.modules ensures we get the module, not the function)
_fc_module = sys.modules["fabric_hydrate.fabric_client"]


class TestFabricClientConfig:
    """Tests for FabricClientConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = FabricClientConfig()

        assert config.base_url == "https://api.fabric.microsoft.com/v1"
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.scope == "https://api.fabric.microsoft.com/.default"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = FabricClientConfig(
            base_url="https://custom.api.com",
            timeout=60.0,
            max_retries=5,
        )

        assert config.base_url == "https://custom.api.com"
        assert config.timeout == 60.0
        assert config.max_retries == 5


class TestFabricAPIClientInit:
    """Tests for FabricAPIClient initialization."""

    @patch.dict(
        os.environ,
        {
            "FABRIC_WORKSPACE_ID": "env-ws-id",
            "FABRIC_LAKEHOUSE_ID": "env-lh-id",
        },
        clear=False,
    )
    def test_init_from_env(self) -> None:
        """Test initialization from environment variables."""
        with patch.object(FabricAPIClient, "_get_credential") as mock_cred:
            mock_cred.return_value = MagicMock()
            client = FabricAPIClient()

            assert client.workspace_id == "env-ws-id"
            assert client.lakehouse_id == "env-lh-id"

    def test_init_with_params(self) -> None:
        """Test initialization with explicit parameters."""
        mock_credential = MagicMock()
        client = FabricAPIClient(
            workspace_id="ws-123",
            lakehouse_id="lh-456",
            credential=mock_credential,
        )

        assert client.workspace_id == "ws-123"
        assert client.lakehouse_id == "lh-456"
        assert client._credential is mock_credential

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom config."""
        mock_credential = MagicMock()
        custom_config = FabricClientConfig(timeout=120.0)
        client = FabricAPIClient(
            workspace_id="ws-123",
            credential=mock_credential,
            config=custom_config,
        )

        assert client.config.timeout == 120.0


class TestFabricAPIClientCredentials:
    """Tests for credential handling."""

    @patch.dict(
        os.environ,
        {
            "AZURE_CLIENT_ID": "client-id",
            "AZURE_CLIENT_SECRET": "secret",
            "AZURE_TENANT_ID": "tenant-id",
        },
        clear=False,
    )
    @patch.object(_fc_module, "ClientSecretCredential")
    def test_service_principal_credentials(self, mock_sp_class: MagicMock) -> None:
        """Test service principal credential creation."""
        mock_sp = MagicMock()
        mock_sp_class.return_value = mock_sp

        _client = FabricAPIClient(workspace_id="ws")

        mock_sp_class.assert_called_once_with(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="secret",
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(_fc_module, "DefaultAzureCredential")
    @patch.object(_fc_module, "AzureCliCredential")
    def test_azure_cli_credential(
        self, mock_cli_class: MagicMock, _mock_default_class: MagicMock
    ) -> None:
        """Test Azure CLI credential fallback."""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        _client = FabricAPIClient(workspace_id="ws")

        mock_cli_class.assert_called_once()
        mock_cli.get_token.assert_called()

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(_fc_module, "DefaultAzureCredential")
    @patch.object(_fc_module, "AzureCliCredential")
    def test_default_credential_fallback(
        self, mock_cli_class: MagicMock, mock_default_class: MagicMock
    ) -> None:
        """Test default credential fallback when CLI fails."""
        mock_cli = MagicMock()
        mock_cli.get_token.side_effect = Exception("CLI not available")
        mock_cli_class.return_value = mock_cli

        mock_default = MagicMock()
        mock_default_class.return_value = mock_default

        _client = FabricAPIClient(workspace_id="ws")

        mock_default_class.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(_fc_module, "DefaultAzureCredential")
    @patch.object(_fc_module, "AzureCliCredential")
    def test_credential_failure(
        self, mock_cli_class: MagicMock, mock_default_class: MagicMock
    ) -> None:
        """Test authentication error when all credentials fail."""
        mock_cli = MagicMock()
        mock_cli.get_token.side_effect = Exception("CLI fail")
        mock_cli_class.return_value = mock_cli

        mock_default = MagicMock()
        mock_default.get_token.side_effect = Exception("Default fail")
        mock_default_class.return_value = mock_default

        with pytest.raises(AuthenticationError):
            FabricAPIClient(workspace_id="ws")


class TestFabricAPIClientToken:
    """Tests for token handling."""

    def test_get_token_success(self) -> None:
        """Test successful token acquisition."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test-token"
        mock_credential.get_token.return_value = mock_token

        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)
        token = client._get_token()

        assert token == "test-token"

    def test_get_token_failure(self) -> None:
        """Test token acquisition failure."""
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = Exception("Token error")

        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        with pytest.raises(AuthenticationError):
            client._get_token()


class TestFabricAPIClientHTTP:
    """Tests for HTTP client handling."""

    def test_client_property_creates_client(self) -> None:
        """Test client property creates httpx.Client."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        http_client = client.client
        assert isinstance(http_client, httpx.Client)

        # Second access should return same instance
        assert client.client is http_client

        client.close()

    def test_async_client_property_creates_client(self) -> None:
        """Test async_client property creates httpx.AsyncClient."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        async_http_client = client.async_client
        assert isinstance(async_http_client, httpx.AsyncClient)

        # Second access should return same instance
        assert client.async_client is async_http_client

    def test_get_headers(self) -> None:
        """Test headers generation."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test-token"
        mock_credential.get_token.return_value = mock_token

        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers


class TestFabricAPIClientResponseHandling:
    """Tests for response handling."""

    def test_handle_response_rate_limit(self) -> None:
        """Test rate limit response handling."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with pytest.raises(RateLimitError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.retry_after == 30

    def test_handle_response_rate_limit_no_retry_after(self) -> None:
        """Test rate limit without Retry-After header."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        with pytest.raises(RateLimitError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.retry_after is None

    def test_handle_response_not_found(self) -> None:
        """Test 404 response handling."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url.path = "/test/path"

        with pytest.raises(ResourceNotFoundError):
            client._handle_response(mock_response)

    def test_handle_response_generic_error(self) -> None:
        """Test generic error response handling."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.url.path = "/test/path"
        mock_response.text = "Server error"

        with pytest.raises(FabricAPIError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.status_code == 500

    def test_handle_response_no_content(self) -> None:
        """Test 204 No Content response handling."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 204

        result = client._handle_response(mock_response)
        assert result == {}

    def test_handle_response_success(self) -> None:
        """Test successful response handling."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        result = client._handle_response(mock_response)
        assert result == {"data": "test"}


class TestFabricAPIClientMethods:
    """Tests for API methods."""

    def test_list_tables_missing_ids(self) -> None:
        """Test list_tables raises error without IDs."""
        mock_credential = MagicMock()
        client = FabricAPIClient(credential=mock_credential)

        with pytest.raises(ValueError, match="workspace_id and lakehouse_id are required"):
            client.list_tables()

    def test_list_tables_success(self) -> None:
        """Test successful list_tables call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        # Create a proper mock response with integer status_code
        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "name": "table1",
                    "type": "Delta",
                    "location": "abfss://path/table1",
                    "format": "delta",
                },
                {
                    "name": "table2",
                    "type": "Delta",
                    "location": "abfss://path/table2",
                    "format": "delta",
                },
            ]
        }

        with patch.object(_fc_module.httpx, "Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(
                workspace_id="ws-123",
                lakehouse_id="lh-456",
                credential=mock_credential,
            )

            tables = client.list_tables()

            assert len(tables) == 2
            assert tables[0].name == "table1"

    def test_get_lakehouse_missing_ids(self) -> None:
        """Test get_lakehouse raises error without IDs."""
        mock_credential = MagicMock()
        client = FabricAPIClient(credential=mock_credential)

        with pytest.raises(ValueError):
            client.get_lakehouse()

    def test_build_onelake_uri(self) -> None:
        """Test OneLake URI building."""
        mock_credential = MagicMock()
        client = FabricAPIClient(
            workspace_id="ws-123",
            lakehouse_id="lh-456",
            credential=mock_credential,
        )

        uri = client.build_onelake_uri("my_table")

        assert uri == (
            "abfss://ws-123@onelake.dfs.fabric.microsoft.com/lh-456.Lakehouse/Tables/my_table"
        )

    def test_build_onelake_uri_missing_ids(self) -> None:
        """Test build_onelake_uri raises error without IDs."""
        mock_credential = MagicMock()
        client = FabricAPIClient(credential=mock_credential)

        with pytest.raises(ValueError):
            client.build_onelake_uri("table")


class TestFabricAPIClientContextManagers:
    """Tests for context managers."""

    def test_sync_context_manager(self) -> None:
        """Test synchronous context manager."""
        mock_credential = MagicMock()

        with FabricAPIClient(workspace_id="ws", credential=mock_credential) as client:
            assert isinstance(client, FabricAPIClient)

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test async context manager."""
        mock_credential = MagicMock()

        async with FabricAPIClient(workspace_id="ws", credential=mock_credential) as client:
            assert isinstance(client, FabricAPIClient)

    def test_fabric_client_context_manager(self) -> None:
        """Test fabric_client context manager function."""
        with patch.object(FabricAPIClient, "_get_credential") as mock_cred:
            mock_cred.return_value = MagicMock()

            with fabric_client(workspace_id="ws-123") as client:
                assert isinstance(client, FabricAPIClient)

    @pytest.mark.asyncio
    async def test_async_fabric_client_context_manager(self) -> None:
        """Test async_fabric_client context manager function."""
        with patch.object(FabricAPIClient, "_get_credential") as mock_cred:
            mock_cred.return_value = MagicMock()

            async with async_fabric_client(workspace_id="ws-123") as client:
                assert isinstance(client, FabricAPIClient)


class TestFabricAPIClientClose:
    """Tests for client cleanup."""

    def test_close(self) -> None:
        """Test close method."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        # Create client
        _ = client.client
        assert client._client is not None

        client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_aclose(self) -> None:
        """Test async close method."""
        mock_credential = MagicMock()
        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        # Create clients
        _ = client.client
        _ = client.async_client

        await client.aclose()
        assert client._client is None
        assert client._async_client is None


class TestFabricAPIClientAsync:
    """Tests for async methods."""

    @pytest.mark.asyncio
    async def test_list_tables_async_missing_ids(self) -> None:
        """Test list_tables_async raises error without IDs."""
        mock_credential = MagicMock()
        client = FabricAPIClient(credential=mock_credential)

        with pytest.raises(ValueError):
            await client.list_tables_async()

    @pytest.mark.asyncio
    async def test_get_lakehouse_async_missing_ids(self) -> None:
        """Test get_lakehouse_async raises error without IDs."""
        mock_credential = MagicMock()
        client = FabricAPIClient(credential=mock_credential)

        with pytest.raises(ValueError):
            await client.get_lakehouse_async()


class TestFabricAPIClientHealthCheck:
    """Tests for health check methods."""

    def test_health_check_success(self) -> None:
        """Test successful health check."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        with patch.object(_fc_module.httpx, "Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

            result = client.health_check()
            assert result is True

    def test_health_check_failure(self) -> None:
        """Test health check failure."""
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = Exception("Token failed")

        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        with pytest.raises(AuthenticationError):
            client.health_check()

    @pytest.mark.asyncio
    async def test_health_check_async_failure(self) -> None:
        """Test async health check failure."""
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = Exception("Token failed")

        client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

        with pytest.raises(AuthenticationError):
            await client.health_check_async()

    @pytest.mark.asyncio
    async def test_health_check_async_success(self) -> None:
        """Test successful async health check."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        with patch.object(_fc_module.httpx, "AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(workspace_id="ws", credential=mock_credential)

            result = await client.health_check_async()
            assert result is True


class TestFabricAPIClientGetLakehouse:
    """Tests for get_lakehouse methods."""

    def test_get_lakehouse_success(self) -> None:
        """Test successful get_lakehouse call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "lh-123",
            "displayName": "My Lakehouse",
            "description": "Test lakehouse",
            "workspaceId": "ws-123",
        }

        with patch.object(_fc_module.httpx, "Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(
                workspace_id="ws-123",
                lakehouse_id="lh-123",
                credential=mock_credential,
            )

            lakehouse = client.get_lakehouse()

            assert lakehouse.id == "lh-123"
            assert lakehouse.displayName == "My Lakehouse"

    def test_list_workspaces_success(self) -> None:
        """Test successful list_workspaces call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"id": "ws-1", "displayName": "Workspace 1", "type": "Workspace"},
                {"id": "ws-2", "displayName": "Workspace 2", "type": "Workspace"},
            ]
        }

        with patch.object(_fc_module.httpx, "Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(credential=mock_credential)

            workspaces = client.list_workspaces()

            assert len(workspaces) == 2
            assert workspaces[0].displayName == "Workspace 1"


class TestFabricAPIClientAsyncMethods:
    """Tests for async API methods."""

    @pytest.mark.asyncio
    async def test_list_tables_async_success(self) -> None:
        """Test successful async list_tables call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"name": "table1", "type": "Delta", "location": "path1", "format": "delta"},
            ]
        }

        with patch.object(_fc_module.httpx, "AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(
                workspace_id="ws-123",
                lakehouse_id="lh-456",
                credential=mock_credential,
            )

            tables = await client.list_tables_async()

            assert len(tables) == 1
            assert tables[0].name == "table1"

    @pytest.mark.asyncio
    async def test_get_lakehouse_async_success(self) -> None:
        """Test successful async get_lakehouse call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "lh-123",
            "displayName": "My Lakehouse",
            "description": None,
            "workspaceId": "ws-123",
        }

        with patch.object(_fc_module.httpx, "AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(
                workspace_id="ws-123",
                lakehouse_id="lh-123",
                credential=mock_credential,
            )

            lakehouse = await client.get_lakehouse_async()

            assert lakehouse.id == "lh-123"

    @pytest.mark.asyncio
    async def test_list_workspaces_async_success(self) -> None:
        """Test successful async list_workspaces call."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "token"
        mock_credential.get_token.return_value = mock_token

        mock_response = MagicMock(spec=["status_code", "json", "headers", "url", "text"])
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"id": "ws-1", "displayName": "Workspace 1", "type": "Workspace"},
            ]
        }

        with patch.object(_fc_module.httpx, "AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            client = FabricAPIClient(credential=mock_credential)

            workspaces = await client.list_workspaces_async()

            assert len(workspaces) == 1

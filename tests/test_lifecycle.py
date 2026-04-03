import pytest
from unittest.mock import AsyncMock, MagicMock

from scanner_client import EWSClient


@pytest.fixture
def mock_httpx_client():
    mock = MagicMock()
    mock.aclose = AsyncMock()
    return mock


class TestLifecycle:
    """Tests for EWSClient lifecycle (context manager and close)."""
    
    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, mock_httpx_client):
        """Test that __aenter__ returns the client instance."""
        client = EWSClient("192.168.1.100")
        client.client = mock_httpx_client
        result = await client.__aenter__()
        assert result is client
    
    @pytest.mark.asyncio
    async def test_aexit_calls_close(self, mock_httpx_client):
        """Test that __aexit__ calls close()."""
        client = EWSClient("192.168.1.100")
        client.client = mock_httpx_client
        
        # Spy on the close method
        original_close = client.close
        close_spy = AsyncMock(side_effect=original_close)
        client.close = close_spy
        
        await client.__aexit__(None, None, None)
        
        close_spy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_calls_httpx_client_aclose(self, mock_httpx_client):
        """Test that close() calls aclose on the httpx client."""
        client = EWSClient("192.168.1.100")
        client.client = mock_httpx_client
        
        await client.close()
        mock_httpx_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_httpx_client, monkeypatch):
        """Test using EWSClient as async context manager."""
        # Patch httpx.AsyncClient to return our mock
        monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: mock_httpx_client)
        
        async with EWSClient("192.168.1.100") as client:
            assert client is not None
            assert isinstance(client, EWSClient)
            assert client.base_url == "https://192.168.1.100"
        
        # After exiting, httpx client should be closed
        mock_httpx_client.aclose.assert_called_once()

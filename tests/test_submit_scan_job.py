import pytest
from unittest.mock import AsyncMock, MagicMock

from scanner_client import EWSClient


@pytest.fixture
def mock_httpx_client():
    mock = MagicMock()
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def ews_client(mock_httpx_client):
    client = EWSClient("192.168.1.100")
    client.client = mock_httpx_client
    return client


class TestSubmitScanJob:
    @pytest.mark.asyncio
    async def test_success_with_location_header(self, ews_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {'Location': 'http://192.168.1.100/eSCL/ScanJobs/12345'}
        mock_response.text = ''
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        result = await ews_client.submit_scan_job()
        
        assert result['job_id'] == '12345'
        assert result['job_url'] == 'http://192.168.1.100/eSCL/ScanJobs/12345'
        assert result['next_document_url'] == 'http://192.168.1.100/eSCL/ScanJobs/12345/NextDocument'
        assert result['status'] == 'Submitted'
    
    @pytest.mark.asyncio
    async def test_missing_location_header(self, ews_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = ''
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(ValueError, match="No Location header returned"):
            await ews_client.submit_scan_job()
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.post = AsyncMock(side_effect=Exception("HTTP error"))
        
        with pytest.raises(Exception, match="HTTP error"):
            await ews_client.submit_scan_job()

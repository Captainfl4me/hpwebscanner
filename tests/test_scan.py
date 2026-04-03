import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

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


class TestScan:
    """Tests for the EWSClient.scan() method."""
    
    @pytest.mark.asyncio
    async def test_scan_wait_for_completion_false(self, ews_client, mock_httpx_client):
        """Test that wait_for_completion=False returns immediately without downloading."""
        # Mock submit_scan_job
        job_info = {
            'job_id': 'job123',
            'job_url': 'http://192.168.1.100/eSCL/ScanJobs/job123',
            'next_document_url': 'http://192.168.1.100/eSCL/ScanJobs/job123/NextDocument',
            'status': 'Submitted'
        }
        ews_client.submit_scan_job = AsyncMock(return_value=job_info)
        
        result = await ews_client.scan('/tmp/scans', wait_for_completion=False)
        
        assert result['job_id'] == 'job123'
        assert result['job_url'] == job_info['job_url']
        assert result['status'] == 'Submitted'
        assert 'saved_path' not in result
        # Verify download_image was NOT called
        mock_httpx_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_scan_wait_for_completion_true_with_default_filename(self, ews_client, mock_httpx_client):
        """Test that wait_for_completion=True with no filename auto-generates scan_{job_id}.jpg."""
        job_info = {
            'job_id': 'job456',
            'job_url': 'http://192.168.1.100/eSCL/ScanJobs/job456',
            'next_document_url': 'http://192.168.1.100/eSCL/ScanJobs/job456/NextDocument',
            'status': 'Submitted'
        }
        ews_client.submit_scan_job = AsyncMock(return_value=job_info)
        
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await ews_client.scan(tmpdir, wait_for_completion=True)
            
            assert result['job_id'] == 'job456'
            assert result['status'] == 'Completed'
            assert result['saved_path'] == f"{tmpdir.rstrip('/')}/scan_job456.jpg"
            
            # Verify download_image was called with correct URL and path
            mock_httpx_client.get.assert_called_once_with(job_info['next_document_url'])
    
    @pytest.mark.asyncio
    async def test_scan_wait_for_completion_true_with_custom_filename(self, ews_client, mock_httpx_client):
        """Test that wait_for_completion=True uses provided filename."""
        job_info = {
            'job_id': 'job789',
            'job_url': 'http://192.168.1.100/eSCL/ScanJobs/job789',
            'next_document_url': 'http://192.168.1.100/eSCL/ScanJobs/job789/NextDocument',
            'status': 'Submitted'
        }
        ews_client.submit_scan_job = AsyncMock(return_value=job_info)
        
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_filename = "my_custom_scan.jpg"
            result = await ews_client.scan(tmpdir, filename=custom_filename, wait_for_completion=True)
            
            assert result['job_id'] == 'job789'
            assert result['status'] == 'Completed'
            assert result['saved_path'] == f"{tmpdir.rstrip('/')}/{custom_filename}"
    
    @pytest.mark.asyncio
    async def test_scan_download_failure_propagates_exception(self, ews_client, mock_httpx_client):
        """Test that if download_image fails, exception propagates from scan()."""
        job_info = {
            'job_id': 'job999',
            'job_url': 'http://192.168.1.100/eSCL/ScanJobs/job999',
            'next_document_url': 'http://192.168.1.100/eSCL/ScanJobs/job999/NextDocument',
            'status': 'Submitted'
        }
        ews_client.submit_scan_job = AsyncMock(return_value=job_info)
        ews_client.download_image = AsyncMock(side_effect=Exception("Download failed"))
        
        with pytest.raises(Exception, match="Download failed"):
            await ews_client.scan('/tmp/scans', wait_for_completion=True)
    
    @pytest.mark.asyncio
    async def test_scan_submit_failure_raises_exception(self, ews_client, mock_httpx_client):
        """Test that if submit_scan_job fails, exception propagates."""
        ews_client.submit_scan_job = AsyncMock(side_effect=ValueError("Submit failed"))
        
        with pytest.raises(ValueError, match="Submit failed"):
            await ews_client.scan('/tmp/scans', wait_for_completion=True)

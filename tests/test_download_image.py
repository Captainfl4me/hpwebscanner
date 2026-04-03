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


class TestDownloadImage:
    @pytest.mark.asyncio
    async def test_success(self, ews_client, mock_httpx_client):
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF test content"  # JPEG header
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
            
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                assert f.read() == image_content
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Download failed"))
        
        with pytest.raises(Exception), tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
    
    @pytest.mark.asyncio
    async def test_invalid_content_type(self, ews_client, mock_httpx_client):
        """Test that non-jpeg Content-Type raises ValueError."""
        image_content = b"not really an image"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            with pytest.raises(ValueError, match="Expected image/jpeg"):
                await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
    
    @pytest.mark.asyncio
    async def test_missing_content_type_raises_error(self, ews_client, mock_httpx_client):
        """Test that missing Content-Type header (empty) raises ValueError."""
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {}  # No Content-Type
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            with pytest.raises(ValueError, match="Expected image/jpeg"):
                await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
    
    @pytest.mark.asyncio
    async def test_content_type_with_charset_is_accepted(self, ews_client, mock_httpx_client):
        """Test that Content-Type 'image/jpeg; charset=utf-8' is accepted (starts_with check)."""
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF test content"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg; charset=utf-8'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            # Should not raise - content_type.startswith('image/jpeg') passes for "image/jpeg; charset=utf-8"
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
            
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                assert f.read() == image_content
    
    @pytest.mark.asyncio
    async def test_disk_full_during_write_raises_oserror(self, ews_client, mock_httpx_client, monkeypatch):
        """Test that disk full (no space) during write raises OSError."""
        image_content = b"x" * (10 * 1024 * 1024)  # 10MB content
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.jpg")
            # Mock open to simulate disk full
            original_open = open
            def mock_open(*args, **kwargs):
                # If it's the save_path in write mode, raise OS error
                if len(args) > 1 and 'w' in args[1] and args[0] == save_path:
                    raise OSError("No space left on device")
                return original_open(*args, **kwargs)
            
            import builtins
            monkeypatch.setattr(builtins, 'open', mock_open)
            
            with pytest.raises(OSError, match="No space"):
                await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
    
    @pytest.mark.asyncio
    async def test_directory_creation_failure_raises_error(self, ews_client, mock_httpx_client, tmp_path):
        """Test that failure to create directory (permission denied) raises an error."""
        image_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = image_content
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        # Create a parent directory that we can't write to (read-only)
        parent_dir = tmp_path / "readonly_parent"
        parent_dir.mkdir()
        os.chmod(parent_dir, 0o444)  # Read-only
    
        # Try to save to a path under this read-only parent
        save_path = parent_dir / "subdir" / "test.jpg"
        
        with pytest.raises(PermissionError):
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', str(save_path))

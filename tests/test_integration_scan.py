import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app, jobs


@pytest.fixture
def mock_ews(monkeypatch):
    """Create a mock EWSClient and patch it into main."""
    mock = MagicMock()
    mock.submit_scan_job = AsyncMock(return_value={
        'job_id': 'test123',
        'job_url': 'http://192.168.1.100/Scan/Jobs/test123',
        'next_document_url': 'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
        'status': 'Submitted'
    })
    mock.download_image = AsyncMock()
    mock.close = AsyncMock()  # Ensure close is awaitable
    monkeypatch.setattr('main.EWSClient', lambda ip, **kwargs: mock)
    return mock


def test_scan_endpoint_success(mock_ews):
    """Test successful scan endpoint returns job info and triggers download."""
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["job_id"] == "test123"
        assert "saved_path" in data
    
    # Verify methods were called
    mock_ews.submit_scan_job.assert_called_once()
    mock_ews.download_image.assert_called_once_with(
        'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
        '/tmp/scans/scan_test123.jpg'
    )


def test_scan_endpoint_failure(mock_ews):
    """Test that /scan returns 500 when scanner throws an exception."""
    mock_ews.submit_scan_job = AsyncMock(side_effect=Exception("Scanner error"))
    
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"


def test_scan_endpoint_download_failure(mock_ews):
    """Test that when image download fails after job submission, returns 500 and job remains in incomplete state."""
    # Override mock_ews.download_image to raise an exception
    mock_ews.download_image = AsyncMock(side_effect=Exception("Download failed"))
    
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to complete scan" in data["message"]
    
    # Job was submitted and added before download attempt, so it should exist in jobs dict
    # Mock returns job_id 'test123' by default
    assert 'test123' in jobs
    # Job status should still be "Downloading" since download never completed
    assert jobs['test123']['status'] == 'Downloading'
    assert jobs['test123']['saved_path'] is None

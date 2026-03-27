import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import os
import sys

# Ensure src is in path (should be from conftest but ensure)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Ensure environment variables are set before importing app
os.environ.setdefault("SCANNER_IP", "192.168.1.100")
os.environ.setdefault("SAVE_FOLDER", "/tmp/scans")
os.environ.setdefault("ALLOWED_IP", "")

from main import app, jobs

@pytest.fixture(autouse=True)
def mock_ews(monkeypatch):
    """Create a mock EWSClient and patch it into main."""
    mock = MagicMock()
    mock.submit_scan_job = AsyncMock(return_value={
        'job_id': 'test123',
        'job_url': 'http://192.168.1.100/Scan/Jobs/test123',
        'next_document_url': 'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
        'status': 'Submitted'
    })
    mock.download_pdf = AsyncMock()
    mock.close = AsyncMock()
    # Mock the httpx client used for health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock.client = AsyncMock()
    mock.client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr('main.EWSClient', lambda ip: mock)
    return mock

@pytest.fixture(autouse=True)
def clear_jobs():
    """Clear jobs dict before each test."""
    jobs.clear()
    yield
    jobs.clear()

def test_health_endpoint():
    """Test that health endpoint returns healthy."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

def test_scan_endpoint_success(mock_ews):
    """Test successful scan submission and immediate download."""
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["job_id"] == "test123"
        assert data["saved_path"] == "/tmp/scans/scan_test123.pdf"
        mock_ews.submit_scan_job.assert_called_once()
        # download_pdf should be called with next_document_url
        mock_ews.download_pdf.assert_called_once_with(
            'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
            '/tmp/scans/scan_test123.pdf'
        )

def test_scan_endpoint_failure(mock_ews):
    """Test scan endpoint when scanner communication fails."""
    mock_ews.submit_scan_job = AsyncMock(side_effect=Exception("Scanner error"))
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to complete scan" in data["message"]

def test_status_endpoint_after_scan(mock_ews):
    """Test that status endpoint shows completed job after immediate download."""
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Get job status - should already be completed
        response = client.get(f"/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_status"]["status"] == "Completed"
        assert data["job_status"]["saved_path"] == "/tmp/scans/scan_test123.pdf"
        
        # wait_for_completion should NOT be called (using direct download)
        mock_ews.wait_for_completion.assert_not_called()
        # download_pdf should be called with next_document_url
        mock_ews.download_pdf.assert_called_once_with(
            'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
            '/tmp/scans/scan_test123.pdf'
        )

def test_status_endpoint_unknown_job():
    """Test status endpoint with non-existent job."""
    with TestClient(app) as client:
        response = client.get("/status/unknown")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"]

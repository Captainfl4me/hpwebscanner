import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import os

# Ensure environment variables are set before importing app
os.environ.setdefault("SCANNER_IP", "192.168.1.100")
os.environ.setdefault("SAVE_FOLDER", "/tmp/scans")
os.environ.setdefault("ALLOWED_IP", "")

from src.main import app, jobs

@pytest.fixture(autouse=True)
def mock_ews(monkeypatch):
    """Create a mock EWSClient and patch it into src.main."""
    mock = MagicMock()
    mock.submit_scan_job = AsyncMock(return_value={
        'job_id': 'test123',
        'job_url': 'http://192.168.1.100/Scan/Jobs/test123',
        'status': 'Submitted'
    })
    mock.wait_for_completion = AsyncMock(return_value={
        'state': 'Completed',
        'binary_url': 'http://192.168.1.100/Scan/Binary/xyz'
    })
    mock.download_pdf = AsyncMock()
    mock.close = AsyncMock()
    # Mock the httpx client used for health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock.client = AsyncMock()
    mock.client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr('src.main.EWSClient', lambda ip: mock)
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
    """Test successful scan submission and background processing."""
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["job_id"] == "test123"
        mock_ews.submit_scan_job.assert_called_once()

def test_scan_endpoint_failure(mock_ews):
    """Test scan endpoint when scanner communication fails."""
    mock_ews.submit_scan_job = AsyncMock(side_effect=Exception("Scanner error"))
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to submit scan job" in data["message"]

def test_status_endpoint_after_scan(mock_ews):
    """Test that status endpoint shows completed job after background processing."""
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Get job status - background task should have completed
        response = client.get(f"/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_status"]["status"] == "Completed"
        assert data["job_status"]["saved_path"] == "/tmp/scans/scan_test123.pdf"
        
        mock_ews.wait_for_completion.assert_called_once()
        mock_ews.download_pdf.assert_called_once_with(
            'http://192.168.1.100/Scan/Binary/xyz',
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

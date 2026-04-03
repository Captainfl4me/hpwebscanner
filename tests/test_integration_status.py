import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app, jobs
import main as main_mod


@pytest.fixture
def mock_ews(monkeypatch):
    """Mock the EWSClient used by the app's lifespan."""
    mock = MagicMock()
    mock.get_status = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    monkeypatch.setattr(main_mod, 'EWSClient', lambda ip, **kwargs: mock)
    return mock


def test_status_endpoint_after_scan(mock_ews):
    """Test status endpoint returns correct job info after successful scan."""
    # Pre-populate jobs dict with a completed job
    job_id = "existing123"
    jobs[job_id] = {
        'job_url': f'http://192.168.1.100/eSCL/ScanJobs/{job_id}',
        'status': 'Completed',
        'saved_path': f'/tmp/scans/scan_{job_id}.jpg'
    }

    with TestClient(app) as client:
        response = client.get(f"/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["job_status"]["status"] == "Completed"
        assert data["job_status"]["saved_path"] == f'/tmp/scans/scan_{job_id}.jpg'


def test_status_endpoint_unknown_job(mock_ews):
    """Test status endpoint with non-existent job."""
    with TestClient(app) as client:
        response = client.get("/status/unknown")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"]

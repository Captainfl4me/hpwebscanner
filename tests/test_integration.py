import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

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
    mock.download_image = AsyncMock()
    mock.close = AsyncMock()
    # Mock the httpx client used for health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock.client = AsyncMock()
    mock.client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr('main.EWSClient', lambda ip, **kwargs: mock)
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
        assert data["saved_path"] == "/tmp/scans/scan_test123.jpg"
        mock_ews.submit_scan_job.assert_called_once()
        # download_image should be called with next_document_url
        mock_ews.download_image.assert_called_once_with(
            'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
            '/tmp/scans/scan_test123.jpg'
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
        assert data["job_status"]["saved_path"] == "/tmp/scans/scan_test123.jpg"
        
        # download_image should be called with next_document_url
        mock_ews.download_image.assert_called_once_with(
            'http://192.168.1.100/Scan/Jobs/test123/NextDocument',
            '/tmp/scans/scan_test123.jpg'
        )

def test_status_endpoint_unknown_job():
    """Test status endpoint with non-existent job."""
    with TestClient(app) as client:
        response = client.get("/status/unknown")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"]

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

def test_max_jobs_eviction_removes_oldest(monkeypatch):
    """Test that when jobs count reaches MAX_JOBS, the oldest job is evicted before adding a new one."""
    import main
    monkeypatch.setattr(main, 'MAX_JOBS', 2)
    
    # Pre-populate jobs dict with two jobs
    jobs['old1'] = {
        'job_url': 'http://192.168.1.100/eSCL/ScanJobs/old1',
        'status': 'Completed',
        'saved_path': '/tmp/scan_old1.jpg'
    }
    jobs['old2'] = {
        'job_url': 'http://192.168.1.100/eSCL/ScanJobs/old2',
        'status': 'Completed',
        'saved_path': '/tmp/scan_old2.jpg'
    }
    assert len(jobs) == 2
    
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
    
    # Verify oldest job (old1) was removed
    assert 'old1' not in jobs
    # Verify other old job remains
    assert 'old2' in jobs
    # Verify new job was added (mock returns 'test123')
    assert 'test123' in jobs
    # Verify total jobs does not exceed MAX_JOBS
    assert len(jobs) == 2

def test_max_jobs_no_eviction_when_below_limit(monkeypatch):
    """Test that when jobs count is below MAX_JOBS, no eviction occurs."""
    import main
    monkeypatch.setattr(main, 'MAX_JOBS', 3)
    
    jobs['old1'] = {
        'job_url': 'http://192.168.1.100/eSCL/ScanJobs/old1',
        'status': 'Completed',
        'saved_path': '/tmp/scan_old1.jpg'
    }
    jobs['old2'] = {
        'job_url': 'http://192.168.1.100/eSCL/ScanJobs/old2',
        'status': 'Completed',
        'saved_path': '/tmp/scan_old2.jpg'
    }
    assert len(jobs) == 2
    
    with TestClient(app) as client:
        response = client.post("/scan")
        assert response.status_code == 200
    
    assert 'old1' in jobs
    assert 'old2' in jobs
    assert 'test123' in jobs
    assert len(jobs) == 3

def test_max_jobs_multiple_scans_fifo_eviction(monkeypatch, mock_ews):
    """Test that with multiple scans generating unique job IDs, eviction follows FIFO order."""
    import main
    monkeypatch.setattr(main, 'MAX_JOBS', 2)
    
    # Override mock_ews.submit_scan_job to return sequential job IDs
    counter = 0
    async def dynamic_submit():
        nonlocal counter
        job_id = f"job{counter}"
        counter += 1
        return {
            'job_id': job_id,
            'job_url': f'http://192.168.1.100/eSCL/ScanJobs/{job_id}',
            'next_document_url': f'http://192.168.1.100/eSCL/ScanJobs/{job_id}/NextDocument',
            'status': 'Submitted'
        }
    mock_ews.submit_scan_job = AsyncMock(side_effect=dynamic_submit)
    # download_image is already mocked
    
    with TestClient(app) as client:
        for i in range(3):
            response = client.post("/scan")
            assert response.status_code == 200, f"Scan {i+1} failed"
    
    # After three scans, should have exactly 2 jobs: job1 and job2 (job0 evicted)
    assert 'job0' not in jobs
    assert 'job1' in jobs
    assert 'job2' in jobs
    assert len(jobs) == 2

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app, jobs, MAX_JOBS
import main


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


def test_max_jobs_eviction_removes_oldest(monkeypatch, mock_ews):
    """Test that when jobs count reaches MAX_JOBS, the oldest job is evicted before adding a new one."""
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


def test_max_jobs_no_eviction_when_below_limit(monkeypatch, mock_ews):
    """Test that when jobs count is below MAX_JOBS, no eviction occurs."""
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

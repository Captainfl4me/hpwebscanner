import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app, jobs, trigger_scan


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


@pytest.mark.asyncio
async def test_concurrent_scans_under_limit(monkeypatch, mock_ews):
    """Test that multiple concurrent scans below MAX_JOBS all succeed and all jobs are retained."""
    import main
    # Set MAX_JOBS higher than number of concurrent scans
    monkeypatch.setattr(main, 'MAX_JOBS', 10)
    # Ensure clean state
    jobs.clear()
    # Set app state ews_client to the mock
    app.state.ews_client = mock_ews
    
    # Create dynamic submit that returns sequential unique job IDs
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
    # download_image is already AsyncMock from fixture (no-op)
    
    # Run 5 concurrent scans
    num_scans = 5
    tasks = [trigger_scan() for _ in range(num_scans)]
    results = await asyncio.gather(*tasks)
    
    # All scans should succeed
    for r in results:
        assert r['status'] == 'success'
    # All jobs should be present in jobs dict
    assert len(jobs) == num_scans
    job_ids_in_jobs = set(jobs.keys())
    result_ids = set(r['job_id'] for r in results)
    assert job_ids_in_jobs == result_ids


@pytest.mark.asyncio
async def test_concurrent_scans_exceed_limit(monkeypatch, mock_ews):
    """Test that when concurrent scans exceed MAX_JOBS, oldest jobs are evicted and exactly MAX_JOBS remain."""
    import main
    monkeypatch.setattr(main, 'MAX_JOBS', 2)
    jobs.clear()
    app.state.ews_client = mock_ews
    
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
    
    # Submit 3 concurrent scans when MAX_JOBS=2
    tasks = [trigger_scan() for _ in range(3)]
    results = await asyncio.gather(*tasks)
    
    for r in results:
        assert r['status'] == 'success'
    # Should have exactly MAX_JOBS entries
    assert len(jobs) == 2
    # Oldest job (job0) should have been evicted
    assert 'job0' not in jobs
    # The two newer jobs remain
    assert 'job1' in jobs
    assert 'job2' in jobs

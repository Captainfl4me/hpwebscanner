import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app
import main as main_mod


@pytest.fixture
def mock_ews(monkeypatch):
    """Mock the EWSClient used by the app's lifespan."""
    mock = MagicMock()
    # Mock the base_url
    mock.base_url = "https://192.168.1.100"
    # Mock the internal httpx client's get method to return a successful capabilities response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock.client = MagicMock()
    mock.client.get = AsyncMock(return_value=mock_response)
    mock.close = AsyncMock()
    monkeypatch.setattr(main_mod, 'EWSClient', lambda ip, **kwargs: mock)
    return mock


def test_health_endpoint(mock_ews):
    """Test that health endpoint returns 200 and healthy status."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "message" in data

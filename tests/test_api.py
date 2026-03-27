from unittest.mock import MagicMock, AsyncMock

def test_health_endpoint(client):
    """Test that health endpoint returns 200 and healthy status."""
    from src.main import app
    # Mock the httpx client's get method for health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Ensure ews_client exists and has a client attribute with get method
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(return_value=mock_response)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "message" in data

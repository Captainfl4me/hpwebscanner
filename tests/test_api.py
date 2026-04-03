from unittest.mock import MagicMock, AsyncMock

def test_health_endpoint(client):
    """Test that health endpoint returns 200 and healthy status."""
    from main import app
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

def test_health_endpoint_redirect_degraded(client):
    """Test that 3xx redirect returns degraded status."""
    from main import app
    mock_response = MagicMock()
    mock_response.status_code = 301
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(return_value=mock_response)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "redirecting" in data["message"].lower()

def test_health_endpoint_4xx_unhealthy(client):
    """Test that 4xx client error returns unhealthy status."""
    from main import app
    mock_response = MagicMock()
    mock_response.status_code = 404
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(return_value=mock_response)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["scanner_status_code"] == 404

def test_health_endpoint_5xx_unhealthy(client):
    """Test that 5xx server error returns unhealthy status."""
    from main import app
    mock_response = MagicMock()
    mock_response.status_code = 500
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(return_value=mock_response)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["scanner_status_code"] == 500

def test_health_endpoint_timeout_unhealthy(client):
    """Test that timeout exception returns unhealthy status."""
    from main import app
    import httpx
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "timeout" in data["error"].lower() or "unreachable" in data["message"].lower()

def test_health_endpoint_connection_error_unhealthy(client):
    """Test that connection error returns unhealthy status."""
    from main import app
    import httpx
    if not hasattr(app.state, 'ews_client'):
        app.state.ews_client = MagicMock()
    app.state.ews_client.client = AsyncMock()
    app.state.ews_client.client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "unreachable" in data["message"].lower()

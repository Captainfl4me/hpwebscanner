import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from main import OriginValidationMiddleware

@pytest.fixture
def app_with_middleware():
    def _make_app(allowed_ip):
        app = FastAPI()
        app.add_middleware(OriginValidationMiddleware, allowed_ip=allowed_ip)
        return app
    return _make_app

def test_middleware_allowed_ip(app_with_middleware):
    allowed_ip = "192.168.1.1"
    app = app_with_middleware(allowed_ip)
    client = TestClient(app, client=(allowed_ip, 12345))
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"client_ip": request.client.host}
    
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["client_ip"] == allowed_ip

def test_middleware_blocked_ip(app_with_middleware):
    allowed_ip = "192.168.1.1"
    app = app_with_middleware(allowed_ip)
    client = TestClient(app, client=("10.0.0.1", 12345))
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"client_ip": request.client.host}
    
    response = client.get("/test")
    assert response.status_code == 403
    assert response.json()["status"] == "error"

def test_middleware_open_all():
    app = FastAPI()
    app.add_middleware(OriginValidationMiddleware, allowed_ip="")
    client = TestClient(app)
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"client_ip": request.client.host}
    
    response = client.get("/test")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_middleware_none_client_host():
    """Test that when request.client is None, request is blocked."""
    from starlette.requests import Request
    from starlette.responses import Response
    
    app = FastAPI()
    middleware = OriginValidationMiddleware(app, allowed_ip="192.168.1.1")
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": None,
    }
    request = Request(scope)
    
    async def dummy_call_next(request):
        return Response("OK", status_code=200)
    
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_middleware_ipv6_address():
    """Test that IPv6 addresses are correctly matched."""
    from starlette.requests import Request
    from starlette.responses import Response
    
    app = FastAPI()
    middleware = OriginValidationMiddleware(app, allowed_ip="::1")
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("::1", 12345),  # 2-tuple (host, port)
    }
    request = Request(scope)
    
    async def dummy_call_next(request):
        return Response("OK", status_code=200)
    
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_middleware_ipv6_blocked_when_different():
    """Test that different IPv6 address is blocked."""
    from starlette.requests import Request
    from starlette.responses import Response
    
    app = FastAPI()
    middleware = OriginValidationMiddleware(app, allowed_ip="::1")
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("::2", 12345),  # Different IPv6, 2-tuple
    }
    request = Request(scope)
    
    async def dummy_call_next(request):
        return Response("OK", status_code=200)
    
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 403

import os
import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ["SCANNER_IP"] = "192.168.1.100"  # dummy IP
os.environ["SAVE_FOLDER"] = "/tmp/scans"
os.environ["ALLOWED_IP"] = ""  # Allow all for testing

from src.main import app

@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_scanner_ip():
    """Return the mock scanner IP used in tests."""
    return "192.168.1.100"

import os
import sys
import tempfile
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image


def _create_minimal_jpeg_bytes():
    buf = BytesIO()
    img = Image.new("RGB", (10, 10), "red")
    img.save(buf, format="JPEG")
    return buf.getvalue()


VALID_JPEG_BYTES = _create_minimal_jpeg_bytes()


class TestOutputFormatValidation:
    """Tests for OUTPUT_FORMAT environment variable validation."""

    def test_invalid_output_format_exits(self):
        """Test that invalid OUTPUT_FORMAT causes sys.exit at startup."""
        env = os.environ.copy()
        env["SCANNER_IP"] = "192.168.1.100"
        env["OUTPUT_FORMAT"] = "png"
        env["SAVE_FOLDER"] = "/tmp/scans"
        env["ALLOWED_IP"] = ""

        import subprocess
        result = subprocess.run(
            [sys.executable, "-c", "import main"],
            env=env,
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'src'),
        )
        assert result.returncode != 0
        assert "Invalid OUTPUT_FORMAT" in result.stderr


class TestOutputFormatJpg:
    """Tests for OUTPUT_FORMAT=jpg (native format)."""

    @pytest.fixture
    def jpg_app_client(self):
        """Create app with OUTPUT_FORMAT=jpg."""
        env_overrides = {"OUTPUT_FORMAT": "jpg"}
        return _create_test_app(env_overrides)

    def test_scan_saves_jpg(self, jpg_app_client):
        """Test that scan endpoint saves .jpg file when OUTPUT_FORMAT=jpg."""
        client, app = jpg_app_client
        response = client.post("/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["saved_path"].endswith(".jpg")


class TestOutputFormatPdf:
    """Tests for OUTPUT_FORMAT=pdf (conversion)."""

    @pytest.fixture
    def pdf_app_client(self):
        """Create app with OUTPUT_FORMAT=pdf."""
        env_overrides = {"OUTPUT_FORMAT": "pdf"}
        return _create_test_app(env_overrides)

    def test_scan_saves_pdf(self, pdf_app_client):
        """Test that scan endpoint saves .pdf file when OUTPUT_FORMAT=pdf."""
        client, app = pdf_app_client
        response = client.post("/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["saved_path"].endswith(".pdf")

    def test_scan_removes_intermediate_jpg(self, pdf_app_client):
        """Test that the intermediate .jpg file is removed after PDF conversion."""
        client, app = pdf_app_client
        response = client.post("/scan")
        data = response.json()
        pdf_path = data["saved_path"]
        jpg_path = pdf_path.replace(".pdf", ".jpg")
        assert not os.path.exists(jpg_path)
        assert os.path.exists(pdf_path)


def _create_test_app(env_overrides):
    """Helper to create a test app with specific environment overrides."""
    import importlib

    for key, value in env_overrides.items():
        os.environ[key] = value

    import main
    importlib.reload(main)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = VALID_JPEG_BYTES
    mock_response.headers = {"Content-Type": "image/jpeg"}

    main.app.state.ews_client = MagicMock()
    main.app.state.ews_client.client = AsyncMock()
    main.app.state.ews_client.client.get = AsyncMock(return_value=mock_response)
    main.app.state.ews_client.submit_scan_job = AsyncMock(return_value={
        "job_id": "test123",
        "job_url": "http://192.168.1.100/eSCL/ScanJobs/test123",
        "next_document_url": "http://192.168.1.100/eSCL/ScanJobs/test123/NextDocument",
        "status": "Submitted",
    })

    async def mock_download_image(image_url, destination_path):
        with open(destination_path, "wb") as f:
            f.write(VALID_JPEG_BYTES)

    main.app.state.ews_client.download_image = mock_download_image

    from fastapi.testclient import TestClient
    return TestClient(main.app), main.app

import asyncio
import os
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock

import pytest
from scanner_client import EWSClient

EWS_NS = {'scan': 'http://www.hp.com/schemas/imaging/eses/2009/03/25/'}


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    return MagicMock()


@pytest.fixture
def ews_client(mock_httpx_client):
    """Create EWSClient with mocked httpx client."""
    client = EWSClient("192.168.1.100")
    client.client = mock_httpx_client
    return client


class TestBuildScanJobXml:
    def test_defaults(self):
        client = EWSClient("1.2.3.4")
        xml_str = client._build_scan_job_xml()
        root = ET.fromstring(xml_str)
        
        assert root.tag == '{http://www.hp.com/schemas/imaging/eses/2009/03/25/}ScanJob'
        settings = root.find('scan:ScanSettings', EWS_NS)
        assert settings is not None
        
        color = settings.find('scan:ColorMode', EWS_NS)
        assert color.text == "Color"
        
        res = settings.find('scan:Resolution', EWS_NS)
        assert res.text == "200"
        
        file_type = settings.find('scan:FileType', EWS_NS)
        assert file_type.text == "PDF"
        
        file_format = settings.find('scan:FileFormat', EWS_NS)
        assert file_format.text == "Adobe PDF"
        
        input_source = settings.find('scan:InputSource', EWS_NS)
        assert input_source.text == "Flatbed"
    
    def test_custom_params(self):
        client = EWSClient("1.2.3.4")
        xml_str = client._build_scan_job_xml(
            color_mode="Grayscale",
            resolution=300,
            file_type="JPEG"
        )
        root = ET.fromstring(xml_str)
        settings = root.find('scan:ScanSettings', EWS_NS)
        
        color = settings.find('scan:ColorMode', EWS_NS)
        assert color.text == "Grayscale"
        
        res = settings.find('scan:Resolution', EWS_NS)
        assert res.text == "300"
        
        file_type = settings.find('scan:FileType', EWS_NS)
        assert file_type.text == "JPEG"


class TestSubmitScanJob:
    @pytest.mark.asyncio
    async def test_success_with_location_header(self, ews_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {'Location': 'http://192.168.1.100/Scan/Jobs/12345'}
        mock_response.text = ''
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        result = await ews_client.submit_scan_job()
        
        assert result['job_id'] == '12345'
        assert result['job_url'] == 'http://192.168.1.100/Scan/Jobs/12345'
        assert result['status'] == 'Submitted'
        
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        # Should use HTTPS base URL with eSCL endpoint
        assert call_args[0][0] == 'https://192.168.1.100/eSCL/ScanJobs'
        assert 'Content-Type' in call_args[1]['headers']
    
    @pytest.mark.asyncio
    async def test_success_with_xml_body(self, ews_client, mock_httpx_client):
        xml_body = '''<?xml version="1.0"?>
        <scan:ScanJob xmlns:scan="http://www.hp.com/schemas/imaging/eses/2009/03/25/">
            <scan:JobURL>http://192.168.1.100/Scan/Jobs/67890</scan:JobURL>
        </scan:ScanJob>'''
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = xml_body
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        result = await ews_client.submit_scan_job()
        
        assert result['job_id'] == '67890'
        assert result['job_url'] == 'http://192.168.1.100/Scan/Jobs/67890'
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Connection error"))
        
        with pytest.raises(Exception):
            await ews_client.submit_scan_job()


class TestGetJobStatus:
    @pytest.mark.asyncio
    async def test_success(self, ews_client, mock_httpx_client):
        xml_body = '''<?xml version="1.0"?>
        <scan:ScanJob xmlns:scan="http://www.hp.com/schemas/imaging/eses/2009/03/25/">
            <scan:JobState>Completed</scan:JobState>
            <scan:BinaryURL>http://192.168.1.100/Scan/Binary/abcd</scan:BinaryURL>
        </scan:ScanJob>'''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = xml_body
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        status = await ews_client.get_job_status('http://192.168.1.100/Scan/Jobs/123')
        
        assert status['state'] == 'Completed'
        assert status['binary_url'] == 'http://192.168.1.100/Scan/Binary/abcd'
    
    @pytest.mark.asyncio
    async def test_processing_state(self, ews_client, mock_httpx_client):
        xml_body = '''<?xml version="1.0"?>
        <scan:ScanJob xmlns:scan="http://www.hp.com/schemas/imaging/eses/2009/03/25/">
            <scan:JobState>Processing</scan:JobState>
        </scan:ScanJob>'''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = xml_body
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        status = await ews_client.get_job_status('http://192.168.1.100/Scan/Jobs/123')
        
        assert status['state'] == 'Processing'
        assert status['binary_url'] is None
    
    @pytest.mark.asyncio
    async def test_missing_elements(self, ews_client, mock_httpx_client):
        xml_body = '''<?xml version="1.0"?>
        <scan:ScanJob xmlns:scan="http://schemas.hp.com/scan">
        </scan:ScanJob>'''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = xml_body
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        status = await ews_client.get_job_status('http://192.168.1.100/Scan/Jobs/123')
        
        assert status['state'] == 'Unknown'
        assert status['binary_url'] is None


class TestWaitForCompletion:
    @pytest.mark.asyncio
    async def test_success(self, ews_client, mock_httpx_client):
        # First call returns Processing, second returns Completed
        responses = [
            {'state': 'Processing', 'binary_url': None},
            {'state': 'Completed', 'binary_url': 'http://192.168.1.100/Scan/Binary/xyz'}
        ]
        
        async def mock_get(url):
            resp = MagicMock()
            resp.status_code = 200
            # Pop from the front
            current = responses.pop(0)
            binary_url = current['binary_url'] if current['binary_url'] else ""
            resp.text = f'''<?xml version="1.0"?>
            <scan:ScanJob xmlns:scan="http://www.hp.com/schemas/imaging/eses/2009/03/25/">
                <scan:JobState>{current["state"]}</scan:JobState>
                <scan:BinaryURL>{binary_url}</scan:BinaryURL>
            </scan:ScanJob>'''
            return resp
        
        mock_httpx_client.get = AsyncMock(side_effect=mock_get)
        
        status = await ews_client.wait_for_completion('http://192.168.1.100/Scan/Jobs/123', poll_interval=0.1)
        
        assert status['state'] == 'Completed'
        assert status['binary_url'] == 'http://192.168.1.100/Scan/Binary/xyz'
    
    @pytest.mark.asyncio
    async def test_timeout(self, ews_client, mock_httpx_client):
        # Always return Processing
        async def mock_get(url):
            resp = MagicMock()
            resp.status_code = 200
            resp.text = '''<?xml version="1.0"?>
            <scan:ScanJob xmlns:scan="http://schemas.hp.com/scan">
                <scan:JobState>Processing</scan:JobState>
            </scan:ScanJob>'''
            return resp
        
        mock_httpx_client.get = AsyncMock(side_effect=mock_get)
        
        with pytest.raises(TimeoutError):
            await ews_client.wait_for_completion('http://192.168.1.100/Scan/Jobs/123', poll_interval=0.1, max_polls=2)


class TestDownloadPdf:
    @pytest.mark.asyncio
    async def test_success(self, ews_client, mock_httpx_client):
        pdf_content = b"%PDF-1.4 test content"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = pdf_content
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.pdf")
            await ews_client.download_pdf('http://192.168.1.100/Scan/Binary/xyz', save_path)
            
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                assert f.read() == pdf_content
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Download failed"))
        
        with pytest.raises(Exception), tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.pdf")
            await ews_client.download_pdf('http://192.168.1.100/Scan/Binary/xyz', save_path)

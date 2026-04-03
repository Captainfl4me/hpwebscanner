import os
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock

import pytest
from scanner_client import EWSClient

ESCL_NS = {
    'pwg': 'http://www.pwg.org/schemas/2010/12/sm',
    'scan': 'http://schemas.hp.com/imaging/escl/2011/05/03'
}


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
        
        # Root should be pwg:ScanSettings
        assert root.tag == f"{{{ESCL_NS['scan']}}}ScanSettings"
        
        # Check pwg:Version
        version = root.find('pwg:Version', ESCL_NS)
        assert version is not None
        assert version.text == "2.0"
        
        # Check pwg:ScanRegions
        scan_regions = root.find('pwg:ScanRegions', ESCL_NS)
        assert scan_regions is not None
        scan_region = scan_regions.find('pwg:ScanRegion', ESCL_NS)
        assert scan_region is not None
        
        # Check dimensions (default A4 at 300 DPI)
        height = scan_region.find('pwg:Height', ESCL_NS)
        assert height is not None
        # 297mm * 300dpi / 25.4 = 3507.87... (floor to 3507)
        assert int(height.text) == 3507
        
        width = scan_region.find('pwg:Width', ESCL_NS)
        assert width is not None
        # 210mm * 300dpi / 25.4 = 2480 pixels (approx)
        assert int(width.text) == 2480
        
        units = scan_region.find('pwg:ContentRegionUnits', ESCL_NS)
        assert units is not None
        assert units.text == "escl:ThreeHundredthsOfInches"
        
        x_offset = scan_region.find('pwg:XOffset', ESCL_NS)
        assert x_offset is not None
        assert x_offset.text == "0"
        
        y_offset = scan_region.find('pwg:YOffset', ESCL_NS)
        assert y_offset is not None
        assert y_offset.text == "0"
        
        # Check pwg:InputSource
        input_src = root.find('pwg:InputSource', ESCL_NS)
        assert input_src is not None
        assert input_src.text == "Platen"
        
        # Check scan:ColorMode (default RGB24)
        color = root.find('scan:ColorMode', ESCL_NS)
        assert color is not None
        assert color.text == "RGB24"
    
    def test_custom_params(self):
        client = EWSClient("1.2.3.4")
        xml_str = client._build_scan_job_xml(
            color_mode="Grayscale",
            width_mm=215.9,  # 8.5 inches in mm
            height_mm=279.4, # 11 inches in mm
            dpi=200
        )
        root = ET.fromstring(xml_str)
        
        # Check dimensions for 200 DPI
        scan_region = root.find('pwg:ScanRegions/pwg:ScanRegion', ESCL_NS)
        assert scan_region is not None
        
        height = scan_region.find('pwg:Height', ESCL_NS)
        assert height is not None
        # 279.4mm * 200dpi / 25.4 = 2200 pixels (approx)
        assert int(height.text) == 2200
        
        width = scan_region.find('pwg:Width', ESCL_NS)
        assert width is not None
        # 215.9mm * 200dpi / 25.4 = 1700 pixels (approx)
        assert int(width.text) == 1700
        
        # Check color mode
        color = root.find('scan:ColorMode', ESCL_NS)
        assert color is not None
        assert color.text == "Grayscale"


class TestSubmitScanJob:
    @pytest.mark.asyncio
    async def test_success_with_location_header(self, ews_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {'Location': 'http://192.168.1.100/eSCL/ScanJobs/12345'}
        mock_response.text = ''
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        result = await ews_client.submit_scan_job()
        
        assert result['job_id'] == '12345'
        assert result['job_url'] == 'http://192.168.1.100/eSCL/ScanJobs/12345'
        assert result['next_document_url'] == 'http://192.168.1.100/eSCL/ScanJobs/12345/NextDocument'
        assert result['status'] == 'Submitted'
        
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        # Should use HTTPS base URL with eSCL endpoint
        assert call_args[0][0] == 'https://192.168.1.100/eSCL/ScanJobs'
        assert call_args[1]['headers']['Content-Type'] == 'text/xml'
        # Check that XML payload contains ESCL structure
        xml_payload = call_args[1]['content']
        assert 'xmlns:pwg' in xml_payload
        assert 'xmlns:scan' in xml_payload
        assert 'pwg:Version' in xml_payload or 'Version' in xml_payload
    
    @pytest.mark.asyncio
    async def test_missing_location_header(self, ews_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = ''
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(ValueError, match="No Location header"):
            await ews_client.submit_scan_job()
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Connection error"))
        
        with pytest.raises(Exception):
            await ews_client.submit_scan_job()





class TestDownloadImage:
    @pytest.mark.asyncio
    async def test_success(self, ews_client, mock_httpx_client):
        pdf_content = b"%PDF-1.4 test content"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = pdf_content
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.pdf")
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)
            
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                assert f.read() == pdf_content
    
    @pytest.mark.asyncio
    async def test_http_error(self, ews_client, mock_httpx_client):
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Download failed"))
        
        with pytest.raises(Exception), tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.pdf")
            await ews_client.download_image('http://192.168.1.100/Scan/Binary/xyz', save_path)

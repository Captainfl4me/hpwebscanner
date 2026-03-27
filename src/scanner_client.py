import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger('hpwebscanner')


class EWSClient:
    """Client for HP scanner ESCL (eSCL) protocol."""
    
    # ESCL/PWG namespaces (based on working example)
    ESCL_NS = {
        'pwg': 'http://www.pwg.org/schemas/2010/12/sm',
        'scan': 'http://schemas.hp.com/imaging/escl/2011/05/03'
    }
    
    def __init__(self, scanner_ip: str, timeout: int = 30):
        self.scanner_ip = scanner_ip
        # Use HTTPS to avoid redirects; fallback to HTTP if needed
        self.base_url = f"https://{scanner_ip}"
        self.api_base = f"{self.base_url}/eSCL"
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False)
        # Default scan parameters
        self.default_dpi = 300
        self.default_width_mm = 210  # A4 width
        self.default_height_mm = 297  # A4 height
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def _build_scan_job_xml(self, 
                           color_mode: str = "RGB24",
                           input_source: str = "Platen",
                           width_mm: int = 210,
                           height_mm: int = 297,
                           dpi: int = 300) -> str:
        """Build the XML payload for scan job submission using ESCL/PWG schema."""
        # Calculate pixel dimensions
        width_px = int(width_mm * dpi / 25.4)
        height_px = int(height_mm * dpi / 25.4)
        
        # Create root element with scan namespace (per ESCL spec)
        pwg_ns = self.ESCL_NS['pwg']
        scan_ns = self.ESCL_NS['scan']
        root = ET.Element(f"{{{scan_ns}}}ScanSettings")
        
        # Add version
        version = ET.SubElement(root, f"{{{pwg_ns}}}Version")
        version.text = "2.0"
        
        # Add scan regions
        scan_regions = ET.SubElement(root, f"{{{pwg_ns}}}ScanRegions")
        scan_region = ET.SubElement(scan_regions, f"{{{pwg_ns}}}ScanRegion")
        
        height_elem = ET.SubElement(scan_region, f"{{{pwg_ns}}}Height")
        height_elem.text = str(height_px)
        
        width_elem = ET.SubElement(scan_region, f"{{{pwg_ns}}}Width")
        width_elem.text = str(width_px)
        
        units = ET.SubElement(scan_region, f"{{{pwg_ns}}}ContentRegionUnits")
        units.text = "escl:ThreeHundredthsOfInches"
        
        x_offset = ET.SubElement(scan_region, f"{{{pwg_ns}}}XOffset")
        x_offset.text = "0"
        
        y_offset = ET.SubElement(scan_region, f"{{{pwg_ns}}}YOffset")
        y_offset.text = "0"
        
        # Add input source
        input_src = ET.SubElement(root, f"{{{pwg_ns}}}InputSource")
        input_src.text = input_source
        
        # Add color mode using scan namespace
        color = ET.SubElement(root, f"{{{scan_ns}}}ColorMode")
        color.text = color_mode
        
        # Register namespaces
        ET.register_namespace('pwg', pwg_ns)
        ET.register_namespace('scan', scan_ns)
        
        return ET.tostring(root, encoding='unicode')
    
    async def submit_scan_job(self) -> Dict[str, Any]:
        """Submit a scan job to the scanner using ESCL protocol."""
        url = f"{self.api_base}/ScanJobs"
        xml_payload = self._build_scan_job_xml()
        logger.debug("ESCL XML payload: %s", xml_payload)
        
        headers = {
            'Content-Type': 'text/xml',
            'Accept': 'text/xml'
        }
        
        try:
            logger.info(f"Submitting scan job to {url}")
            response = await self.client.post(url, content=xml_payload, headers=headers)
            response.raise_for_status()
            
            # Extract job URL from Location header
            job_url = response.headers.get('Location')
            if not job_url:
                raise ValueError("No Location header returned from scan job submission")
            
            # Construct next document URL by appending '/NextDocument'
            # As per example-scan.py: urljoin(resp.headers['Location'] + '/', 'NextDocument')
            from urllib.parse import urljoin
            next_doc_url = urljoin(job_url.rstrip('/') + '/', 'NextDocument')
            
            # Extract job ID from the job URL (last part after /)
            job_id = job_url.rstrip('/').split('/')[-1]
            
            logger.info(f"Scan job submitted successfully - Job ID: {job_id}, NextDoc URL: {next_doc_url}")
            return {
                'job_id': job_id,
                'job_url': job_url,
                'next_document_url': next_doc_url,
                'status': 'Submitted'
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error submitting scan job: {e}")
            raise
        except Exception as e:
            logger.error(f"Error submitting scan job: {e}")
            raise
    

    async def download_pdf(self, pdf_url: str, destination_path: str) -> None:
        """Download the PDF from the BinaryURL and save to file."""
        try:
            logger.info(f"Downloading PDF from {pdf_url} to {destination_path}")
            response = await self.client.get(pdf_url)
            response.raise_for_status()
            
            # Ensure directory exists
            import os
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Write PDF file
            with open(destination_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"PDF saved successfully to {destination_path}")
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading PDF: {e}")
            raise
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            raise
    
    async def scan(self, save_folder: str, 
                   filename: Optional[str] = None,
                   wait_for_completion: bool = True,
                   **scan_kwargs) -> Dict[str, Any]:
        """Complete scan workflow: submit job and immediately download result (ESCL protocol)."""
        # Submit scan job
        job_info = await self.submit_scan_job()
        job_id = job_info['job_id']
        job_url = job_info['job_url']
        next_doc_url = job_info['next_document_url']
        
        result = {
            'job_id': job_id,
            'job_url': job_url,
            'status': 'Submitted'
        }
        
        if wait_for_completion:
            # With ESCL, the result is available immediately after submission
            # Generate filename if not provided
            if not filename:
                filename = f"scan_{job_id}.jpg"
            
            save_path = f"{save_folder.rstrip('/')}/{filename}"
            
            # Download directly from NextDocument URL
            await self.download_pdf(next_doc_url, save_path)
            result['saved_path'] = save_path
            result['status'] = 'Completed'
        
        return result
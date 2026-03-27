import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger('hpwebscanner')


class EWSClient:
    """Client for HP scanner Embedded Web Server (EWS) protocol."""
    
    # eSCL namespace (HP implementation)
    EWS_NS = {'scan': 'http://www.hp.com/schemas/imaging/eses/2009/03/25/'}
    
    def __init__(self, scanner_ip: str, timeout: int = 30):
        self.scanner_ip = scanner_ip
        # Use HTTPS to avoid redirects; fallback to HTTP if needed
        self.base_url = f"https://{scanner_ip}"
        self.api_base = f"{self.base_url}/eSCL"
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def _build_scan_job_xml(self, 
                           color_mode: str = "Color",
                           resolution: int = 200,
                           file_type: str = "PDF") -> str:
        """Build the XML payload for scan job submission."""
        ns = self.EWS_NS['scan']
        
        # Use Clark notation for namespaced tags
        root = ET.Element(f"{{{ns}}}ScanJob")
        
        settings = ET.SubElement(root, f"{{{ns}}}ScanSettings")
        
        color = ET.SubElement(settings, f"{{{ns}}}ColorMode")
        color.text = color_mode
        
        res = ET.SubElement(settings, f"{{{ns}}}Resolution")
        res.text = str(resolution)
        
        file_type_elem = ET.SubElement(settings, f"{{{ns}}}FileType")
        file_type_elem.text = file_type
        
        # Add basic file format settings
        file_format = ET.SubElement(settings, f"{{{ns}}}FileFormat")
        file_format.text = "Adobe PDF"
        
        # Input source - flatbed by default
        input_source = ET.SubElement(settings, f"{{{ns}}}InputSource")
        input_source.text = "Flatbed"
        
        # Register namespace to get consistent prefix
        ET.register_namespace('scan', ns)
        
        return ET.tostring(root, encoding='unicode')
    
    async def submit_scan_job(self) -> Dict[str, Any]:
        """Submit a scan job to the scanner."""
        url = f"{self.api_base}/ScanJobs"
        xml_payload = self._build_scan_job_xml()
        
        headers = {
            'Content-Type': 'application/xml',
            'Accept': 'application/xml'
        }
        
        try:
            logger.info(f"Submitting scan job to {url}")
            response = await self.client.post(url, content=xml_payload, headers=headers)
            response.raise_for_status()
            
            # Parse the response XML
            response_xml = response.text
            
            # Extract job URL from Location header or from response body
            job_url = response.headers.get('Location')
            if not job_url:
                # Parse XML to find JobURL or JobId
                root = ET.fromstring(response_xml)
                job_url_elem = root.find('.//scan:JobURL', self.EWS_NS)
                if job_url_elem is not None:
                    job_url = job_url_elem.text
                else:
                    # Try to find JobId and construct URL
                    job_id_elem = root.find('.//scan:JobId', self.EWS_NS)
                    if job_id_elem is not None:
                        job_id = job_id_elem.text
                        job_url = f"{self.api_base}/jobs/{job_id}"
            
            if not job_url:
                raise ValueError("No job URL returned from scan job submission")
            
            # Extract job ID from the URL (last part after /)
            job_id = job_url.rstrip('/').split('/')[-1]
            
            logger.info(f"Scan job submitted successfully - Job ID: {job_id}, Job URL: {job_url}")
            return {
                'job_id': job_id,
                'job_url': job_url,
                'status': 'Submitted'
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error submitting scan job: {e}")
            raise
        except Exception as e:
            logger.error(f"Error submitting scan job: {e}")
            raise
    
    async def get_job_status(self, job_url: str) -> Dict[str, Any]:
        """Poll the job status from the job URL."""
        try:
            logger.debug(f"Polling job status from {job_url}")
            response = await self.client.get(job_url)
            response.raise_for_status()
            
            # Parse the response XML
            root = ET.fromstring(response.text)
            
            # Extract job state
            state_elem = root.find('.//scan:JobState', self.EWS_NS)
            state = state_elem.text if state_elem is not None else "Unknown"
            
            # Check if PDF is available
            binary_url_elem = root.find('.//scan:BinaryURL', self.EWS_NS)
            binary_url = binary_url_elem.text if binary_url_elem is not None else None
            
            result = {
                'state': state,
                'binary_url': binary_url
            }
            
            logger.debug(f"Job status: {state}")
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting job status: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            raise
    
    async def wait_for_completion(self, job_url: str, 
                                  poll_interval: int = 2, 
                                  max_polls: int = 300) -> Dict[str, Any]:
        """Poll job until completion or timeout."""
        for i in range(max_polls):
            status = await self.get_job_status(job_url)
            
            # EWS states: Submitted, Processing, Completed, Cancelled, Error
            if status['state'] in ['Completed', 'Cancelled', 'Error']:
                logger.info(f"Job finished with state: {status['state']}")
                return status
            
            if i < max_polls - 1:
                await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Job did not complete within {max_polls * poll_interval} seconds")
    
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
        """Complete scan workflow: submit job, wait (optional), and save PDF."""
        # Submit scan job
        job_info = await self.submit_scan_job()
        job_id = job_info['job_id']
        job_url = job_info['job_url']
        
        result = {
            'job_id': job_id,
            'job_url': job_url,
            'status': 'Submitted'
        }
        
        if wait_for_completion:
            # Wait for job to complete
            final_status = await self.wait_for_completion(job_url)
            result['final_state'] = final_status['state']
            
            if final_status['state'] == 'Completed' and final_status.get('binary_url'):
                # Generate filename if not provided
                if not filename:
                    filename = f"scan_{job_id}.pdf"
                
                save_path = f"{save_folder.rstrip('/')}/{filename}"
                
                # Download PDF
                await self.download_pdf(final_status['binary_url'], save_path)
                result['saved_path'] = save_path
                result['status'] = 'Completed'
            else:
                result['status'] = final_status['state']
        
        return result
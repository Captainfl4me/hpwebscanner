from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging
import os
import sys
import asyncio
from typing import Dict, Any, Optional
from scanner_client import EWSClient

# Environmental variables configuration
SCANNER_IP = os.getenv("SCANNER_IP")
SAVE_FOLDER = os.getenv("SAVE_FOLDER", "./")
ALLOWED_IP = os.getenv("ALLOWED_IP", "127.0.0.1")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() == "true"

# Check required environment variables
if not SCANNER_IP:
    logger = logging.getLogger('hpwebscanner')
    logger.error("SCANNER_IP environment variable is required but not provided.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hpwebscanner')

# Validate SAVE_FOLDER exists and is writable
try:
    # Expand user home directory if needed
    save_folder_path = os.path.expanduser(SAVE_FOLDER)
    # Create folder if it doesn't exist
    if not os.path.exists(save_folder_path):
        logger.info(f"SAVE_FOLDER does not exist, creating: {save_folder_path}")
        os.makedirs(save_folder_path, exist_ok=True)
    # Check writability
    if not os.access(save_folder_path, os.W_OK):
        raise PermissionError(f"SAVE_FOLDER is not writable: {save_folder_path}")
    logger.info(f"SAVE_FOLDER validated: {save_folder_path}")
except Exception as e:
    logger.error(f"Failed to validate SAVE_FOLDER '{SAVE_FOLDER}': {e}")
    sys.exit(1)

# Log configuration at startup
logger.info(f"Configuration loaded - SCANNER_IP: {SCANNER_IP}")
logger.info(f"SAVE_FOLDER: {SAVE_FOLDER}")
logger.info(f"ALLOWED_IP: {ALLOWED_IP}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")

# Job storage and lock (kept for status tracking, though scans are immediate)
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = asyncio.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.ews_client = EWSClient(SCANNER_IP, verify_ssl=SSL_VERIFY)
    logger.info("EWS client initialized")
    yield
    # Shutdown
    await app.state.ews_client.close()
    logger.info("EWS client closed")

app = FastAPI(lifespan=lifespan)

# Origin validation middleware
class OriginValidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_ip: str):
        super().__init__(app)
        self.allowed_ip = allowed_ip
        self.is_open = allowed_ip == ""  # Empty means allow all
    
    async def dispatch(self, request: Request, call_next):
        if self.is_open:
            return await call_next(request)
        
        client_ip = request.client.host
        if client_ip != self.allowed_ip:
            logger.warning(f"Blocked request from unauthorized IP: {client_ip}")
            return JSONResponse(
                status_code=403,
                content={"status": "error", "message": "Access denied: IP not allowed"}
            )
        
        return await call_next(request)

app.add_middleware(OriginValidationMiddleware, allowed_ip=ALLOWED_IP)



@app.get("/health")
async def health_check():
        logger.info("Health check endpoint accessed")
        try:
            # Test basic connectivity to scanner by checking capabilities endpoint
            client = app.state.ews_client
            capabilities_url = f"{client.base_url}/eSCL/ScannerCapabilities"
            response = await client.client.get(capabilities_url, timeout=5)
            status_code = response.status_code
            
            # Proper HTTP status code classification
            if 200 <= status_code < 300:
                return {
                    "status": "healthy",
                    "message": "Server and scanner connection OK",
                    "scanner_status_code": status_code
                }
            elif 300 <= status_code < 400:
                return {
                    "status": "degraded",
                    "message": "Server running but scanner redirecting",
                    "scanner_status_code": status_code
                }
            else:  # 4xx or 5xx
                return {
                    "status": "unhealthy",
                    "message": "Server running but scanner error",
                    "scanner_status_code": status_code
                }
        except Exception as e:
            logger.warning(f"Health check failed to reach scanner: {e}")
            return {
                "status": "unhealthy",
                "message": "Server running but scanner unreachable",
                "error": str(e)
            }

@app.post("/scan")
async def trigger_scan():
    """Endpoint to trigger a new scan job and immediately download the result."""
    logger.info("Scan request received")
    
    try:
        client = app.state.ews_client
        # Submit scan job and get the next document URL (direct download)
        job_info = await client.submit_scan_job()
        job_id = job_info['job_id']
        job_url = job_info['job_url']
        next_doc_url = job_info['next_document_url']
        
        # Store initial job info
        async with jobs_lock:
            jobs[job_id] = {
                'job_url': job_url,
                'status': 'Downloading',
                'saved_path': None
            }
        
        # Download the PDF immediately (no polling needed with ESCL)
        filename = f"scan_{job_id}.jpg"
        save_path = f"{SAVE_FOLDER.rstrip('/')}/{filename}"
        
        await client.download_image(next_doc_url, save_path)
        
        # Update job status
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]['status'] = 'Completed'
                jobs[job_id]['saved_path'] = save_path
        
        logger.info(f"Scan job {job_id} completed, PDF saved to {save_path}")
        
        return {
            "status": "success",
            "job_id": job_id,
            "message": "Scan completed successfully",
            "saved_path": save_path
        }
    
    except Exception as e:
        logger.error(f"Failed to complete scan: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to complete scan: {str(e)}"}
        )

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a specific job."""
    async with jobs_lock:
        if job_id not in jobs:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Job {job_id} not found"}
            )
        
        job = jobs[job_id].copy()
    
    return {
        "status": "success",
        "job_id": job_id,
        "job_status": job
    }

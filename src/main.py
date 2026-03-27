from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import os
import sys
import asyncio
from typing import Dict, Any, Optional
from scanner_client import EWSClient

# Environmental variables configuration
SCANNER_IP = os.getenv("SCANNER_IP")
SAVE_FOLDER = os.getenv("SAVE_FOLDER", "/scans")
ALLOWED_IP = os.getenv("ALLOWED_IP", "127.0.0.1")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

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

# Log configuration at startup
logger.info(f"Configuration loaded - SCANNER_IP: {SCANNER_IP}")
logger.info(f"SAVE_FOLDER: {SAVE_FOLDER}")
logger.info(f"ALLOWED_IP: {ALLOWED_IP}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")

app = FastAPI()

# Job storage and lock
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = asyncio.Lock()

# Lifespan events for EWSClient
@app.on_event("startup")
async def startup_event():
    app.state.ews_client = EWSClient(SCANNER_IP)
    logger.info("EWS client initialized")

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.ews_client.close()
    logger.info("EWS client closed")

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

async def process_scan_job(job_id: str, job_url: str):
    """Background task to process scan job (poll and save PDF)."""
    async with jobs_lock:
        if job_id in jobs:
            jobs[job_id]['status'] = 'Processing'
    
    try:
        client = app.state.ews_client
        logger.info(f"Processing job {job_id} - waiting for completion")
        
        # Wait for job to complete
        final_status = await client.wait_for_completion(job_url)
        state = final_status['state']
        
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]['state'] = state
        
        if state == 'Completed' and final_status.get('binary_url'):
            # Download PDF
            pdf_url = final_status['binary_url']
            filename = f"scan_{job_id}.pdf"
            save_path = f"{SAVE_FOLDER.rstrip('/')}/{filename}"
            
            await client.download_pdf(pdf_url, save_path)
            
            async with jobs_lock:
                if job_id in jobs:
                    jobs[job_id]['saved_path'] = save_path
                    jobs[job_id]['status'] = 'Completed'
            
            logger.info(f"Job {job_id} completed, PDF saved to {save_path}")
        else:
            async with jobs_lock:
                if job_id in jobs:
                    jobs[job_id]['status'] = state
            logger.info(f"Job {job_id} finished with state: {state}")
    
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]['status'] = 'Error'
                jobs[job_id]['error'] = str(e)

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    try:
        # Test basic connectivity to scanner by checking capabilities endpoint
        client = app.state.ews_client
        capabilities_url = f"{client.base_url}/eSCL/ScannerCapabilities"
        response = await client.client.get(capabilities_url, timeout=5)
        if response.status_code < 500:  # Accept any non-server error
            return {
                "status": "healthy",
                "message": "Server and scanner connection OK",
                "scanner_status_code": response.status_code
            }
        else:
            return {
                "status": "degraded",
                "message": "Server running but scanner error",
                "scanner_status_code": response.status_code
            }
    except Exception as e:
        logger.warning(f"Health check failed to reach scanner: {e}")
        return {
            "status": "unhealthy",
            "message": "Server running but scanner unreachable",
            "error": str(e)
        }

@app.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Endpoint to trigger a new scan job."""
    logger.info("Scan request received")
    
    try:
        client = app.state.ews_client
        job_info = await client.submit_scan_job()
        job_id = job_info['job_id']
        job_url = job_info['job_url']
        
        # Store job info
        async with jobs_lock:
            jobs[job_id] = {
                'job_url': job_url,
                'status': 'Submitted',
                'state': None
            }
        
        # Start background processing
        background_tasks.add_task(process_scan_job, job_id, job_url)
        
        logger.info(f"Scan job {job_id} submitted, processing in background")
        return {
            "status": "success",
            "job_id": job_id,
            "message": "Scan job submitted successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to submit scan job: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to submit scan job: {str(e)}"}
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

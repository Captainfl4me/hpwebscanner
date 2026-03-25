from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys

# Environmental variables configuration
SCANNER_IP = os.getenv("SCANNER_IP")
SAVE_FOLDER = os.getenv("SAVE_FOLDER", "/scans")
ALLOWED_IP = os.getenv("ALLOWED_IP", "")
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

# Optional: CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy", "message": "Server is running"}

@app.post("/scan")
async def trigger_scan():
    logger.info("Scan request received")
    return {"status": "success", "message": "Scan initiated"}
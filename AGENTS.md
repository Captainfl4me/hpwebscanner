# hpwebscanner - Agent Guidelines

## Project Overview
Tool to trigger HP scanner (EWS/ESCL compatible) via REST API, handle image storage and scanner communication. Designed for Home Assistant integration.

## Requirements
- Python-based REST API with FastAPI
  - Three endpoints:
    1. `/health` - Scanner connection status
    2. `/scan` - Trigger scan and save image to predefined folder
    3. `/status/{job_id}` - Get job status
  - Act as client to HP EWS/ESCL
  - Docker container: self-contained, exposes API
- Origin validation via configurable ENV var (ALLOWED_IP)
- Logging with configurable levels (INFO, WARN, ERROR)

## Technical Stack
- Language: Python 3.9+
- Web Framework: FastAPI
- HTTP Client: httpx (async)
- XML Parsing: xml.etree.ElementTree
- Container: Docker
- Testing: pytest, pytest-asyncio

## ESCL Protocol Details
- Scan job submission: POST to `/eSCL/ScanJobs` with XML payload
- Job status: Get `Location` header from response, append `/NextDocument` for image download URL
- Scanner status: GET to `/eSCL/ScannerCapabilities` (used for health check)
- Image retrieval: GET from NextDocument URL (immediate with ESCL)

## Configuration
  - **SCANNER_IP**: (required) Environment variable for HP scanner address
  - **SAVE_FOLDER**: Environment variable for image storage path (default: `./`)
  - **ALLOWED_IP**: Environment variable for API origin validation (default: `127.0.0.1`, empty string allows all)
  - **LOG_LEVEL**: Environment variable for logging (default: `INFO`)
  - **SSL_VERIFY**: Environment variable for SSL verification (default: `true`)
  - **MAX_JOBS**: Environment variable for max in-memory job entries (default: `100`)
  - **OUTPUT_FORMAT**: Environment variable for output file format (default: `jpg`, options: `jpg`, `pdf`)

## API Endpoints
- `GET /health` - Returns scanner status (checks connectivity to `/eSCL/ScannerCapabilities`)
- `POST /scan` - Initiates scan, returns job ID and saved image path
- `GET /status/{job_id}` - Get status of a specific job (in-memory tracking)

## Running Unit Tests
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (if needed)
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_scanner_client.py

# Run test by name pattern
pytest -k "test_build_scan_job_xml"
```
Tests are located in the `tests/` directory and include:
- `test_api.py` - API endpoint tests (health, scan)
- `test_middleware.py` - Origin validation middleware tests
- `test_scanner_client.py` - EWSClient unit tests (XML generation, job submission, image download)

## Running the Application
```bash
# Activate virtual environment
source venv/bin/activate

# Set required environment variables
export SCANNER_IP="192.168.1.100"
export SAVE_FOLDER="./scans"
export ALLOWED_IP="127.0.0.1"
export LOG_LEVEL="INFO"

# Add src directory to Python path (source is in src/)
export PYTHONPATH=src

# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Development Notes
- Maintain async compatibility with FastAPI
- Handle XML namespaces correctly (pwg and scan namespaces)
- Implement proper error handling and logging
- ESCL protocol returns images immediately (no polling needed)
- Test with actual HP ESCL device when available
- Python source code is located inside `src` folder.
- Immediate download: The `/scan` endpoint downloads the JPG immediately after job submission (ESCL protocol)

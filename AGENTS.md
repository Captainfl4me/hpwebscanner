# hpwebscanner - Agent Guidelines

## Project Overview
Tool to trigger HP scanner (EWS compatible) via REST API, handle PDF storage and scanner communication. Designed for Home Assistant integration.

## Requirements
- Python-based REST API with FastAPI
- Two endpoints:
  1. `/health` - Scanner connection status
  2. `/scan` - Trigger scan and save PDF to predefined folder
- Act as client to HP EWS (no PDF processing)
- Docker container: self-contained, exposes API
- Origin validation via configurable ENV var (ALLOWED_IP)
- Logging with configurable levels (INFO, WARN, ERROR)

## Technical Stack
- Language: Python 3.9+
- Web Framework: FastAPI
- HTTP Client: httpx (async) or requests
- XML Parsing: xml.etree.ElementTree
- Container: Docker

## EWS Protocol Details (from go-example)
- Scan job submission: POST to `/Scan/Jobs` with XML payload
- Job status polling: GET to job location URL
- Scanner status: GET to `/Scan/Status`
- PDF retrieval: GET to BinaryURL from job response

## Configuration
- SCANNER_IP: Environment variable for HP scanner address
- SAVE_FOLDER: Environment variable for PDF storage path
- ALLOWED_IP: Environment variable for API origin validation
- LOG_LEVEL: Environment variable for logging (default: INFO)

## API Endpoints
- GET /health - Returns scanner status (Idle/Busy/etc.)
- POST /scan - Initiates scan, returns job ID, saves PDF when complete

## Development Notes
- Maintain async compatibility with FastAPI
- Handle XML namespaces correctly (as in go-example)
- Implement proper error handling and logging
- Ensure Dockerfile includes only necessary dependencies
- Test with actual HP EWS device when available
- Python source code should be located inside `src` folder.

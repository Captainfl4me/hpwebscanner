# hpwebscanner

REST API to trigger HP scanner (EWS/ESCL compatible) and save scanned JPG images. Designed for Home Assistant integration.

## Features

- **REST API** with FastAPI (async)
- **Two endpoints**: `/health` (scanner status) and `/scan` (trigger scan)
- **Job tracking**: `/status/{job_id}` endpoint
- **Origin validation**: Configurable IP whitelist
- **Docker support**: Self-contained container
- **Configurable**: Environment variables for scanner IP, storage path, logging

## Quick Start

### With Docker

```bash
# Build image
docker build -t hpwebscanner .

# Run container
docker run -d \
  -p 8000:8000 \
  -e SCANNER_IP="192.168.1.100" \
  -e SAVE_FOLDER="/scans" \
  -e ALLOWED_IP="" \
  -e LOG_LEVEL="INFO" \
  -v $(pwd)/scans:/scans \
  hpwebscanner
```

### Direct Python

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SCANNER_IP="192.168.1.100"
export SAVE_FOLDER="./scans"
export ALLOWED_IP="127.0.0.1"
export LOG_LEVEL="INFO"

# Add src to Python path
export PYTHONPATH=src

# Run API
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SCANNER_IP` | Yes | - | IP address of HP scanner |
| `SAVE_FOLDER` | No | `./` | Directory to save scanned JPG files |
| `ALLOWED_IP` | No | `127.0.0.1` | Allowed client IP (empty = allow all) |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check scanner connectivity |
| `POST` | `/scan` | Trigger scan, returns job ID and saved path |
| `GET` | `/status/{job_id}` | Get job status |

### Example: Trigger Scan

```bash
curl -X POST http://localhost:8000/scan
```

Response:
```json
{
  "status": "success",
  "job_id": "12345",
  "message": "Scan completed successfully",
  "saved_path": "./scans/scan_12345.jpg"
}
```

## Testing

```bash
pytest
```

## Notes

- Python source code is located in `src/` directory
- Scanned images are saved as JPG (ESCL protocol)
- Scanner must be EWS/ESCL compatible (HP network scanners)

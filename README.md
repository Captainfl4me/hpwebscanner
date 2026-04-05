# hpwebscanner

REST API to trigger HP scanner (EWS/ESCL compatible) and save scanned JPG images. Designed for Home Assistant integration.

## Features

- **REST API** with FastAPI (async)
- **Three endpoints**: `/health` (scanner status), `/scan` (trigger scan), `/status/{job_id}` (job tracking)
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

### With Docker Compose

```bash
# Edit SCANNER_IP in docker-compose.yml, then:
docker compose up -d
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
| `SAVE_FOLDER` | No | `./` | Directory to save scanned files |
| `ALLOWED_IP` | No | `127.0.0.1` | Allowed client IP (empty = allow all) |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `OUTPUT_FORMAT` | No | `jpg` | Output file format (`jpg` or `pdf`) |

## API Endpoints

### `GET /health`

Check scanner connectivity.

**Response (200):**
```json
{
  "status": "healthy",
  "message": "Server and scanner connection OK",
  "scanner_status_code": 200
}
```

**Possible `status` values:** `healthy`, `degraded`, `unhealthy`

### `POST /scan`

Trigger scan, returns job ID and saved path.

**Response (200):**
```json
{
  "status": "success",
  "job_id": "12345",
  "message": "Scan completed successfully",
  "saved_path": "./scans/scan_12345.jpg"
}
```

**Response (500):**
```json
{
  "status": "error",
  "message": "Failed to complete scan: <error details>"
}
```

### `GET /status/{job_id}`

Get job status.

**Response (200):**
```json
{
  "status": "success",
  "job_id": "12345",
  "job_status": {
    "job_url": "https://192.168.1.100/eSCL/ScanJobs/12345",
    "status": "Completed",
    "saved_path": "./scans/scan_12345.jpg"
  }
}
```

**Response (404):**
```json
{
  "status": "error",
  "message": "Job 12345 not found"
}
```

**Possible `status` values:** `healthy`, `degraded`, `unhealthy`

### `POST /scan`

Trigger scan, returns job ID and saved path.

**Response (200):**
```json
{
  "status": "success",
  "job_id": "12345",
  "message": "Scan completed successfully",
  "saved_path": "./scans/scan_12345.jpg"
}
```

**Response (500):**
```json
{
  "status": "error",
  "message": "Failed to complete scan: <error details>"
}
```

### `GET /status/{job_id}`

Get job status.

**Response (200):**
```json
{
  "status": "success",
  "job_id": "12345",
  "job_status": {
    "job_url": "https://192.168.1.100/eSCL/ScanJobs/12345",
    "status": "Completed",
    "saved_path": "./scans/scan_12345.jpg"
  }
}
```

**Response (404):**
```json
{
  "status": "error",
  "message": "Job 12345 not found"
}
```

## Testing

```bash
pytest
```

## Notes

- Python source code is located in `src/` directory
- Scanned images are saved as JPG or PDF (controlled by `OUTPUT_FORMAT`)
- Scanner must be EWS/ESCL compatible (HP network scanners)

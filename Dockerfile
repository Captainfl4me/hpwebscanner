# Use slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Environment variables (can be overridden at runtime)
ENV PYTHONPATH=/app/src
ENV SAVE_FOLDER=/scans
ENV ALLOWED_IP=""
ENV LOG_LEVEL="INFO"
ENV OUTPUT_FORMAT="jpg"

# Create scans directory
RUN mkdir -p /scans

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

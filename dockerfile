# Use official Python slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by psycopg2 and Pillow
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Cloud Run sets PORT env variable — default to 8080
ENV PORT=8080

# Run with Gunicorn + Uvicorn workers
CMD exec gunicorn app.main:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --keep-alive 5 \
    --log-level info
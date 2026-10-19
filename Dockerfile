# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8090 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Persistent data and upload staging dirs (both bind-mounted / volumed in compose)
RUN mkdir -p /app/data /tmp/autosplit/uploads

ENV TESSERACT_CMD=/usr/bin/tesseract

EXPOSE 8090

# Default: web server. Worker overrides this with: python worker.py
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app


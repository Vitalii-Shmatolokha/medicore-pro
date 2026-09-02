# ==========================================================
# Multi-Stage Production Dockerfile for MediCore Pro
# Python 3.11-slim Base
# ==========================================================

# Stage 1: Build Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==========================================================
# Stage 2: Final Minimal & Secure Runtime
# ==========================================================
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/medicore/.local/bin:$PATH \
    FLASK_ENV=production

# Install runtime PostgreSQL client library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user for security
RUN groupadd -r medicore && useradd -r -g medicore -d /home/medicore -s /bin/bash medicore \
    && mkdir -p /home/medicore /app/instance \
    && chown -R medicore:medicore /home/medicore /app

# Copy compiled python packages from builder
COPY --from=builder --chown=medicore:medicore /root/.local /home/medicore/.local

# Copy application source code
COPY --chown=medicore:medicore . /app

# Switch to non-root user
USER medicore

EXPOSE 8000

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start via Gunicorn with Eventlet configuration
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]

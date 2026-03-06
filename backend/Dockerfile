# =============================================================================
# Backend Dockerfile — multi-stage build
# =============================================================================

# ---- Builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Security: non-root user
RUN groupadd --gid 1001 nonroot && \
    useradd --uid 1001 --gid 1001 --no-create-home nonroot

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY app/ ./app/

# Environment hardening
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Switch to non-root
USER nonroot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

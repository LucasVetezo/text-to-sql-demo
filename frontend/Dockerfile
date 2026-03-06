# =============================================================================
# Frontend Dockerfile — multi-stage build
# =============================================================================

FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim AS runtime
RUN groupadd --gid 1001 nonroot && \
    useradd --uid 1001 --gid 1001 --no-create-home nonroot

COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8501

USER nonroot

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]

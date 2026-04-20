# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
RUN opentelemetry-bootstrap -a install

# =============================================================================
# Stage 2: Final
# =============================================================================
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget && rm -rf /var/lib/apt/lists/*

RUN groupadd -r -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -m -s /sbin/nologin appuser

COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# OpenTelemetry config
ENV OTEL_SERVICE_NAME="analytics-service" \
    OTEL_RESOURCE_ATTRIBUTES="service.namespace=togglemaster,deployment.environment=production,service.version=1.0.0" \
    OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector-opentelemetry-collector.monitoring.svc.cluster.local:4317" \
    OTEL_EXPORTER_OTLP_INSECURE="true" \
    OTEL_EXPORTER_OTLP_PROTOCOL="grpc" \
    OTEL_TRACES_EXPORTER="otlp" \
    OTEL_METRICS_EXPORTER="otlp" \
    OTEL_LOGS_EXPORTER="otlp" \
    OTEL_PYTHON_LOG_CORRELATION="true"

WORKDIR /app
COPY --chown=appuser:appgroup requirements.txt .
COPY --chown=appuser:appgroup app.py .

USER appuser
EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8005/health || exit 1

CMD ["opentelemetry-instrument", "gunicorn", "--bind", "0.0.0.0:8005", "--workers", "2", "--timeout", "60", "app:app"]

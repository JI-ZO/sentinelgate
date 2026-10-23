# ==========================================
# Multi-stage Dockerfile for SentinelGate
# ==========================================

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY sentinelgate ./sentinelgate

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ==========================================
# Final Runtime Stage
# ==========================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Run as non-root user for security
RUN groupadd -r sentinel && useradd -r -g sentinel sentinel

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/sentinelgate /usr/local/bin/sentinelgate
COPY sentinelgate ./sentinelgate

USER sentinel

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

ENTRYPOINT ["sentinelgate", "--host", "0.0.0.0", "--port", "8000"]

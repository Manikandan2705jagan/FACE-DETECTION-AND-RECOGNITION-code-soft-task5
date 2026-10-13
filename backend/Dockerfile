# Minimal, CPU-only image so the whole stack runs without a GPU.
# For GPU/TensorRT use infra/backend.Dockerfile.gpu instead.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libglib2.0-0 \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install without insightface first (large, needs compilation), then best-effort.
RUN pip install --upgrade pip && \
    grep -v '^insightface' requirements.txt > requirements-cpu.txt && \
    pip install -r requirements-cpu.txt

# insightface is optional at runtime; install best-effort so builds don't fail.
RUN pip install insightface==0.7.3 || echo "insightface not installed; mock engine will be used"

COPY . .

RUN mkdir -p /models /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

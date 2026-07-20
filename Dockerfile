# ---- base ----
FROM python:3.11-slim AS base

# ---- builder ----
FROM base AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY api/ api/
COPY data/ data/
COPY asset/img/ asset/img/

# ---- runtime ----
FROM base AS runtime

# Install runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application files
COPY --from=builder /app/api /app/api
COPY --from=builder /app/data /app/data
COPY --from=builder /app/asset/img /app/asset/img

# Place venv on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Ensure data directory is writable by non-root user
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# For GPU workloads, run with: docker run --runtime=nvidia --gpus all
# or set deploy.resources.reservations.devices in docker-compose.yml

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

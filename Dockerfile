# Stage 1: Builder - Install dependencies
FROM python:3.12-slim AS builder

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV from official image (faster than pip install)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies with cache mount for faster builds
# Use --system to install directly (no venv in Docker)
# uv will automatically use uv.lock if present for reproducibility
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -e .

# Copy application code for editable install
COPY . .

# Install the project itself in editable mode (without dependencies)
RUN uv pip install --system --no-deps -e .

# Stage 2: Runtime - Minimal production image
FROM python:3.12-slim AS runtime

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy UV binary from builder (needed for potential runtime operations)
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/app/static/uploads && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Install the project itself in editable mode (without dependencies)
# Need to do this as root before switching to appuser
RUN uv pip install --system --no-deps -e .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8000)); s.close()" || exit 1

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head || true && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

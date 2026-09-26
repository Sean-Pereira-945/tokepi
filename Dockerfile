# Build Stage
FROM python:3.12-slim as builder

WORKDIR /app
COPY pyproject.toml ./
# Create a dummy README and driftguard package for dependency resolution
RUN touch README.md && mkdir driftguard && touch driftguard/__init__.py
RUN pip install --no-cache-dir build && \
    pip wheel --no-deps --wheel-dir /app/wheels -e .

# Production Stage
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies needed for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
# Install python dependencies
COPY pyproject.toml ./
RUN touch README.md && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir uvicorn psycopg2-binary redis

# Copy source code
COPY driftguard /app/driftguard

EXPOSE 8000

CMD ["uvicorn", "driftguard.routes:app", "--host", "0.0.0.0", "--port", "8000"]

# syntax=docker/dockerfile:1

# 1. Build the dashboard into driftguard/server/static
FROM node:22-alpine AS dashboard
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2. Build the Python wheel with the dashboard bundled
FROM python:3.12-slim AS wheel
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml README.md MANIFEST.in ./
COPY driftguard/ driftguard/
COPY --from=dashboard /src/driftguard/server/static/ driftguard/server/static/
RUN python -m build --wheel --outdir /dist

# 3. Runtime image
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DRIFTGUARD_ENV=production \
    DATABASE_URL=sqlite:////data/driftguard.db
COPY --from=wheel /dist/*.whl /tmp/
RUN pip install --no-cache-dir "$(ls /tmp/*.whl)[all]" && rm /tmp/*.whl \
    && useradd --system --uid 10001 --home-dir /data driftguard \
    && mkdir -p /data && chown driftguard /data
USER driftguard
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"
CMD ["driftguard-server", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

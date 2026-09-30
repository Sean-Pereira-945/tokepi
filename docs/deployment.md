# Deployment

## Docker Compose (recommended for self-hosting)

[`docker-compose.yml`](../docker-compose.yml) runs three services: the API and
dashboard (two workers), PostgreSQL 16, and Redis 7. Only the API port is
published. The database and cache are reachable only inside the compose network.

```bash
cp .env.example .env
# Required in .env:
#   DRIFTGUARD_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
#   POSTGRES_PASSWORD=<a strong password>
docker compose up -d --build
docker compose ps          # api shows "healthy" once /health passes
```

After you've created your own account, set `DRIFTGUARD_ALLOW_SIGNUP=false` in
`.env` and run `docker compose up -d` so strangers can't register.

## The image

The [`Dockerfile`](../Dockerfile) builds in three stages:

1. Node 22 builds the dashboard.
2. A Python stage builds the `driftguard` wheel with the dashboard bundled.
3. A slim Python 3.12 runtime installs the wheel with all extras.

The runtime stage has these properties:

- It runs as an unprivileged user (UID 10001).
- It sets `DRIFTGUARD_ENV=production`.
- It stores SQLite in `/data` if no `DATABASE_URL` is given. Mount a volume
  there.
- It trusts `X-Forwarded-*` headers (`--proxy-headers`), so rate limits see real
  client IPs behind a proxy.
- Its `HEALTHCHECK` calls `GET /health`, which checks the database.

```bash
docker build -t driftguard .
docker run -p 8000:8000 -e DRIFTGUARD_SECRET_KEY=... -v driftguard-data:/data driftguard
```

## TLS and reverse proxy

The app doesn't terminate TLS. Put it behind a proxy that does. With Caddy,
certificates are automatic:

```caddyfile
driftguard.example.com {
    reverse_proxy localhost:8000
}
```

With nginx, forward the headers and allow WebSocket upgrades on `/ws/`:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Without Docker

```bash
pip install "driftguard[all]"      # server + PostgreSQL + Redis drivers
export DRIFTGUARD_ENV=production DRIFTGUARD_SECRET_KEY=... \
       DATABASE_URL=postgresql://... REDIS_URL=redis://...
driftguard-server --host 0.0.0.0 --workers 4 --proxy-headers
```

Wheels published to PyPI include the built dashboard. If you install from a
source checkout, run `npm ci && npm run build` in `frontend/` first.

## Scaling

- **Workers and replicas.** Any number can run against the same PostgreSQL and
  Redis. Redis is **required** once there's more than one process: without it,
  each worker keeps its own rate-limit counters and only delivers realtime
  alerts to its own WebSocket clients.
- **Load balancers** must allow WebSocket upgrades for `/ws/projects/*`. Sticky
  sessions aren't needed.
- **Retention** runs in every worker. Pruning the same rows twice is harmless.

## Upgrades and backups

- **Schema migrations** run automatically at startup and are additive. They add
  tables, columns, and indexes, and hash v0.3 plaintext API keys. Back up the
  database before upgrading.
- **PostgreSQL backup:** `docker compose exec db pg_dump -U driftguard driftguard > backup.sql`.
- **SQLite backup:** stop the server and copy the file, or use `sqlite3 driftguard.db ".backup backup.db"`.
- **Changing `DRIFTGUARD_SECRET_KEY`** signs everyone out. It doesn't affect
  project API keys.

## Upgrading from 0.3

- Start the server with a `DATABASE_URL` that points at the old database. Data
  is kept, and the old plaintext API keys keep working. From then on they're
  stored only as hashes.
- The 0.3 `default` account and the old `sessions` table are left in place, but
  nothing uses them. Accounts from 0.3 had no passwords. Register a new account,
  then either recreate your projects or move them to the new account in SQL:
  `UPDATE projects SET account_id = '<new id>' WHERE account_id = 'default';`
- `uvicorn driftguard.routes:app` becomes `driftguard-server`.
- 0.3 SDK clients keep working against a 0.4 server, because the single-event
  endpoints they call still exist. The 0.4 SDK uses the new batch endpoints, so
  it needs a 0.4 server. The list of breaking changes is in
  [CHANGELOG.md](../CHANGELOG.md).

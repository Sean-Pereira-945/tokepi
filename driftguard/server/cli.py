"""``driftguard-server`` command: run the API and dashboard with uvicorn."""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="driftguard-server", description="Run the DriftGuard server.")
    parser.add_argument("--host", default=os.getenv("DRIFTGUARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("DRIFTGUARD_WORKERS", "1")),
        help="Worker processes. Set REDIS_URL when using more than one.",
    )
    parser.add_argument("--reload", action="store_true", help="Reload on code changes (development).")
    parser.add_argument(
        "--proxy-headers", action="store_true", help="Trust X-Forwarded-* headers from a reverse proxy."
    )
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(
        "driftguard.server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        workers=None if args.reload else args.workers,
        reload=args.reload,
        proxy_headers=args.proxy_headers,
        forwarded_allow_ips="*" if args.proxy_headers else None,
    )


if __name__ == "__main__":
    main()

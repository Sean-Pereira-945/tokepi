"""Push alerts to dashboard WebSocket clients.

``publish`` is safe to call from any thread (FastAPI runs sync endpoints in a
thread pool). With Redis configured, messages fan out through pub/sub so every
server worker reaches its own connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_CHANNEL = "driftguard:realtime"


class Broadcaster:
    def __init__(self, redis_url: str | None = None) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._redis_url = redis_url
        self._redis: Any = None
        self._listener: threading.Thread | None = None
        self._stopping = threading.Event()

    async def start(self) -> None:
        """Bind to the running event loop and start the Redis listener if configured."""
        self._loop = asyncio.get_running_loop()
        if not self._redis_url:
            return
        try:
            import redis

            self._redis = redis.Redis.from_url(self._redis_url)
            pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(_CHANNEL)
        except Exception as exc:
            logger.warning("Realtime Redis fan-out unavailable, using local delivery only: %s", exc)
            self._redis = None
            return
        self._listener = threading.Thread(target=self._listen, args=(pubsub,), daemon=True, name="driftguard-realtime")
        self._listener.start()

    def stop(self) -> None:
        self._stopping.set()

    def _listen(self, pubsub: Any) -> None:
        while not self._stopping.is_set():
            try:
                message = pubsub.get_message(timeout=1.0)
            except Exception as exc:
                logger.warning("Realtime Redis listener error: %s", exc)
                self._stopping.wait(2.0)
                continue
            if message and message.get("type") == "message":
                payload = json.loads(message["data"])
                self._schedule(payload["project_id"], payload["message"])

    async def connect(self, project_id: str, websocket: WebSocket, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self._connections[project_id].add(websocket)

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        self._connections[project_id].discard(websocket)

    def publish(self, project_id: str, message: dict[str, Any]) -> None:
        """Send ``message`` to every client watching ``project_id``."""
        if self._redis is not None:
            try:
                self._redis.publish(_CHANNEL, json.dumps({"project_id": project_id, "message": message}))
                return
            except Exception as exc:
                logger.warning("Realtime Redis publish failed, delivering locally: %s", exc)
        self._schedule(project_id, message)

    def _schedule(self, project_id: str, message: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed() or not self._connections.get(project_id):
            return
        asyncio.run_coroutine_threadsafe(self._deliver(project_id, message), self._loop)

    async def _deliver(self, project_id: str, message: dict[str, Any]) -> None:
        for websocket in list(self._connections.get(project_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(project_id, websocket)

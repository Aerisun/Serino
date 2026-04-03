from __future__ import annotations

import asyncio

import httpx


class SyncASGITransport(httpx.BaseTransport):
    def __init__(self, app) -> None:
        self._app = app

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        body = request.content
        response_started: dict[str, object] = {}
        response_body = bytearray()
        request_complete = False

        async def receive() -> dict[str, object]:
            nonlocal request_complete
            if request_complete:
                await asyncio.sleep(0)
                return {"type": "http.disconnect"}
            request_complete = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        async def send(message: dict[str, object]) -> None:
            message_type = str(message.get("type") or "")
            if message_type == "http.response.start":
                response_started["status"] = int(message["status"])
                response_started["headers"] = list(message.get("headers") or [])
                return
            if message_type == "http.response.body":
                response_body.extend(bytes(message.get("body") or b""))

        async def run_app() -> None:
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": request.method,
                "scheme": request.url.scheme,
                "path": request.url.path,
                "raw_path": request.url.raw_path.split(b"?", 1)[0],
                "query_string": request.url.query,
                "root_path": "",
                "headers": [(name.lower(), value) for name, value in request.headers.raw],
                "client": ("testclient", 50000),
                "server": (request.url.host, request.url.port or (443 if request.url.scheme == "https" else 80)),
            }
            await self._app(scope, receive, send)

        asyncio.run(run_app())

        headers = response_started.get("headers") or []
        status_code = int(response_started.get("status") or 500)
        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=bytes(response_body),
            request=request,
        )

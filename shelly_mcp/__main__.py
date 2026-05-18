#!/usr/bin/env python3
import argparse
import contextlib
import os
from contextlib import asynccontextmanager

import uvicorn
from anyio import ClosedResourceError
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from shelly_mcp import mcp

_ENV_TOKEN = "SHELLY_MCP_TOKEN"


class _SuppressClosedResource:
    """Silently drops ClosedResourceError at the outermost ASGI layer.

    The MCP Streamable HTTP transport raises ClosedResourceError when a client
    disconnects or a session expires while a tool is still running. The SDK does
    not catch this internally, so it propagates to uvicorn and produces a noisy
    500 traceback. The error is harmless — the response simply has nowhere to go.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.app(scope, receive, send)
        except ClosedResourceError:
            pass


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects requests that do not carry the correct Bearer token.

    Set SHELLY_MCP_TOKEN in the environment to enable. When the variable is
    absent or empty the middleware is not added and all requests pass through.
    """

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[len("Bearer "):] != self._token:
            return JSONResponse(
                {"error": "Unauthorized — valid Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="shelly-mcp",
        description="Shelly Smart Home MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
Without flags runs stdio (for Claude Desktop / local MCP clients).
Flags can be combined: --sse --http is equivalent to --server.

Authentication (HTTP modes only):
  Set {_ENV_TOKEN} to require a Bearer token on all HTTP requests.
  Example: export {_ENV_TOKEN}=mysecrettoken
""",
    )
    parser.add_argument("--sse",    action="store_true", help="Enable SSE transport             (/sse, /messages)")
    parser.add_argument("--http",   action="store_true", help="Enable Streamable HTTP transport  (/mcp)")
    parser.add_argument("--server", action="store_true", help="Enable both SSE and Streamable HTTP (shorthand for --sse --http)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Bind port (default: 8000)")
    return parser.parse_args()


def _build_app(sse: bool, http: bool) -> ASGIApp:
    routes = []
    lifespans = []

    if sse:
        src = mcp.sse_app()
        routes += list(src.routes)
        lc = getattr(src.router, "lifespan_context", None)
        if lc:
            lifespans.append(lc)

    if http:
        src = mcp.streamable_http_app()
        routes += list(src.routes)
        lc = getattr(src.router, "lifespan_context", None)
        if lc:
            lifespans.append(lc)

    @asynccontextmanager
    async def combined_lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for lc in lifespans:
                await stack.enter_async_context(lc(app))
            yield

    app = Starlette(routes=routes, lifespan=combined_lifespan)

    token = os.environ.get(_ENV_TOKEN, "").strip()
    if token:
        app.add_middleware(BearerAuthMiddleware, token=token)

    return _SuppressClosedResource(app)


def main() -> None:
    args = _parse_args()

    want_sse  = args.sse  or args.server
    want_http = args.http or args.server

    if not want_sse and not want_http:
        mcp.run()
        return

    host, port = args.host, args.port
    token_set = bool(os.environ.get(_ENV_TOKEN, "").strip())

    if want_sse:
        print(f"Shelly MCP  SSE:  http://{host}:{port}/sse")
    if want_http:
        print(f"Shelly MCP  HTTP: http://{host}:{port}/mcp")
    if token_set:
        print(f"Auth:       Bearer token active ({_ENV_TOKEN} is set)")
    else:
        print(f"Auth:       none  (set {_ENV_TOKEN} to enable Bearer auth)")

    uvicorn.run(_build_app(want_sse, want_http), host=host, port=port)


if __name__ == "__main__":
    main()

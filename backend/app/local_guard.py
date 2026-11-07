"""ローカルAPIを、起動のたびに発行するトークンと Origin / Host で守る。"""

from __future__ import annotations

import hmac
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 開発中の Vite と、配布版（file:// は Origin が "null"）だけを許可する
ALLOWED_ORIGINS = {
    "null",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
}
ALLOWED_HOSTS = {"127.0.0.1:8787", "localhost:8787"}
LOOPBACK_CLIENTS = {"127.0.0.1", "::1"}
TOKEN_HEADER = "x-pchc-token"


def load_api_token() -> str:
    """Electron が渡したトークンを使う。無ければこのプロセス専用の乱数にする。"""
    configured = os.environ.get("PCHC_API_TOKEN", "").strip()
    if configured:
        return configured
    return secrets.token_urlsafe(32)


API_TOKEN = load_api_token()


def token_matches(presented: str) -> bool:
    if not presented or not API_TOKEN:
        return False
    try:
        return hmac.compare_digest(presented.encode("utf-8"), API_TOKEN.encode("utf-8"))
    except Exception:
        return False


class LocalApiGuard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        host = (request.headers.get("host") or "").strip().lower()
        if host not in ALLOWED_HOSTS:
            return JSONResponse(status_code=403, content={"detail": "許可されていないHostです"})

        client_host = request.client.host if request.client else ""
        if client_host not in LOOPBACK_CLIENTS:
            return JSONResponse(status_code=403, content={"detail": "ローカル以外からの接続は拒否しました"})

        origin = request.headers.get("origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "許可されていないOriginです"})

        # ブラウザの事前確認（OPTIONS）にはトークンが付かない
        if request.method != "OPTIONS" and not token_matches(request.headers.get(TOKEN_HEADER, "")):
            return JSONResponse(status_code=401, content={"detail": "認証トークンが正しくありません"})

        return await call_next(request)

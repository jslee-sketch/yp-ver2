# app/middleware/admin_auth.py
"""
Admin route protection middleware.
Requires valid JWT with role='admin' for all /admin/* endpoints.
"""
from __future__ import annotations

import os
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET_KEY") or "dev-only-change-in-production"
ALGORITHM = "HS256"

# /admin/* routes that should be protected
ADMIN_PREFIX = "/admin/"

# Exempt paths (health checks etc.)
EXEMPT_PATHS = {"/admin/health"}


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only guard /admin/* paths
        if not path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        # Exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # OPTIONS (CORS preflight) — pass through
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return Response(
                content='{"detail":"Not authenticated"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[7:]  # strip "Bearer "

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            role = payload.get("role", "")
            if role != "admin":
                return Response(
                    content='{"detail":"Admin access required"}',
                    status_code=403,
                    media_type="application/json",
                )
        except JWTError:
            return Response(
                content='{"detail":"Invalid or expired token"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)

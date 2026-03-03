# app/middleware/rate_limit.py
"""
인메모리 Rate Limiter.
- 기본: IP당 60req/분
- AI 엔드포인트: 10req/분
- Admin 엔드포인트: 30req/분
"""
from __future__ import annotations

import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_rpm: int = 60):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.requests: dict = defaultdict(list)
        self.path_limits = {
            "/ai/": 10,
            "/v3_6/pingpong/": 10,
            "/admin/": 30,
        }

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        path = request.url.path

        rpm = self.default_rpm
        # Use matched path prefix as bucket key so different route groups
        # don't share a bucket (e.g. /v3_6/pingpong/ vs /v3_6/reservations)
        matched_prefix = None
        for prefix, limit in self.path_limits.items():
            if path.startswith(prefix):
                rpm = limit
                matched_prefix = prefix
                break

        if matched_prefix:
            key = f"{client_ip}:{matched_prefix}"
        else:
            seg = path.split("/")[1] if "/" in path else path
            key = f"{client_ip}:{seg}"
        self.requests[key] = [t for t in self.requests[key] if now - t < 60]

        if len(self.requests[key]) >= rpm:
            return Response(
                content='{"detail": "rate_limit_exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        self.requests[key].append(now)
        return await call_next(request)

# app/services/coupang_search.py
"""쿠팡 파트너스 API 상품 검색"""

import hmac
import hashlib
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

COUPANG_ACCESS_KEY = os.environ.get("COUPANG_ACCESS_KEY", "")
COUPANG_SECRET_KEY = os.environ.get("COUPANG_SECRET_KEY", "")


def _generate_hmac(method: str, url_path: str, secret_key: str) -> str:
    """쿠팡 API HMAC 서명 생성."""
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = dt + method + url_path
    sig = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, "
        f"signed-date={dt}, signature={sig}"
    )


def search_coupang_products(keyword: str, limit: int = 10) -> list:
    """쿠팡 파트너스 API로 상품 검색. 키 미설정 시 빈 리스트 반환."""
    if not COUPANG_ACCESS_KEY or not COUPANG_SECRET_KEY:
        return []

    try:
        encoded_kw = quote(keyword, safe="")
        url_path = (
            f"/v2/providers/affiliate_open_api/apis/openapi/products/search"
            f"?keyword={encoded_kw}&limit={limit}"
        )
        auth = _generate_hmac("GET", url_path, COUPANG_SECRET_KEY)

        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"https://api-gateway.coupang.com{url_path}",
                headers={
                    "Authorization": auth,
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            print(f"[COUPANG] API error: {resp.status_code} {resp.text[:200]}", flush=True)
            return []

        data = resp.json()
        products = data.get("data", {}).get("productData", [])

        results = []
        for p in products:
            price = p.get("productPrice", 0)
            if price <= 0:
                continue
            results.append({
                "title": p.get("productName", ""),
                "price": int(price),
                "link": p.get("productUrl", ""),
                "source": "coupang",
                "mall": "쿠팡",
                "is_rocket": p.get("isRocket", False),
            })

        print(f"[COUPANG] '{keyword}': {len(results)}건", flush=True)
        return results

    except Exception as e:
        print(f"[COUPANG] error: {e}", flush=True)
        return []

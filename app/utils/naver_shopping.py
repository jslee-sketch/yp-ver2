"""
네이버 쇼핑 API 공용 유틸
- app/routers/deal_ai_helper.py : 딜 개설 시 시장가 조회
- tools/pingpong_sidecar_openai.py : 가격 검색 (별도 구현 유지, 이 모듈로 교체 가능)
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

import requests
from pydantic import BaseModel

# FastAPI main.py에 dotenv가 없으므로 best-effort로 .env 로드
try:
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_Path(__file__).parent.parent.parent / ".env")
except Exception:
    pass

_NAVER_API_URL = "https://openapi.naver.com/v1/search/shop.json"
_TIMEOUT = 4.0  # seconds


class NaverProductResult(BaseModel):
    """네이버 쇼핑 검색 결과 1건"""
    product_name: str
    lowest_price: int
    highest_price: Optional[int] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    mall_name: Optional[str] = None
    category1: Optional[str] = None
    category2: Optional[str] = None
    brand: Optional[str] = None


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _get_creds() -> tuple[str, str]:
    cid = (os.getenv("NAVER_CLIENT_ID") or "").strip()
    sec = (os.getenv("NAVER_CLIENT_SECRET") or "").strip()
    return cid, sec


def _parse_items(items: list) -> List[NaverProductResult]:
    results = []
    for item in items:
        lp = int(item.get("lprice") or 0)
        hp_raw = item.get("hprice") or "0"
        hp = int(hp_raw) if hp_raw else 0
        results.append(NaverProductResult(
            product_name=_clean_html(item.get("title", "")),
            lowest_price=lp,
            highest_price=hp if hp > lp else None,
            image_url=item.get("image"),
            product_url=item.get("link"),
            mall_name=item.get("mallName"),
            category1=item.get("category1"),
            category2=item.get("category2"),
            brand=_clean_html(item.get("brand", "")) or None,
        ))
    return results


def search_naver_shopping(
    query: str,
    display: int = 5,
    sort: str = "sim",
) -> Optional[NaverProductResult]:
    """
    네이버 쇼핑 검색 API → 관련성(sim) 기준 상위 1건 반환.
    최저가 정렬을 쓰면 케이스/액세서리가 걸릴 수 있으므로 sim 순위 1위 사용.
    실패 시 None (서버 로직 중단 없음).
    """
    cid, sec = _get_creds()
    if not cid or not sec:
        print("[naver_shopping] ⚠️ NAVER API 키 미설정 — NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 확인")
        return None
    try:
        resp = requests.get(
            _NAVER_API_URL,
            headers={
                "X-Naver-Client-Id": cid,
                "X-Naver-Client-Secret": sec,
            },
            params={"query": query, "display": display, "sort": sort},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"[naver_shopping] HTTP {resp.status_code} for query={query!r}")
            return None
        items = resp.json().get("items", [])
        if not items:
            return None
        results = _parse_items(items)
        # sim 정렬 기준 상위 1건 (네이버 API 반환 순서 유지)
        return results[0] if results else None
    except Exception as e:
        print(f"[naver_shopping] API 호출 실패: {e}")
        return None


def search_naver_shopping_multi(
    query: str,
    display: int = 5,
    sort: str = "sim",
) -> List[NaverProductResult]:
    """
    네이버 쇼핑 검색 API → 여러 결과 반환 (가격 비교용).
    실패 시 빈 리스트.
    """
    cid, sec = _get_creds()
    if not cid or not sec:
        return []
    try:
        resp = requests.get(
            _NAVER_API_URL,
            headers={
                "X-Naver-Client-Id": cid,
                "X-Naver-Client-Secret": sec,
            },
            params={"query": query, "display": display, "sort": sort},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
        return _parse_items(items)
    except Exception:
        return []

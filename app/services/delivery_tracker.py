# app/services/delivery_tracker.py
"""
택배 배송조회 서비스 — SweetTracker API 연동.
SWEETTRACKER_API_KEY 없으면 mock 모드.
"""
from __future__ import annotations

import os, json
from typing import Optional
from datetime import datetime

SWEETTRACKER_API_KEY = os.environ.get("SWEETTRACKER_API_KEY", "")
SWEETTRACKER_BASE = "http://info.sweettracker.co.kr/api/v1"

# 택배사 코드 매핑
CARRIER_CODES: dict[str, str] = {
    "CJ대한통운": "04",
    "한진택배": "05",
    "롯데택배": "08",
    "우체국택배": "01",
    "로젠택배": "06",
    "경동택배": "23",
    "대신택배": "22",
    "일양로지스": "11",
    "합동택배": "32",
    "GS Postbox": "24",
    "GSMNtoN": "40",
    "쿠팡로켓배송": "36",
    "카카오T당일배송": "54",
    "CU편의점택배": "46",
}


def get_carrier_code(carrier_name: str) -> str:
    """택배사 이름 → 코드 (퍼지 매칭)"""
    # 정확 매칭
    if carrier_name in CARRIER_CODES:
        return CARRIER_CODES[carrier_name]
    # 부분 매칭
    for name, code in CARRIER_CODES.items():
        if name in carrier_name or carrier_name in name:
            return code
    # 키워드 매칭
    cl = carrier_name.lower().replace(" ", "")
    if "cj" in cl or "대한" in cl:
        return "04"
    if "한진" in cl:
        return "05"
    if "롯데" in cl:
        return "08"
    if "우체국" in cl:
        return "01"
    if "로젠" in cl:
        return "06"
    if "경동" in cl:
        return "23"
    return "04"  # 기본: CJ대한통운


async def track_delivery(carrier_name: str, tracking_number: str) -> dict:
    """스마트택배 API로 배송 추적"""
    if not SWEETTRACKER_API_KEY:
        return {"success": False, "error": "API 키 미설정"}

    carrier_code = get_carrier_code(carrier_name)

    url = f"{SWEETTRACKER_BASE}/trackingInfo"
    params = {
        "t_key": SWEETTRACKER_API_KEY,
        "t_code": carrier_code,
        "t_invoice": tracking_number.strip(),
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if data.get("code") == "104":
            return {"success": False, "error": "운송장 번호를 찾을 수 없습니다"}

        tracking_details = data.get("trackingDetails", [])

        if not tracking_details:
            return {
                "success": True,
                "status": "READY",
                "status_label": "배송 준비",
                "level": 1,
                "carrier": carrier_name,
                "tracking_number": tracking_number,
                "details": [],
            }

        latest = tracking_details[-1]
        level = data.get("level", 1)

        # level → 상태 매핑
        # 1: 배송준비, 2: 집하, 3: 배송중, 4: 지역도착, 5: 배달중, 6: 배달완료
        status_map = {
            1: ("READY", "배송 준비"),
            2: ("COLLECTING", "집하 완료"),
            3: ("IN_TRANSIT", "배송 중"),
            4: ("IN_TRANSIT", "지역 도착"),
            5: ("OUT_FOR_DELIVERY", "배달 중"),
            6: ("DELIVERED", "배달 완료"),
        }

        status, status_label = status_map.get(level, ("READY", "확인 중"))

        details = []
        for d in tracking_details:
            details.append({
                "time": d.get("timeString", ""),
                "where": d.get("where", ""),
                "kind": d.get("kind", ""),
                "telno": d.get("telno", ""),
            })

        return {
            "success": True,
            "status": status,
            "status_label": status_label,
            "level": level,
            "carrier": carrier_name,
            "tracking_number": tracking_number,
            "sender": data.get("senderName", ""),
            "receiver": data.get("receiverName", ""),
            "product": data.get("itemName", ""),
            "details": details,
            "latest": {
                "time": latest.get("timeString", ""),
                "where": latest.get("where", ""),
                "kind": latest.get("kind", ""),
            },
        }
    except Exception as e:
        if "Timeout" in type(e).__name__:
            return {"success": False, "error": "API 응답 시간 초과"}
        return {"success": False, "error": str(e)}


async def get_carrier_list() -> list:
    """스마트택배 지원 택배사 목록"""
    if not SWEETTRACKER_API_KEY:
        return [{"Code": code, "Name": name} for name, code in CARRIER_CODES.items()]

    url = f"{SWEETTRACKER_BASE}/companyInfo"
    params = {"t_key": SWEETTRACKER_API_KEY}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        return data.get("Company", [])
    except Exception:
        return [{"Code": code, "Name": name} for name, code in CARRIER_CODES.items()]

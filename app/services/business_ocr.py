# app/services/business_ocr.py
"""
GPT-4o Vision을 이용한 사업자등록증 OCR 파싱.
base64 인코딩된 이미지를 GPT-4o에 전달하여 사업자 정보를 추출한다.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 지원하는 MIME 타입
_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_MAP.get(f".{ext}", "image/jpeg")


async def ocr_business_registration(image_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    사업자등록증 이미지를 GPT-4o Vision으로 파싱하여 구조화된 데이터를 반환한다.

    Returns:
        {
            "business_name": str,
            "business_number": str,
            "representative_name": str,
            "address": str,
            "business_type": str,
            "business_item": str,
        }
    """
    from app.llm_client import get_client

    client = get_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = _guess_mime(filename)

    prompt = (
        "이 이미지는 한국 사업자등록증입니다. 다음 정보를 정확히 추출하여 JSON으로 반환하세요.\n"
        "반드시 아래 형식의 JSON만 반환하세요 (다른 텍스트 없이):\n"
        "{\n"
        '  "business_name": "상호(법인명)",\n'
        '  "business_number": "사업자등록번호 (예: 123-45-67890)",\n'
        '  "representative_name": "대표자명",\n'
        '  "address": "사업장 소재지",\n'
        '  "business_type": "업태",\n'
        '  "business_item": "종목"\n'
        "}\n"
        "읽을 수 없는 항목은 빈 문자열로 넣으세요."
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=500,
            temperature=0,
        )

        raw = resp.choices[0].message.content.strip()
        # JSON 블록 추출 (```json ... ``` 감싸인 경우 대비)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        # 필수 키 보장
        keys = ["business_name", "business_number", "representative_name",
                "address", "business_type", "business_item"]
        return {k: parsed.get(k, "") for k in keys}

    except json.JSONDecodeError:
        logger.error("OCR 응답 JSON 파싱 실패: %s", raw if "raw" in dir() else "N/A")
        raise ValueError("사업자등록증 OCR 결과를 파싱할 수 없습니다.")
    except Exception as e:
        logger.error("OCR 요청 실패: %s", e)
        raise

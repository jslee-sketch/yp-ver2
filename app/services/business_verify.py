# app/services/business_verify.py
"""
국세청 사업자등록정보 진위확인 및 상태조회 서비스.
공공데이터포털(data.go.kr) API 사용.
환경변수: NTS_API_KEY (없으면 검증 스킵)
"""
import os
import re
import logging

import requests

logger = logging.getLogger(__name__)

NTS_API_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"


def _get_api_key() -> str | None:
    return os.environ.get("NTS_API_KEY")


def verify_business_number(biz_number: str) -> dict:
    """
    사업자등록번호 진위확인.
    Returns: {valid: bool|None, status: str, tax_type: str, message: str}
    """
    clean = re.sub(r"[-\\s]", "", biz_number or "")
    if len(clean) != 10 or not clean.isdigit():
        return {"valid": False, "status": "", "tax_type": "", "message": "사업자등록번호 형식이 올바르지 않습니다 (숫자 10자리)"}

    api_key = _get_api_key()
    if not api_key:
        logger.warning("[BIZ-VERIFY] NTS_API_KEY 미설정 → 검증 스킵")
        return {"valid": None, "status": "", "tax_type": "", "message": "검증 서비스 미설정 (NTS_API_KEY 필요)"}

    try:
        r = requests.post(
            NTS_API_URL,
            json={"b_no": [clean]},
            params={"serviceKey": api_key},
            timeout=10,
        )
        data = r.json()

        if data.get("data") and len(data["data"]) > 0:
            result = data["data"][0]
            status = result.get("b_stt", "")
            tax_type = result.get("tax_type", "")
            valid = status == "계속사업자"
            return {
                "valid": valid,
                "status": status,
                "tax_type": tax_type,
                "message": f"사업자 상태: {status}" if status else "조회 결과 없음",
            }

        return {"valid": False, "status": "", "tax_type": "", "message": "조회 결과 없음"}

    except Exception as e:
        logger.error("[BIZ-VERIFY] API 호출 실패: %s", e)
        return {"valid": None, "status": "", "tax_type": "", "message": "검증 서비스 일시 불가"}

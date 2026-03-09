# app/services/gpt_price_estimator.py
"""GPT-4o-mini 기반 시장가 추정"""

import json
from app.llm_client import get_client


def estimate_price_with_gpt(
    product_name: str,
    brand: str = "",
    options: str = "",
    user_target_price: int = 0,
) -> dict:
    """GPT-4o-mini로 제품 시장가 추정. 실패 시 빈 결과 반환."""
    try:
        client = get_client()

        ctx = f"제품: {product_name}"
        if brand:
            ctx += f"\n브랜드: {brand}"
        if options:
            ctx += f"\n옵션: {options}"
        if user_target_price > 0:
            ctx += f"\n구매자 희망가: {user_target_price:,}원"

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{ctx}\n\n"
                        "이 제품의 한국 시장가를 추정해주세요. 반드시 JSON으로만 답해주세요:\n"
                        "{\n"
                        '  "estimated_price": 추정 시장가 (정수, 원),\n'
                        '  "price_range_min": 최저 예상가 (정수),\n'
                        '  "price_range_max": 최고 예상가 (정수),\n'
                        '  "confidence": "high/medium/low",\n'
                        '  "reasoning": "추정 근거 한 줄",\n'
                        '  "is_online_purchasable": true/false,\n'
                        '  "category_hint": "전자기기/가전/자동차/패션/식품/기타"\n'
                        "}\n\n"
                        "주의:\n"
                        "- 자동차, 부동산 등 온라인 쇼핑몰에서 판매하지 않는 제품이면 is_online_purchasable: false\n"
                        "- 가격 범위가 넓으면 confidence: low\n"
                        "- 구매자 희망가가 있으면 참고하되 그것에 맞추지는 마"
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=300,
            timeout=15,
        )

        text = (resp.choices[0].message.content or "").strip()

        try:
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)
        except Exception:
            result = {
                "estimated_price": 0,
                "confidence": "low",
                "reasoning": text[:200],
                "is_online_purchasable": True,
            }

        ep = result.get("estimated_price", 0)
        print(
            f"[GPT-PRICE] {product_name}: {ep:,}원 ({result.get('confidence', '?')})",
            flush=True,
        )
        return result

    except Exception as e:
        print(f"[GPT-PRICE] error: {e}", flush=True)
        return {"estimated_price": 0, "confidence": "low", "error": str(e)}

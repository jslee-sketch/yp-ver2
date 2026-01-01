# scripts/bump_offer_capacity.py
"""
테스트용으로 특정 Offer의 total_available_qty 를 강제로 늘려주는 스크립트.

- 기본값: offer_id=1, total_available_qty=10 으로 세팅
- 필요하면 아래 DEFAULT_OFFER_ID / NEW_TOTAL_QTY 를 수정해서 사용

실행 방법 (프로젝트 루트에서):
    (venv) python scripts/bump_offer_capacity.py
"""

import os
import sys
from pathlib import Path

# -----------------------------
# 1) 프로젝트 루트 경로를 sys.path 에 추가
# -----------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent  # .../yp-ver2
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 이제부터는 app 패키지 import 가능
# -----------------------------
# 2) DB 세션 팩토리 import (프로젝트 구조에 따라 다를 수 있어 대비)
# -----------------------------
try:
    from app.database import SessionLocal as SessionFactory  # 가장 흔한 패턴
except ImportError:
    try:
        from app.database import Session as SessionFactory   # crud.py 에서 이렇게 쓰는 경우 대비
    except ImportError:
        print("❌ DB Session 팩토리를 찾을 수 없습니다. app.database 안을 확인해주세요.")
        raise

from app.models import Offer

# -----------------------------
# 3) 설정값
# -----------------------------
DEFAULT_OFFER_ID = int(os.getenv("YP_BUMP_OFFER_ID", "1"))
NEW_TOTAL_QTY = int(os.getenv("YP_BUMP_OFFER_TOTAL_QTY", "10"))  # 테스트용 capacity


def main():
    print(f"✅ Using project root: {ROOT_DIR}")
    print(f"✅ Target offer_id: {DEFAULT_OFFER_ID}")
    print(f"✅ New total_available_qty: {NEW_TOTAL_QTY}")
    print()

    session = SessionFactory()
    try:
        offer = session.get(Offer, DEFAULT_OFFER_ID)
        if not offer:
            print(f"❌ Offer(id={DEFAULT_OFFER_ID}) not found in DB")
            return

        before_total = getattr(offer, "total_available_qty", None)
        before_sold = getattr(offer, "sold_qty", None)
        before_reserved = getattr(offer, "reserved_qty", None)

        print("🔎 Before:")
        print(f"   total_available_qty = {before_total}")
        print(f"   sold_qty            = {before_sold}")
        print(f"   reserved_qty        = {before_reserved}")
        print()

        # 실제로 capacity 올리기
        offer.total_available_qty = NEW_TOTAL_QTY
        session.add(offer)
        session.commit()
        session.refresh(offer)

        after_total = getattr(offer, "total_available_qty", None)
        after_sold = getattr(offer, "sold_qty", None)
        after_reserved = getattr(offer, "reserved_qty", None)

        print("✅ After:")
        print(f"   total_available_qty = {after_total}")
        print(f"   sold_qty            = {after_sold}")
        print(f"   reserved_qty        = {after_reserved}")
        print()
        print("🎉 bump_offer_capacity 완료")

    finally:
        session.close()


if __name__ == "__main__":
    main()
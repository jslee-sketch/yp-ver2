"""
DB 컬럼 + 데이터 정합성 검증 스크립트
로컬 SQLite 또는 PostgreSQL 연결로 전체 검증 수행
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine
import sqlalchemy as sa
from sqlalchemy import text


def verify():
    inspector = sa.inspect(engine)
    errors = []
    warns = []
    checks = 0

    # =========================================================
    # 1. 필수 테이블 존재 확인
    # =========================================================
    required_tables = [
        'users', 'buyers', 'sellers', 'actuators',
        'deals', 'deal_rounds', 'offers', 'reservations',
        'reservation_settlements', 'point_transactions',
        'actuator_commissions', 'actuator_reward_logs',
        'seller_reviews', 'seller_rating_aggregates',
        'event_logs', 'user_notifications', 'deal_chat_messages',
        'policy_declarations', 'pingpong_logs',
    ]
    optional_tables = [
        'tax_invoices', 'business_info_change_logs',
    ]
    existing_tables = inspector.get_table_names()
    for t in required_tables:
        checks += 1
        if t not in existing_tables:
            errors.append(f"MISSING TABLE: {t}")
    for t in optional_tables:
        checks += 1
        if t not in existing_tables:
            warns.append(f"OPTIONAL TABLE NOT FOUND: {t}")

    # =========================================================
    # 2. 컬럼 검증
    # =========================================================
    column_checks = {
        'actuators': [
            'contract_agreed', 'contract_agreed_at', 'contract_version',
            'withholding_tax_rate', 'resident_id_last',
            'is_business', 'business_name', 'business_number',
        ],
        'sellers': [
            'business_name', 'business_number', 'verified_at',
            'level', 'nickname',
        ],
        'buyers': ['nickname', 'level', 'points'],
        'reservation_settlements': ['status', 'seller_id', 'platform_commission_amount', 'seller_payout_amount'],
    }
    for tbl, cols in column_checks.items():
        if tbl not in existing_tables:
            continue
        actual = {c['name'] for c in inspector.get_columns(tbl)}
        for col in cols:
            checks += 1
            if col not in actual:
                errors.append(f"MISSING COLUMN: {tbl}.{col}")

    # =========================================================
    # 3. 레코드 수 검증
    # =========================================================
    with engine.connect() as conn:
        count_tables = [
            'buyers', 'sellers', 'actuators', 'deals',
            'offers', 'reservations', 'reservation_settlements',
            'point_transactions', 'seller_reviews',
        ]
        print("\n--- Record Counts ---")
        for tbl in count_tables:
            if tbl not in existing_tables:
                continue
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                print(f"  {tbl}: {cnt}")
                checks += 1
            except Exception as e:
                warns.append(f"COUNT FAILED: {tbl} ({e})")

        # Tax invoices
        if 'tax_invoices' in existing_tables:
            try:
                cnt = conn.execute(text("SELECT COUNT(*) FROM tax_invoices")).scalar()
                print(f"  tax_invoices: {cnt}")
                checks += 1
            except Exception:
                pass

        # =========================================================
        # 4. 역할별 사용자 수
        # =========================================================
        print("\n--- User Role Counts ---")
        for tbl in ['buyers', 'sellers', 'actuators']:
            if tbl not in existing_tables:
                continue
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                print(f"  {tbl}: {cnt}")
            except Exception:
                pass

        # =========================================================
        # 5. 정산 상태별 분포
        # =========================================================
        if 'reservation_settlements' in existing_tables:
            print("\n--- Settlement Status Distribution ---")
            try:
                rows = conn.execute(text(
                    "SELECT status, COUNT(*) as cnt FROM reservation_settlements GROUP BY status ORDER BY cnt DESC"
                )).fetchall()
                for row in rows:
                    print(f"  {row[0]}: {row[1]}")
                checks += 1
            except Exception as e:
                warns.append(f"SETTLEMENT STATUS QUERY FAILED: {e}")

        # =========================================================
        # 6. 세금계산서 상태별 분포
        # =========================================================
        if 'tax_invoices' in existing_tables:
            print("\n--- Tax Invoice Status Distribution ---")
            try:
                rows = conn.execute(text(
                    "SELECT status, COUNT(*) as cnt FROM tax_invoices GROUP BY status ORDER BY cnt DESC"
                )).fetchall()
                for row in rows:
                    print(f"  {row[0]}: {row[1]}")

                total_amt = conn.execute(text(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM tax_invoices"
                )).scalar()
                print(f"  Total Amount: {total_amt:,}")
                checks += 1
            except Exception as e:
                warns.append(f"TAX INVOICE QUERY FAILED: {e}")

        # =========================================================
        # 7. 포인트 현황
        # =========================================================
        if 'point_transactions' in existing_tables:
            print("\n--- Point Summary ---")
            try:
                earned = conn.execute(text(
                    "SELECT COALESCE(SUM(amount), 0) FROM point_transactions WHERE amount > 0"
                )).scalar()
                used = conn.execute(text(
                    "SELECT COALESCE(SUM(amount), 0) FROM point_transactions WHERE amount < 0"
                )).scalar()
                print(f"  Earned: {earned:,}")
                print(f"  Used: {used:,}")
                print(f"  Net: {earned + used:,}")
                checks += 1
            except Exception as e:
                warns.append(f"POINT QUERY FAILED: {e}")

        # =========================================================
        # 8. 풀 플로우 정합성 (딜→오퍼→예약 연결)
        # =========================================================
        print("\n--- Flow Integrity ---")
        try:
            deals = conn.execute(text("SELECT COUNT(*) FROM deals")).scalar()
            offers = conn.execute(text("SELECT COUNT(*) FROM offers")).scalar()
            reservations = conn.execute(text("SELECT COUNT(*) FROM reservations")).scalar()
            print(f"  Deals: {deals} → Offers: {offers} → Reservations: {reservations}")

            # Orphan offers (offer without valid deal)
            orphan_offers = conn.execute(text(
                "SELECT COUNT(*) FROM offers WHERE deal_id NOT IN (SELECT id FROM deals)"
            )).scalar()
            if orphan_offers > 0:
                warns.append(f"ORPHAN OFFERS: {orphan_offers} offers with invalid deal_id")
            else:
                print(f"  Orphan offers: 0 (OK)")

            # Orphan reservations
            orphan_res = conn.execute(text(
                "SELECT COUNT(*) FROM reservations WHERE offer_id NOT IN (SELECT id FROM offers)"
            )).scalar()
            if orphan_res > 0:
                warns.append(f"ORPHAN RESERVATIONS: {orphan_res} reservations with invalid offer_id")
            else:
                print(f"  Orphan reservations: 0 (OK)")
            checks += 2
        except Exception as e:
            warns.append(f"FLOW INTEGRITY CHECK FAILED: {e}")

    # =========================================================
    # 결과 출력
    # =========================================================
    print(f"\n{'='*50}")
    print(f"DB Verification: {checks} checks, {len(errors)} errors, {len(warns)} warnings")
    print(f"{'='*50}")

    if errors:
        for e in errors:
            print(f"  X {e}")

    if warns:
        for w in warns:
            print(f"  ! {w}")

    if not errors:
        print("  OK: All critical checks passed")
        print("\nPASSED")
        return 0
    else:
        print(f"\nFAILED: {len(errors)} critical issue(s)")
        return 1


if __name__ == '__main__':
    sys.exit(verify())

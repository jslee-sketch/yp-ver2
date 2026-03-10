"""
DB 컬럼 검증 스크립트
역할 스트레스 테스트에 필요한 모든 DB 컬럼이 존재하는지 확인
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine
import sqlalchemy as sa

def verify():
    inspector = sa.inspect(engine)
    errors = []
    checks = 0

    # 필수 테이블 목록
    required_tables = [
        'users', 'buyers', 'sellers', 'actuators',
        'deals', 'deal_rounds', 'offers', 'reservations',
        'reservation_settlements', 'point_transactions',
        'actuator_commissions', 'actuator_reward_logs',
        'seller_reviews', 'seller_rating_aggregates',
        'event_logs', 'user_notifications', 'deal_chat_messages',
        'policy_declarations', 'pingpong_logs',
    ]
    existing_tables = inspector.get_table_names()
    for t in required_tables:
        checks += 1
        if t not in existing_tables:
            errors.append(f"MISSING TABLE: {t}")

    # Actuator 추가 컬럼
    actuator_cols = [
        'contract_agreed', 'contract_agreed_at', 'contract_version',
        'withholding_tax_rate', 'resident_id_last',
        'is_business', 'business_name', 'business_number',
    ]
    if 'actuators' in existing_tables:
        actual = {c['name'] for c in inspector.get_columns('actuators')}
        for col in actuator_cols:
            checks += 1
            if col not in actual:
                errors.append(f"MISSING COLUMN: actuators.{col}")

    # Seller 추가 컬럼
    seller_cols = [
        'business_name', 'business_number', 'is_approved',
        'level', 'nickname',
    ]
    if 'sellers' in existing_tables:
        actual = {c['name'] for c in inspector.get_columns('sellers')}
        for col in seller_cols:
            checks += 1
            if col not in actual:
                errors.append(f"MISSING COLUMN: sellers.{col}")

    # Buyer 추가 컬럼
    buyer_cols = ['nickname', 'level', 'points']
    if 'buyers' in existing_tables:
        actual = {c['name'] for c in inspector.get_columns('buyers')}
        for col in buyer_cols:
            checks += 1
            if col not in actual:
                errors.append(f"MISSING COLUMN: buyers.{col}")

    # ReservationSettlement 컬럼
    settlement_cols = ['status', 'seller_id', 'platform_fee', 'seller_amount']
    if 'reservation_settlements' in existing_tables:
        actual = {c['name'] for c in inspector.get_columns('reservation_settlements')}
        for col in settlement_cols:
            checks += 1
            if col not in actual:
                errors.append(f"MISSING COLUMN: reservation_settlements.{col}")

    # 결과 출력
    print(f"\n{'='*50}")
    print(f"DB Verification: {checks} checks, {len(errors)} errors")
    print(f"{'='*50}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        print(f"\nFAILED: {len(errors)} issue(s) found")
        return 1
    else:
        print("  ✅ All tables and columns verified")
        print("\nPASSED")
        return 0

if __name__ == '__main__':
    sys.exit(verify())

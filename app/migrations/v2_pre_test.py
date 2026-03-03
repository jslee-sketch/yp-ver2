# app/migrations/v2_pre_test.py
"""
테스트 전 DB 마이그레이션.
실행: python -m app.migrations.v2_pre_test
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "app" / "ypver2.db"


MIGRATIONS = [
    # Buyer 계정 상태
    "ALTER TABLE buyers ADD COLUMN is_active BOOLEAN DEFAULT 1",
    "ALTER TABLE buyers ADD COLUMN withdrawn_at DATETIME",
    "ALTER TABLE buyers ADD COLUMN is_banned BOOLEAN DEFAULT 0",
    "ALTER TABLE buyers ADD COLUMN banned_until DATETIME",
    "ALTER TABLE buyers ADD COLUMN ban_reason TEXT",
    # Seller 계정 상태
    "ALTER TABLE sellers ADD COLUMN is_active BOOLEAN DEFAULT 1",
    "ALTER TABLE sellers ADD COLUMN withdrawn_at DATETIME",
    "ALTER TABLE sellers ADD COLUMN is_banned BOOLEAN DEFAULT 0",
    "ALTER TABLE sellers ADD COLUMN banned_until DATETIME",
    "ALTER TABLE sellers ADD COLUMN ban_reason TEXT",
    # Actuator 탈퇴
    "ALTER TABLE actuators ADD COLUMN withdrawn_at DATETIME",
    # Reservation 배송 자동확인
    "ALTER TABLE reservations ADD COLUMN delivery_auto_confirmed BOOLEAN DEFAULT 0",
    "ALTER TABLE reservations ADD COLUMN delivery_confirmed_source TEXT",
    # 신고 테이블
    """CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL,
        reporter_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'OPEN',
        resolution TEXT,
        action_taken TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME
    )""",
    # 업로드 파일 테이블
    """CREATE TABLE IF NOT EXISTS uploaded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_size INTEGER,
        mime_type TEXT,
        uploaded_by_id INTEGER,
        uploaded_by_type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    # 정산 지급 요청 테이블
    """CREATE TABLE IF NOT EXISTS payout_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        settlement_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        bank_code TEXT,
        account_number TEXT,
        account_holder TEXT,
        status TEXT DEFAULT 'PENDING',
        requested_at DATETIME,
        completed_at DATETIME,
        pg_transaction_id TEXT,
        failure_reason TEXT,
        retry_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_payout_batch ON payout_requests(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_payout_status ON payout_requests(status)",
    # 정책 제안서 테이블
    """CREATE TABLE IF NOT EXISTS policy_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        proposal_type TEXT NOT NULL,
        target_param TEXT,
        current_value TEXT,
        proposed_value TEXT,
        anomaly_alerts TEXT,
        evidence_summary TEXT,
        status TEXT DEFAULT 'PROPOSED',
        proposed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        proposed_by TEXT DEFAULT 'pingpong_auto',
        reviewed_at DATETIME,
        reviewed_by TEXT,
        review_note TEXT,
        applied_at DATETIME,
        rolled_back_at DATETIME,
        rollback_reason TEXT,
        yaml_snapshot_before TEXT,
        yaml_snapshot_after TEXT
    )""",
]


def run():
    conn = sqlite3.connect(str(DB_PATH))
    ok = 0
    skip = 0
    fail = 0
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
            ok += 1
        except Exception as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg:
                skip += 1
            else:
                print(f"  FAIL: {sql[:60]}... -> {e}")
                fail += 1
    conn.commit()
    conn.close()
    print(f"Migration done: ok={ok}, skip={skip}, fail={fail}")


if __name__ == "__main__":
    run()

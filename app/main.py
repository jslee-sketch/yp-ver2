# app/main.py
from __future__ import annotations

import sys as _sys
import io as _io
# Force UTF-8 stdout/stderr on Windows (cp949 crashes on emoji)
if _sys.stdout and hasattr(_sys.stdout, 'buffer'):
    try:
        _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

import builtins
import traceback
import os
import asyncio
import importlib
import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# .env 파일 로드 (OPENAI_API_KEY, NAVER_CLIENT_ID 등)
try:
    from pathlib import Path as _P
    from dotenv import load_dotenv as _ld
    _ld(_P(__file__).parent.parent / ".env", override=True)
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# 초기화(DB/모델 로드)
from app.config import project_rules as R

from app import crud, models, database
from app.database import Base, engine

# ✅ 모든 모델 명시적 import — 하나라도 빠지면 테이블 안 만들어짐
from app.models import (  # noqa: F401
    User, Buyer, Seller, Actuator,
    PointTransaction, ActuatorCommission, ActuatorRewardLog,
    Deal, DealAILog, DealParticipant, DealRound,
    DealChatMessage, DealViewer,
    UserNotification,
    Offer, OfferPolicy,
    Reservation, ReservationSettlement, ReservationPayment,
    SellerReview, SellerRatingAggregate,
    CustomerInquiry,
    EventLog,
    PolicyDeclaration, PolicyProposal,
    PingpongLog, PingpongCase,
    SpectatorPrediction, SpectatorMonthlyStats, SpectatorBadge,
    Report, UploadedFile, PayoutRequest,
    Announcement,
    UserBehaviorLog, UserProfile,
    TaxInvoice, TaxInvoiceStatus, BusinessInfoChangeLog,
    CustomReportTemplate,
    UserInterest, NotificationSetting,
    PreRegister,
    UserConditionOverride, EcountMapping,
    DonzzulActuator, DonzzulStore, DonzzulDeal, DonzzulVoucher,
    DonzzulVoteWeek, DonzzulVote, DonzzulSettlement, DonzzulChatMessage,
    Dispute, SellerExternalRating, SellerVerificationScore, ActuatorSellerDisconnection,
)

# ═══════════════════════════════════════════════════════════
# ✅ DB 테이블 생성 — 3단계 cascade (module-level, 반드시 성공해야 함)
# ═══════════════════════════════════════════════════════════
import sqlalchemy as _sa

_DATABASE_URL_RAW = os.environ.get("DATABASE_URL", "")
print(f"[DB_INIT] DATABASE_URL type: {'postgresql' if 'postgres' in _DATABASE_URL_RAW else 'sqlite'}", flush=True)
print(f"[DB_INIT] engine.url = {engine.url}", flush=True)

_registered = sorted(Base.metadata.tables.keys())
print(f"[DB_INIT] Registered models: {len(_registered)}", flush=True)

_REQUIRED = {"users", "buyers", "sellers", "deals", "offers", "reservations",
             "reservation_settlements", "point_transactions", "policy_declarations"}

# ── Method 1: SQLAlchemy create_all ──
print("[DB_INIT] Method 1: Base.metadata.create_all()", flush=True)
try:
    Base.metadata.create_all(bind=engine)
    _inspector = _sa.inspect(engine)
    _db_tables = sorted(_inspector.get_table_names())
    _missing = _REQUIRED - set(_db_tables)
    print(f"[DB_INIT] M1 result: {len(_db_tables)} tables, missing={_missing or 'none'}", flush=True)
except Exception as _cae:
    print(f"[DB_INIT] M1 FAILED: {_cae.__class__.__name__}: {_cae}", flush=True)
    traceback.print_exc()

# ── ALTER TABLE: add new columns to existing tables ──
_alter_cols = [
    ("users", "name", "VARCHAR(50)"),
    ("deals", "brand", "VARCHAR"),
    ("deals", "model_number", "VARCHAR"),
    ("deals", "options", "TEXT"),
    ("deals", "free_text", "TEXT"),
    ("deals", "category", "VARCHAR"),
    ("deals", "product_detail", "VARCHAR"),
    ("deals", "product_code", "VARCHAR"),
    ("deals", "condition", "VARCHAR"),
    ("deals", "market_price", "FLOAT"),
    ("deals", "price_evidence", "TEXT"),
    ("deal_ai_logs", "note", "TEXT"),
    ("sellers", "business_license_image", "VARCHAR(500)"),
    ("sellers", "ecommerce_permit_image", "VARCHAR(500)"),
    ("sellers", "bankbook_image", "VARCHAR(500)"),
    ("sellers", "external_ratings", "TEXT"),
    # actuator 신규 컬럼
    ("actuators", "password_hash", "VARCHAR(255)"),
    ("actuators", "nickname", "VARCHAR(50)"),
    ("actuators", "bank_name", "VARCHAR(100)"),
    ("actuators", "account_number", "VARCHAR(100)"),
    ("actuators", "account_holder", "VARCHAR(100)"),
    ("actuators", "bankbook_image", "VARCHAR(500)"),
    ("actuators", "is_business", "BOOLEAN DEFAULT FALSE"),
    ("actuators", "business_name", "VARCHAR(255)"),
    ("actuators", "business_number", "VARCHAR(50)"),
    ("actuators", "ecommerce_permit_number", "VARCHAR(100)"),
    ("actuators", "business_address", "VARCHAR(500)"),
    ("actuators", "business_zip_code", "VARCHAR(20)"),
    ("actuators", "company_phone", "VARCHAR(50)"),
    ("actuators", "business_license_image", "VARCHAR(500)"),
    ("actuators", "ecommerce_permit_image", "VARCHAR(500)"),
    # actuator 위탁계약 + 원천징수
    ("actuators", "contract_agreed", "BOOLEAN DEFAULT FALSE"),
    ("actuators", "contract_agreed_at", "DATETIME"),
    ("actuators", "contract_version", "VARCHAR(20)"),
    ("actuators", "withholding_tax_rate", "DOUBLE PRECISION DEFAULT 0.033"),
    ("actuators", "resident_id_last", "VARCHAR(10)"),
    # seller ERP 추가 컬럼
    ("sellers", "shipping_policy", "TEXT"),
    ("reservations", "refund_type", "VARCHAR(20)"),
    ("reviews", "seller_reply", "TEXT"),
    ("reviews", "replied_at", "DATETIME"),
    # 비밀번호 재설정 토큰
    ("buyers", "reset_token", "VARCHAR(64)"),
    ("buyers", "reset_token_expires_at", "TIMESTAMP"),
    ("sellers", "reset_token", "VARCHAR(64)"),
    ("sellers", "reset_token_expires_at", "TIMESTAMP"),
    ("actuators", "reset_token", "VARCHAR(64)"),
    ("actuators", "reset_token_expires_at", "TIMESTAMP"),
    # 판매자 생년월일 / 성별
    ("sellers", "birth_date", "TIMESTAMP"),
    ("sellers", "gender", "VARCHAR(10)"),
    # announcements
    ("announcements", "is_pinned", "BOOLEAN DEFAULT FALSE"),
    ("announcements", "is_published", "BOOLEAN DEFAULT FALSE"),
    ("announcements", "target_role", "VARCHAR(20) DEFAULT 'all'"),
    ("announcements", "author", "VARCHAR(100)"),
    ("announcements", "updated_at", "DATETIME"),
    # dispute 확장 컬럼
    ("reservations", "dispute_reason", "VARCHAR(500)"),
    ("reservations", "dispute_resolution", "VARCHAR(500)"),
    ("reservations", "dispute_admin_id", "INTEGER"),
    # 배송 추적 확장 컬럼
    ("reservations", "order_number", "VARCHAR(20)"),
    ("reservations", "delivery_status", "VARCHAR(30)"),
    ("reservations", "delivery_last_detail", "TEXT"),
    ("reservations", "delivery_last_checked_at", "TIMESTAMP"),
    ("reservations", "auto_confirm_deadline", "TIMESTAMP"),
    # 소셜 로그인 (seller / actuator)
    ("sellers", "social_provider", "VARCHAR(20)"),
    ("sellers", "social_id", "VARCHAR(100)"),
    ("actuators", "social_provider", "VARCHAR(20)"),
    ("actuators", "social_id", "VARCHAR(100)"),
    # 세금계산서용 사업자 추가 필드 (Seller)
    ("sellers", "representative_name", "VARCHAR(50)"),
    ("sellers", "business_type", "VARCHAR(100)"),
    ("sellers", "business_item", "VARCHAR(100)"),
    ("sellers", "tax_invoice_email", "VARCHAR(100)"),
    ("sellers", "business_verified", "BOOLEAN DEFAULT FALSE"),
    ("sellers", "business_registered_at", "TIMESTAMP"),
    ("sellers", "business_updated_at", "TIMESTAMP"),
    # 세금계산서용 사업자 추가 필드 (Actuator)
    ("actuators", "representative_name", "VARCHAR(50)"),
    ("actuators", "business_type", "VARCHAR(100)"),
    ("actuators", "business_item", "VARCHAR(100)"),
    ("actuators", "tax_invoice_email", "VARCHAR(100)"),
    ("actuators", "business_verified", "BOOLEAN DEFAULT FALSE"),
    # FCM 푸시 토큰
    ("buyers", "fcm_token", "VARCHAR(500)"),
    ("buyers", "fcm_updated_at", "TIMESTAMP"),
    ("sellers", "fcm_token", "VARCHAR(500)"),
    ("sellers", "fcm_updated_at", "TIMESTAMP"),
    ("actuators", "fcm_token", "VARCHAR(500)"),
    ("actuators", "fcm_updated_at", "TIMESTAMP"),
]
try:
    _insp = _sa.inspect(engine)
    _cols_cache: dict = {}
    def _get_existing(tbl: str) -> set:
        if tbl not in _cols_cache:
            _cols_cache[tbl] = {c["name"] for c in _insp.get_columns(tbl)} if _insp.has_table(tbl) else set()
        return _cols_cache[tbl]
    _need_alter = [(t, c, typ) for t, c, typ in _alter_cols if c not in _get_existing(t)]
    if _need_alter:
        for _tbl, _col, _typ in _need_alter:
            try:
                with engine.begin() as _conn:
                    _conn.execute(_sa.text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                print(f"[DB_INIT] Added column {_tbl}.{_col}", flush=True)
            except Exception as _col_err:
                print(f"[DB_INIT] Failed to add {_tbl}.{_col}: {_col_err}", flush=True)
    else:
        print("[DB_INIT] ALTER TABLE skipped — all columns exist", flush=True)
except Exception as _ae:
    print(f"[DB_INIT] ALTER TABLE error: {_ae}", flush=True)

# ── 긴급 수복: actuator 컬럼 직접 추가 (위 _alter_cols 실패 대비) ──
_emergency_actuator_cols = [
    ("contract_agreed", "BOOLEAN DEFAULT FALSE"),
    ("contract_agreed_at", "TIMESTAMP"),
    ("contract_version", "VARCHAR(20)"),
    ("withholding_tax_rate", "DOUBLE PRECISION DEFAULT 0.033"),
    ("resident_id_last", "VARCHAR(10)"),
]
try:
    _insp2 = _sa.inspect(engine)
    if _insp2.has_table("actuators"):
        _existing2 = {c["name"] for c in _insp2.get_columns("actuators")}
        for _ecol, _etyp in _emergency_actuator_cols:
            if _ecol not in _existing2:
                try:
                    with engine.begin() as _conn:
                        _conn.execute(_sa.text(f"ALTER TABLE actuators ADD COLUMN {_ecol} {_etyp}"))
                    print(f"[DB_INIT] Emergency added actuators.{_ecol}", flush=True)
                except Exception as _ee:
                    print(f"[DB_INIT] Emergency fail actuators.{_ecol}: {_ee}", flush=True)
except Exception as _e2:
    print(f"[DB_INIT] Emergency migration error: {_e2}", flush=True)

# ── ALTER COLUMN TYPE: VARCHAR→TEXT for base64 image columns ──
_alter_type_sqls = [
    "ALTER TABLE sellers ALTER COLUMN business_license_image TYPE TEXT",
    "ALTER TABLE sellers ALTER COLUMN ecommerce_permit_image TYPE TEXT",
    "ALTER TABLE sellers ALTER COLUMN bankbook_image TYPE TEXT",
    "ALTER TABLE sellers ALTER COLUMN external_ratings TYPE TEXT",
    "ALTER TABLE actuators ALTER COLUMN bankbook_image TYPE TEXT",
    "ALTER TABLE actuators ALTER COLUMN business_license_image TYPE TEXT",
    "ALTER TABLE actuators ALTER COLUMN ecommerce_permit_image TYPE TEXT",
]
if "postgres" in _DATABASE_URL_RAW:
    try:
        with engine.begin() as _conn:
            for _sql in _alter_type_sqls:
                try:
                    _conn.execute(_sa.text(_sql))
                except Exception:
                    pass
        print("[DB_INIT] Image columns → TEXT OK", flush=True)
    except Exception as _te:
        print(f"[DB_INIT] Image columns error: {_te}", flush=True)

# ── Method 2: Raw psycopg fallback (PostgreSQL only) ──
if "postgres" in _DATABASE_URL_RAW:
    try:
        _m2_tables = set(_sa.inspect(engine).get_table_names())
        _m2_missing = _REQUIRED - _m2_tables
        if _m2_missing:
            print(f"[DB_INIT] Method 2: raw psycopg (missing: {_m2_missing})", flush=True)
            import psycopg
            _conn_url = _DATABASE_URL_RAW
            if "postgresql+psycopg://" in _conn_url:
                _conn_url = _conn_url.replace("postgresql+psycopg://", "postgresql://")
            elif "postgres://" in _conn_url and "postgresql://" not in _conn_url:
                _conn_url = _conn_url.replace("postgres://", "postgresql://")

            _raw_conn = psycopg.connect(_conn_url)
            _raw_cur = _raw_conn.cursor()

            from sqlalchemy.schema import CreateTable as _CT
            from sqlalchemy.dialects import postgresql as _pg_dialect

            for _tbl in Base.metadata.sorted_tables:
                if _tbl.name in _m2_tables:
                    continue
                try:
                    _ddl = _CT(_tbl, if_not_exists=True)
                    _sql = str(_ddl.compile(dialect=_pg_dialect.dialect())).strip()
                    _raw_cur.execute(_sql)
                    print(f"  [M2] created: {_tbl.name}", flush=True)
                except Exception as _te:
                    print(f"  [M2] {_tbl.name} FAILED: {_te}", flush=True)

            _raw_conn.commit()
            _raw_cur.close()
            _raw_conn.close()
            print("[DB_INIT] M2 done", flush=True)
        else:
            print("[DB_INIT] M2 skipped — all required tables exist", flush=True)
    except Exception as _e:
        print(f"[DB_INIT] M2 FAILED: {_e}", flush=True)
        traceback.print_exc()

# ── Final verification ──
try:
    _final_tables = sorted(_sa.inspect(engine).get_table_names())
    _final_missing = _REQUIRED - set(_final_tables)
    print(f"[DB_INIT] FINAL: {len(_final_tables)} tables, missing={_final_missing or 'none'}", flush=True)
except Exception as _ve:
    print(f"[DB_INIT] verification error: {_ve}", flush=True)


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

app = FastAPI(default_response_class=Utf8JSONResponse)



# 0) ORMModel shim
try:
    from app.schemas import ORMModel as _ORMModel  # type: ignore
except Exception:
    try:
        from pydantic import BaseModel as _ORMModel  # type: ignore
    except Exception:
        _ORMModel = object
builtins.ORMModel = _ORMModel


# 프로덕션에서는 상세 에러 숨김 (DEV_BYPASS=true일 때만 상세 노출)
_dev_bypass_env = os.environ.get("DEV_BYPASS", "false").lower() == "true"
DEV_DEBUG_ERRORS = _dev_bypass_env



def _as_utc_aware(dt: datetime) -> datetime:
    """
    DB/SQLite에서 tzinfo 없는 naive datetime이 오면 UTC로 간주해서 aware로 만든다.
    이미 tz-aware면 UTC로 변환한다.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --------------------------------------------------
# 예약 자동 만료 워커
# --------------------------------------------------
async def start_auto_expire_worker() -> None:
    """
    예약 자동 만료 워커
    - 항상 '다음으로 만료될 예약'의 expires_at 을 찾아서
      그 시각까지 정확히 기다렸다가 expire_reservations() 실행
    - 이론상 300초 + 수십 ms 정도의 오차로 맞게 됨
    """

    async def worker():
        while True:
            try:
                db = database.SessionLocal()

                # 1) 가장 빨리 만료될 PENDING 예약의 expires_at 찾기
                q = (
                    db.query(models.Reservation.expires_at)
                    .filter(
                        models.Reservation.status == "PENDING",
                        models.Reservation.expires_at.isnot(None),
                    )
                    .order_by(models.Reservation.expires_at.asc())
                    .limit(1)
                )
                row = q.first()
                db.close()

                if not row or not row[0]:
                    # 만료 대기 중인 예약이 없으면 60초 후 다시 체크
                    await asyncio.sleep(60)
                    continue

                next_expires_at = _as_utc_aware(row[0])

                if not isinstance(next_expires_at, datetime):
                    await asyncio.sleep(60)
                    continue

                # 2) 현재 시각과의 차이 (UTC 기준)
                now = datetime.now(timezone.utc)
                delay = (next_expires_at - now).total_seconds()

                # 이미 지났으면 바로 만료 스윕
                if delay < 0:
                    delay = 0

                # 3) 다음 만료 시각까지 기다리기
                await asyncio.sleep(delay)

                # 4) 실제 만료 처리
                db = database.SessionLocal()
                expired = crud.expire_reservations(db)
                db.close()

                if expired:
                    print(f"[AUTO_EXPIRE] expired={expired} (next_at={next_expires_at})")

            except Exception as e:
                # 에러가 나도 워커가 멈추지 않도록
                print(f"[AUTO_EXPIRE] error: {e}")
                await asyncio.sleep(30)  # 잠깐 쉬고 다시 시도

    asyncio.create_task(worker())


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup 역할
    try:
        R.set_test_now_utc(None)
    except Exception:
        pass

    # ✅ DB 테이블 생성 (module-level이 실패했을 경우 재시도)
    try:
        Base.metadata.create_all(bind=engine)
        _tbl_names = sorted(_sa.inspect(engine).get_table_names())
        print(f"✅ [lifespan] create_all OK — {len(_tbl_names)} tables: {_tbl_names[:5]}...")
    except Exception as e:
        print(f"❌ [lifespan] create_all FAILED: {e.__class__.__name__}: {e}")
        traceback.print_exc()

    # ✅ nickname 컬럼 마이그레이션 (기존 DB 호환)
    from sqlalchemy import text as _text
    for _tbl, _col in [("buyers", "nickname"), ("sellers", "nickname")]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} VARCHAR(30)"))
                _conn.commit()
                print(f"[migration] ALTER TABLE {_tbl} ADD COLUMN {_col} OK")
        except Exception:
            pass  # 이미 존재하면 무시

    # ✅ donzzul_vouchers FK 제거 (PostgreSQL only)
    for _fk_name in ["donzzul_vouchers_buyer_id_fkey", "donzzul_vouchers_gifted_to_fkey"]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_vouchers DROP CONSTRAINT IF EXISTS {_fk_name}"))
                _conn.commit()
                print(f"[migration] DROP CONSTRAINT {_fk_name} OK")
        except Exception:
            pass

    # ✅ donzzul_vouchers 신규 컬럼 마이그레이션
    _VOUCHER_NEW_COLS = [
        ("settlement_id", "INTEGER"),
        ("donated_at", "TIMESTAMP"),
        ("last_warning_days", "INTEGER"),
    ]
    for _col, _type in _VOUCHER_NEW_COLS:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_vouchers ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE donzzul_vouchers ADD COLUMN {_col} OK")
        except Exception:
            pass

    # ✅ donzzul_settlements period_start/period_end nullable 변경 (PostgreSQL)
    for _col in ["period_start", "period_end"]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_settlements ALTER COLUMN {_col} DROP NOT NULL"))
                _conn.commit()
                print(f"[migration] ALTER TABLE donzzul_settlements ALTER COLUMN {_col} DROP NOT NULL OK")
        except Exception:
            pass

    # ✅ donzzul_settlements 신규 컬럼 마이그레이션
    _SETTLEMENT_NEW_COLS = [
        ("total_amount", "INTEGER DEFAULT 0"),
        ("voucher_count", "INTEGER DEFAULT 0"),
        ("used_amount", "INTEGER DEFAULT 0"),
        ("donated_amount", "INTEGER DEFAULT 0"),
        ("payout_amount", "INTEGER DEFAULT 0"),
        ("approved_by", "INTEGER"),
        ("approved_at", "TIMESTAMP"),
        ("paid_at", "TIMESTAMP"),
        ("period_from", "TIMESTAMP"),
        ("period_to", "TIMESTAMP"),
    ]
    for _col, _type in _SETTLEMENT_NEW_COLS:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_settlements ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE donzzul_settlements ADD COLUMN {_col} OK")
        except Exception:
            pass

    # ✅ 돈쭐 채팅 컬럼 마이그레이션
    _CHAT_NEW_COLS = [
        ("sender_nickname", "VARCHAR(50)"),
        ("is_deleted", "BOOLEAN DEFAULT FALSE"),
    ]
    for _col, _type in _CHAT_NEW_COLS:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_chat_messages ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE donzzul_chat_messages ADD COLUMN {_col} OK")
        except Exception:
            pass

    # FK constraint drop for donzzul_chat_messages.sender_id (buyers table may not have the row)
    try:
        with engine.connect() as _conn:
            _conn.execute(_text("ALTER TABLE donzzul_chat_messages DROP CONSTRAINT IF EXISTS donzzul_chat_messages_sender_id_fkey"))
            _conn.commit()
            print("[migration] donzzul_chat_messages sender_id FK dropped")
    except Exception:
        pass

    # ✅ 돈쭐 투표 컬럼 마이그레이션
    _VOTE_NEW_COLS = [
        ("weight", "INTEGER DEFAULT 1"),
    ]
    for _col, _type in _VOTE_NEW_COLS:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_votes ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE donzzul_votes ADD COLUMN {_col} OK")
        except Exception:
            pass

    # Widen week_label column
    try:
        with engine.connect() as _conn:
            _conn.execute(_text("ALTER TABLE donzzul_vote_weeks ALTER COLUMN week_label TYPE VARCHAR(100)"))
            _conn.commit()
            print("[migration] donzzul_vote_weeks week_label widened to 100")
    except Exception:
        pass

    # FK constraint drops for donzzul_actuators
    for _fk_name in ["donzzul_actuators_user_id_fkey", "donzzul_actuators_actuator_id_fkey"]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_actuators DROP CONSTRAINT IF EXISTS {_fk_name}"))
                _conn.commit()
                print(f"[migration] donzzul_actuators {_fk_name} dropped")
        except Exception:
            pass

    # FK constraint drops for donzzul_votes
    for _fk_name in ["donzzul_votes_voter_id_fkey", "donzzul_votes_store_id_fkey"]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE donzzul_votes DROP CONSTRAINT IF EXISTS {_fk_name}"))
                _conn.commit()
                print(f"[migration] donzzul_votes {_fk_name} dropped")
        except Exception:
            pass

    # ✅ 돈쭐 배치 스케줄러 시작 (매 1시간)
    import threading, time as _time
    def _donzzul_batch_scheduler():
        while True:
            try:
                _time.sleep(3600)
                _db = SessionLocal()
                try:
                    from app.services.donzzul_batch import (
                        run_donzzul_expiry_batch,
                        run_donzzul_expiry_warning_batch,
                        run_donzzul_deal_expiry_batch,
                    )
                    r1 = run_donzzul_expiry_batch(_db)
                    r2 = run_donzzul_expiry_warning_batch(_db)
                    r3 = run_donzzul_deal_expiry_batch(_db)
                    if r1["donated_count"] or r2["warnings_sent"] or r3["closed_deals"]:
                        print(f"[DONZZUL BATCH] expired={r1['donated_count']} warned={r2['warnings_sent']} closed={r3['closed_deals']}", flush=True)
                finally:
                    _db.close()
            except Exception as e:
                print(f"[DONZZUL BATCH ERROR] {e}", flush=True)
    threading.Thread(target=_donzzul_batch_scheduler, daemon=True).start()
    print("[DONZZUL] Batch scheduler started (hourly)", flush=True)

    # ✅ seller 서류 컬럼 마이그레이션 (기존 DB 호환, SQLite + PostgreSQL)
    _SELLER_NEW_COLS = [
        ("ecommerce_permit_number", "VARCHAR(50)"),
        ("bank_name", "VARCHAR(50)"),
        ("account_number", "VARCHAR(50)"),
        ("account_holder", "VARCHAR(50)"),
        ("business_license_image", "VARCHAR(500)"),
        ("ecommerce_permit_image", "VARCHAR(500)"),
        ("bankbook_image", "VARCHAR(500)"),
    ]
    for _col, _type in _SELLER_NEW_COLS:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE sellers ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE sellers ADD COLUMN {_col} OK")
        except Exception:
            pass  # already exists

    # ✅ payment_method 컬럼 마이그레이션
    try:
        with engine.connect() as _conn:
            _conn.execute(_text("ALTER TABLE buyers ADD COLUMN payment_method VARCHAR(50)"))
            _conn.commit()
            print("[migration] ALTER TABLE buyers ADD COLUMN payment_method OK")
    except Exception:
        pass

    # ✅ social login 컬럼 마이그레이션
    for _col, _type in [("social_provider", "VARCHAR(20)"), ("social_id", "VARCHAR(100)")]:
        try:
            with engine.connect() as _conn:
                _conn.execute(_text(f"ALTER TABLE buyers ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migration] ALTER TABLE buyers ADD COLUMN {_col} OK")
        except Exception:
            pass

    # ✅ seed: DB가 완전히 비었으면 데모 데이터 삽입 (Railway 초기 배포 대응)
    try:
        _seed_db = database.SessionLocal()
        try:
            if _seed_db.query(models.Buyer).count() == 0:
                print("[seed] Empty DB detected — inserting demo data...")
                from passlib.context import CryptContext as _Ctx
                _pwd = _Ctx(schemes=["bcrypt"], deprecated="auto")
                _now = datetime.now(timezone.utc)
                _demo_buyer = models.Buyer(
                    name="Demo Buyer", email="demo@yeokping.com",
                    password_hash=_pwd.hash("demo1234"),
                    nickname="데모바이어", phone="010-0000-0000",
                    created_at=_now,
                )
                _seed_db.add(_demo_buyer)
                _seed_db.flush()
                _demo_seller = models.Seller(
                    email="seller@yeokping.com",
                    password_hash=_pwd.hash("seller1234"),
                    business_name="Demo Seller",
                    business_number="999-99-99998",
                    nickname="데모셀러",
                    created_at=_now,
                )
                _seed_db.add(_demo_seller)
                _seed_db.flush()
                _demo_deal = models.Deal(
                    product_name="에어팟 프로 2세대 (데모)",
                    creator_id=_demo_buyer.id,
                    desired_qty=10, current_qty=1,
                    target_price=280000, max_budget=350000,
                    anchor_price=359000, brand="Apple",
                    status="open", created_at=_now,
                )
                _seed_db.add(_demo_deal)
                _seed_db.commit()
                print(f"[seed] Created buyer #{_demo_buyer.id}, seller #{_demo_seller.id}, deal #{_demo_deal.id}")

            # admin seed (항상 실행 — 관리자 계정이 없으면 생성, 있으면 비밀번호 통일)
            _admin_exists = _seed_db.query(models.User).filter(models.User.email == "admin@yeokping.com").first()
            from passlib.context import CryptContext as _Ctx2
            _pwd2 = _Ctx2(schemes=["bcrypt"], deprecated="auto")
            if not _admin_exists:
                _admin = models.User(
                    email="admin@yeokping.com",
                    hashed_password=_pwd2.hash("admin1234!"),
                    name="관리자",
                    role="admin",
                    is_active=True,
                )
                _seed_db.add(_admin)
                _seed_db.commit()
                print("[seed] Admin account created: admin@yeokping.com / admin1234!", flush=True)
            else:
                # 비밀번호 통일 (admin1234!)
                if not _pwd2.verify("admin1234!", _admin_exists.hashed_password):
                    _admin_exists.hashed_password = _pwd2.hash("admin1234!")
                    _seed_db.commit()
                    print("[seed] Admin password reset to admin1234!", flush=True)

            # seller seed (항상 실행 — 테스트 판매자 계정이 없으면 생성)
            try:
                _seller_exists = _seed_db.query(models.Seller).filter(models.Seller.email == "seller@yeokping.com").first()
                if not _seller_exists:
                    from passlib.context import CryptContext as _Ctx3
                    _pwd3 = _Ctx3(schemes=["bcrypt"], deprecated="auto")
                    _seed_seller = models.Seller(
                        email="seller@yeokping.com",
                        password_hash=_pwd3.hash("seller1234!"),
                        business_name="테스트 판매자",
                        business_number="999-99-99999",
                        nickname="테스트셀러",
                        phone="01000000001",
                        is_active=True,
                        verified_at=datetime.now(timezone.utc),
                        level=6,
                    )
                    _seed_db.add(_seed_seller)
                    _seed_db.commit()
                    print("[seed] Seller created: seller@yeokping.com / seller1234!", flush=True)
            except Exception as _sse:
                _seed_db.rollback()
                print(f"[warn] seller seed failed: {_sse}", flush=True)
        finally:
            _seed_db.close()
    except Exception as _se:
        print(f"[warn] seed data failed: {_se}")

    # ✅ seed: 정책 선언 DB 자동 시드 (policy_declarations 테이블이 비어있으면 .md 파일에서 로드)
    try:
        _pol_db = database.SessionLocal()
        try:
            _pol_count = _pol_db.query(models.PolicyDeclaration).filter(
                models.PolicyDeclaration.is_active == True,
            ).count()
            if _pol_count == 0:
                print("[seed] policy_declarations empty — seeding from .md files...")
                _app_dir = _P(__file__).resolve().parent
                _doc_roots = [
                    _app_dir / "policy" / "docs" / "public",
                    _app_dir / "policy" / "docs" / "admin",
                    _app_dir / "policy" / "docs" / "admin" / "ssot",
                ]
                _pol_inserted = 0
                for _dr in _doc_roots:
                    if not _dr.exists():
                        continue
                    for _fp in sorted(_dr.rglob("*.md")):
                        if not _fp.is_file():
                            continue
                        _md_text = _fp.read_text(encoding="utf-8", errors="replace").strip()
                        if not _md_text:
                            continue
                        try:
                            _rel = _fp.relative_to(_app_dir / "policy" / "docs").as_posix().removesuffix(".md")
                        except Exception:
                            _rel = _fp.stem
                        _kl = _rel.lower()
                        _domain = (
                            "REFUND" if "refund" in _kl else
                            "SHIPPING" if "shipping" in _kl else
                            "SETTLEMENT" if "settlement" in _kl else
                            "FEES" if "fee" in _kl else
                            "TIERS" if "tier" in _kl else
                            "PRICING" if "pricing" in _kl or "price" in _kl else
                            "GUARDRAILS" if "guardrail" in _kl else
                            "TIME" if "time" in _kl else
                            "PARTICIPANTS" if "participant" in _kl else
                            "PINGPONG" if "pingpong" in _kl else
                            "ACTUATOR" if "actuator" in _kl else
                            "BUYER" if "buyer" in _kl else
                            "SELLER" if "seller" in _kl else
                            "GENERAL"
                        )
                        _title = _fp.stem
                        for _line in _md_text.splitlines():
                            _ls = _line.strip()
                            if _ls.startswith("# ") and _ls[2:].strip():
                                _title = _ls[2:].strip()
                                break
                        _pol_db.add(models.PolicyDeclaration(
                            domain=_domain,
                            policy_key=_rel,
                            title=_title,
                            description_md=_md_text,
                            version=1,
                            is_active=1,
                        ))
                        _pol_inserted += 1
                _pol_db.commit()
                print(f"[seed] Inserted {_pol_inserted} policy declarations")
            else:
                print(f"[seed] policy_declarations already has {_pol_count} active rows — skip")
        finally:
            _pol_db.close()
    except Exception as _pe:
        print(f"[warn] policy seed failed: {_pe}")

    # ✅ 주문번호 backfill (order_number가 없는 기존 예약에 자동 부여)
    try:
        _on_db = database.SessionLocal()
        try:
            from app.services.order_number import backfill_order_numbers
            _filled = backfill_order_numbers(_on_db)
            if _filled:
                print(f"[migration] Backfilled {_filled} order_numbers")
        finally:
            _on_db.close()
    except Exception as _one:
        print(f"[warn] order_number backfill failed: {_one}")

    # ✅ 워커 시작
    try:
        await start_auto_expire_worker()
    except Exception as e:
        print(f"[warn] start_auto_expire_worker failed: {e.__class__.__name__}: {e}")

    yield

    # shutdown 역할
    try:
        R.set_test_now_utc(None)
    except Exception:
        pass


app = FastAPI(title="Yeokping Ver2 API, version=3.5", lifespan=lifespan)


# 예외 핸들러
@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exc_handler(request, exc: Exception):
    # 항상 서버 로그에 기록
    print(f"[ERROR] {request.method} {request.url.path}: {exc.__class__.__name__}: {exc}", flush=True)
    traceback.print_exc()

    if DEV_DEBUG_ERRORS:
        tb_tail = traceback.format_exc().splitlines()[-1]
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "error": exc.__class__.__name__,
                    "msg": str(exc),
                    "where": f"{request.method} {request.url.path}",
                    "trace_tail": tb_tail,
                }
            },
        )
    # 프로덕션: 상세 에러 숨김
    return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


# CORS — 환경변수 ALLOWED_ORIGINS 로 제어 (쉼표 구분)
# 프로덕션: ALLOWED_ORIGINS=https://web-production-defb.up.railway.app,https://yeokping.com,https://www.yeokping.com
# 개발: ALLOWED_ORIGINS=* (기본값)
_allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Router include helper (한 번만 정의)
def _include_router_safe(module_path: str, attr_candidates: tuple[str, ...], *, label: str):
    full_mod = f"app.routers.{module_path}"
    try:
        # 스펙 존재여부 확인 (리로더 환경에서도 안전)
        if importlib.util.find_spec(full_mod) is None:
            print(f"[warn] Skip router [{label}]: spec not found for '{full_mod}'")
            return

        mod = importlib.import_module(full_mod)
        router_obj = None

        for name in attr_candidates:
            router_obj = getattr(mod, name, None)
            if router_obj is not None:
                break

        if router_obj is None:
            print(f"[warn] Skip router [{label}]: none of attrs {attr_candidates} found in {full_mod}")
            return

        app.include_router(router_obj)
        print(f"✅ Mounted router [{label}] from {full_mod}")

    except Exception as e:
        print(f"[warn] Skip router [{label}]: {e.__class__.__name__}: {e}")


# --------------------------------------------------
# 1️⃣ Buyer 관련 → Seller 관련 → 기본 프로필
# --------------------------------------------------
_include_router_safe("auth", ("router",), label="auth")
_include_router_safe("auth_social", ("router",), label="auth_social")
_include_router_safe("users", ("router",), label="users")

# Buyer 기본 / 확장
_include_router_safe("buyers", ("router",), label="buyers")
_include_router_safe("routes_extended.buyers_extended", ("router",), label="routes_extended.buyers")

# Seller 기본 / 확장 / 온보딩
_include_router_safe("sellers", ("router",), label="sellers")
_include_router_safe("routes_extended.sellers_extended", ("router",), label="routes_extended.sellers")
_include_router_safe("sellers_onboarding", ("router",), label="onboarding")

# Buyer / Seller 기본 카드용 정보
_include_router_safe("basic_info", ("router",), label="basic_info")


# --------------------------------------------------
# 2️⃣ Deal → Offer → Payment → Point
# --------------------------------------------------
_include_router_safe("deals", ("router",), label="deals")
_include_router_safe("reservations", ("router",), label="reservations")

# ✅ offers 모듈은 aggregator router 하나만 포함하면 됨
_include_router_safe("offers", ("router",), label="offers.v35")

# ✅ v3.6 offers + reservations 전용 라우터
_include_router_safe("offers_reservations_v3_6", ("router",), label="offers_reservations_v3_6")

_include_router_safe("actuators", ("router",), label="actuators")
_include_router_safe("me_actuator", ("router",), label="me_actuator")

# extras 가 별도 모듈이면 그대로 유지
_include_router_safe("offers_extras", ("router", "api"), label="offers_extras")

_include_router_safe("payments", ("router",), label="payments")
_include_router_safe("points", ("router",), label="points")


# ---------------------------------------------------
# Deal 채팅 관련
# ---------------------------------------------------
_include_router_safe("deal_chat", ("router",), label="deal_chat")


# --------------------------------------------------
# 3️⃣ 리뷰 / UI / 분석 계열
# --------------------------------------------------
_include_router_safe("reviews", ("router",), label="reviews")
_include_router_safe("ui_portal", ("router",), label="ui_portal")

# AI 보조. Deal의 제목/옵션 추천
_include_router_safe("deal_ai_helper", ("router",), label="deal_ai_helper")
_include_router_safe("deal_intents", ("router",), label="deal_intents")

_include_router_safe("dashboard", ("router",), label="dashboard")
_include_router_safe("insights_overview", ("router",), label="insights_overview")
_include_router_safe("insights", ("router",), label="insights")
_include_router_safe("activity_log", ("router",), label="activity_log")
_include_router_safe("preview_pack", ("router",), label="preview_pack")

# --------------------------------------------------
# 4️⃣ Admin / 시뮬레이션 / 정책
# --------------------------------------------------
_include_router_safe("admin_policy", ("router",), label="admin_policy")
_include_router_safe("admin_simulate", ("router",), label="admin_simulate")
_include_router_safe("admin_simulate_status", ("router",), label="admin_simulate_status")
_include_router_safe("simulate_v3_6", ("router",), label="simulate_v3_6")
_include_router_safe("simulate_v3_6_run", ("router",), label="simulate_v3_6_run")

_include_router_safe("settlements", ("router",), label="settlements")
_include_router_safe("admin_settlements", ("router",), label="admin_settlements")
_include_router_safe("tax_invoices", ("router",), label="tax_invoices")

# --------------------------------------------------
# Notification
# --------------------------------------------------
_include_router_safe("notifications", ("router",), label="notifications")

_include_router_safe("admin_refund_preview", ("router",), label="admin_refund_preview")
_include_router_safe("customer_inquiries", ("router",), label="customer_inquiries")

# --------------------------------------------------
# Spectator 관전자 시스템
# --------------------------------------------------
_include_router_safe("spectator", ("router",), label="spectator")

# --------------------------------------------------
# PINGPONG AI Agent
# --------------------------------------------------
_include_router_safe("pingpong", ("router",), label="pingpong")

# --------------------------------------------------
# Behavior Tracking & AI Profiling
# --------------------------------------------------
_include_router_safe("behavior", ("router",), label="behavior")

# --------------------------------------------------
# Delivery Tracking (SweetTracker)
# --------------------------------------------------
_include_router_safe("delivery_tracking", ("router",), label="delivery_tracking")

# --------------------------------------------------
# WebSocket 실시간 채팅
# --------------------------------------------------
_include_router_safe("deal_chat_ws", ("router",), label="deal_chat_ws")

# --------------------------------------------------
# 5️⃣ 플랫폼 필수 기능 (v2)
# --------------------------------------------------
_include_router_safe("account", ("router",), label="account")
_include_router_safe("admin_users", ("router",), label="admin_users")
_include_router_safe("reports", ("router",), label="reports")
_include_router_safe("uploads", ("router",), label="uploads")
_include_router_safe("delivery", ("router",), label="delivery")
_include_router_safe("admin_anomaly", ("router",), label="admin_anomaly")
_include_router_safe("admin_policy_proposals", ("router",), label="admin_policy_proposals")

# --------------------------------------------------
# Admin core / policy yaml / policy docs / announcements
# --------------------------------------------------
_include_router_safe("admin_core", ("router",), label="admin_core")
_include_router_safe("admin_custom_report", ("router",), label="admin_custom_report")
_include_router_safe("notification_settings", ("router",), label="notification_settings")
_include_router_safe("admin_policy_yaml", ("router",), label="admin_policy_yaml")
_include_router_safe("admin_policy_docs", ("router",), label="admin_policy_docs")
_include_router_safe("admin_announcements", ("router",), label="admin_announcements")
_include_router_safe("preregister", ("router",), label="preregister")

# --------------------------------------------------
# 🎮 Arena (배틀 아레나 미니게임)
# --------------------------------------------------
_include_router_safe("arena", ("router",), label="arena")

# --------------------------------------------------
# 📊 Public Demand Dashboard (공개 수요 대시보드)
# --------------------------------------------------
_include_router_safe("public_demand", ("router",), label="public_demand")

# 돈쭐 (착한 가게 응원 시스템)
_include_router_safe("donzzul", ("router",), label="donzzul")

# 분쟁 프로세스 v3
_include_router_safe("disputes", ("router",), label="disputes")

# 판매자 신뢰 엔진 v2
_include_router_safe("seller_trust", ("router",), label="seller_trust")

# 정적 파일 (이미지 업로드)
try:
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    import os as _os
    _os.makedirs("uploads", exist_ok=True)
    app.mount("/uploads", _StaticFiles(directory="uploads"), name="uploads")
except Exception as _e:
    print(f"[warn] static files mount failed: {_e}")

# WWW 리다이렉트: yeokping.com → www.yeokping.com
try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import RedirectResponse as _RedirectResponse

    class WwwRedirectMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            host = request.headers.get("host", "")
            if host.split(":")[0] == "yeokping.com":
                url = request.url
                new_url = str(url).replace("://yeokping.com", "://www.yeokping.com")
                if not new_url.startswith("https"):
                    new_url = new_url.replace("http://", "https://")
                return _RedirectResponse(new_url, status_code=301)
            return await call_next(request)

    app.add_middleware(WwwRedirectMiddleware)
    print("✅ WwwRedirectMiddleware loaded")
except Exception as _e:
    print(f"[warn] WwwRedirectMiddleware not loaded: {_e}")

# Admin Auth 미들웨어 — /admin/* 엔드포인트 JWT+role=admin 필수
try:
    from app.middleware.admin_auth import AdminAuthMiddleware
    app.add_middleware(AdminAuthMiddleware)
    print("✅ AdminAuthMiddleware loaded")
except Exception as _e:
    print(f"[warn] AdminAuthMiddleware not loaded: {_e}")

# Rate Limiting 미들웨어
try:
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, default_rpm=int(__import__('os').environ.get('RATE_LIMIT_RPM', '100')))
except Exception as _e:
    print(f"[warn] RateLimitMiddleware not loaded: {_e}")


# Health/Version
@app.get("/api/health")
def root():
    return {"message": "Yeokping Ver2 API(NO-AUTH) is running", "ok": True}


@app.get("/health")
def health():
    from sqlalchemy import text as _htext
    db_status = "ok"
    try:
        _hdb = next(database.get_db())
        _hdb.execute(_htext("SELECT 1"))
        _hdb.close()
    except Exception:
        db_status = "error"
    return {
        "ok": db_status == "ok",
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/debug/dist")
def debug_dist():
    import os as _dos
    from pathlib import Path as _DP
    _base = _DP(__file__).parent.parent
    paths = [
        str(_base / "frontend" / "dist"),
        str(_base / "frontend" / "dist" / "assets"),
        "frontend/dist",
        "frontend/dist/assets",
        "/app/frontend/dist",
        "/app/frontend/dist/assets",
    ]
    result = {"cwd": os.getcwd(), "base": str(_base)}
    for p in paths:
        if _dos.path.exists(p):
            try:
                result[p] = _dos.listdir(p)[:20]
            except Exception as e:
                result[p] = f"ERROR: {e}"
        else:
            result[p] = "NOT FOUND"
    # index.html 내용도 확인
    idx = _base / "frontend" / "dist" / "index.html"
    if idx.is_file():
        result["index.html_content"] = idx.read_text()[:500]
    else:
        result["index.html_content"] = "NOT FOUND"
    return result


@app.get("/api/env-check")
def env_check():
    """Deployment diagnostic — shows which env vars are set (values hidden)."""
    keys = ["OPENAI_API_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET",
            "SECRET_KEY", "JWT_SECRET_KEY", "ALLOWED_ORIGINS", "DATABASE_URL",
            "DEV_BYPASS", "RATE_LIMIT_RPM"]
    result = {}
    for k in keys:
        v = os.environ.get(k)
        if v is None:
            result[k] = "NOT SET"
        elif k in ("OPENAI_API_KEY", "SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"):
            result[k] = f"SET ({len(v)} chars, starts with {v[:4]}...)"
        else:
            result[k] = f"SET ({v})"
    return result


@app.get("/health/deep")
def health_deep():
    import time
    checks: dict = {}

    # DB 체크
    t0 = time.time()
    try:
        db = database.SessionLocal()
        from sqlalchemy import text as _text
        db.execute(_text("SELECT 1"))
        db.close()
        checks["db"] = {"status": "ok", "response_ms": round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        checks["db"] = {"status": "down", "error": str(e)}

    # 디스크 사용량
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        checks["disk_usage_pct"] = round(used / total * 100, 1)
    except Exception:
        checks["disk_usage_pct"] = None

    overall = "ok" if all(
        (v.get("status") == "ok" if isinstance(v, dict) else True)
        for v in checks.values()
    ) else "degraded"

    from datetime import datetime, timezone
    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/version")
def version():
    return {"app": "Yeokping Ver2 API", "version": "3.5-A-route R1"}  # reload-ping


# --------------------------------------------------
# SPA 정적 파일 서빙 (프론트엔드 빌드 결과물)
# ⚠️ 반드시 모든 API 라우터 뒤에 위치해야 함
# --------------------------------------------------
try:
    from pathlib import Path as _SpaPath
    from fastapi.staticfiles import StaticFiles as _SpaStatic
    from fastapi.responses import FileResponse as _FileResponse

    _FRONTEND_DIST = _SpaPath(__file__).parent.parent / "frontend" / "dist"
    _INDEX_HTML = _FRONTEND_DIST / "index.html"

    if _FRONTEND_DIST.is_dir() and _INDEX_HTML.is_file():
        # Vite 빌드 에셋 (JS/CSS/이미지)
        _assets_dir = _FRONTEND_DIST / "assets"
        if _assets_dir.is_dir():
            app.mount("/assets", _SpaStatic(directory=str(_assets_dir)), name="spa_assets")

        # SPA catch-all: API/uploads/assets에 매칭되지 않는 모든 GET → index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # API 경로나 이미 마운트된 경로는 여기 도달하지 않음
            # 파일이 dist에 직접 존재하면 그 파일 서빙 (favicon.ico 등)
            _candidate = _FRONTEND_DIST / full_path
            if full_path and _candidate.is_file() and ".." not in full_path:
                return _FileResponse(str(_candidate))
            return _FileResponse(str(_INDEX_HTML))

        print(f"✅ SPA fallback enabled: {_FRONTEND_DIST}")
    else:
        print(f"[info] SPA fallback skipped: {_FRONTEND_DIST} not found (npm run build 필요)")
except Exception as _spa_err:
    print(f"[warn] SPA fallback setup failed: {_spa_err}")
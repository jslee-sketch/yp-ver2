# app/main.py
from __future__ import annotations

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
    EventLog,
    PolicyDeclaration, PolicyProposal,
    PingpongLog, PingpongCase,
    SpectatorPrediction, SpectatorMonthlyStats, SpectatorBadge,
    Report, UploadedFile, PayoutRequest,
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
    ("deals", "brand", "VARCHAR"),
    ("deals", "model_number", "VARCHAR"),
    ("deals", "options", "TEXT"),
    ("deals", "free_text", "TEXT"),
    ("deals", "category", "VARCHAR"),
    ("deals", "product_detail", "VARCHAR"),
    ("deals", "product_code", "VARCHAR"),
    ("deals", "condition", "VARCHAR"),
    ("deals", "market_price", "FLOAT"),
    ("deal_ai_logs", "note", "TEXT"),
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
        with engine.begin() as _conn:
            for _tbl, _col, _typ in _need_alter:
                try:
                    _conn.execute(_sa.text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    print(f"[DB_INIT] Added column {_tbl}.{_col}", flush=True)
                except Exception:
                    pass
    else:
        print("[DB_INIT] ALTER TABLE skipped — all columns exist", flush=True)
except Exception as _ae:
    print(f"[DB_INIT] ALTER TABLE error: {_ae}", flush=True)

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


DEV_DEBUG_ERRORS = False



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
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


# CORS — 환경변수 ALLOWED_ORIGINS 로 제어 (쉼표 구분, 기본값: 개발용 *)
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
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

# --------------------------------------------------
# Notification
# --------------------------------------------------
_include_router_safe("notifications", ("router",), label="notifications")

_include_router_safe("admin_refund_preview", ("router",), label="admin_refund_preview")

# --------------------------------------------------
# Spectator 관전자 시스템
# --------------------------------------------------
_include_router_safe("spectator", ("router",), label="spectator")

# --------------------------------------------------
# PINGPONG AI Agent
# --------------------------------------------------
_include_router_safe("pingpong", ("router",), label="pingpong")

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

# 정적 파일 (이미지 업로드)
try:
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    import os as _os
    _os.makedirs("uploads", exist_ok=True)
    app.mount("/uploads", _StaticFiles(directory="uploads"), name="uploads")
except Exception as _e:
    print(f"[warn] static files mount failed: {_e}")

# Rate Limiting 미들웨어
try:
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, default_rpm=int(__import__('os').environ.get('RATE_LIMIT_RPM', '600')))
except Exception as _e:
    print(f"[warn] RateLimitMiddleware not loaded: {_e}")


# Health/Version
@app.get("/api/health")
def root():
    return {"message": "Yeokping Ver2 API(NO-AUTH) is running", "ok": True}


@app.get("/health")
def health():
    return {"ok": True}


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
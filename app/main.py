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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# 초기화(DB/모델 로드)
from app.config import project_rules as R

from app import crud, models, database
from app.database import Base, engine


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

    # ✅ DB 테이블 생성은 import 시점이 아니라 startup 시점에서
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[warn] Base.metadata.create_all failed: {e.__class__.__name__}: {e}")

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


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# PINGPONG AI Agent
# --------------------------------------------------
_include_router_safe("pingpong", ("router",), label="pingpong")


# Health/Version
@app.get("/")
def root():
    return {"message": "Yeokping Ver2 API(NO-AUTH) is running 🚀"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    return {"app": "Yeokping Ver2 API", "version": "3.5-A-route R1"}  # reload-ping
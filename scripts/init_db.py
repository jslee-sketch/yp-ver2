#!/usr/bin/env python
"""
scripts/init_db.py
Force-create all database tables.

3-method cascade:
  1. Base.metadata.create_all() (standard)
  2. Individual CreateTable DDL per table (bypasses bulk issues)
  3. Raw compiled SQL via text() (last resort)

Run: python scripts/init_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

print("[init_db] Starting...", flush=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

from app.database import engine, Base

# ── Force import ALL model classes ──
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

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable

print(f"[init_db] engine.url = {engine.url}", flush=True)
print(f"[init_db] dialect    = {engine.dialect.name}", flush=True)

# ── Connection test ──
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[init_db] Connection OK", flush=True)
except Exception as e:
    print(f"[init_db] Connection FAILED: {e}", flush=True)
    sys.exit(1)

registered = sorted(Base.metadata.tables.keys())
print(f"[init_db] Registered models: {len(registered)}", flush=True)

inspector = inspect(engine)
existing = set(inspector.get_table_names())
print(f"[init_db] Existing tables:   {len(existing)}")

REQUIRED = {"users", "buyers", "sellers", "deals", "offers", "reservations",
            "reservation_settlements", "point_transactions", "policy_declarations"}


def check_done() -> bool:
    tables = set(inspect(engine).get_table_names())
    missing = REQUIRED - tables
    if not missing:
        print(f"[init_db] ALL {len(tables)} tables OK")
        return True
    print(f"[init_db] Still missing: {missing}")
    return False


# ════════════════════════════════════════════
# Method 1: standard create_all
# ════════════════════════════════════════════
print("\n=== Method 1: Base.metadata.create_all() ===")
try:
    Base.metadata.create_all(bind=engine)
    print("[M1] create_all returned without error")
    if check_done():
        sys.exit(0)
except Exception as e:
    print(f"[M1] FAILED: {e}")

# ════════════════════════════════════════════
# Method 2: individual CreateTable DDL
# ════════════════════════════════════════════
print("\n=== Method 2: Individual CreateTable DDL ===")
existing2 = set(inspect(engine).get_table_names())
for table in Base.metadata.sorted_tables:
    if table.name in existing2:
        continue
    try:
        with engine.begin() as conn:
            conn.execute(CreateTable(table, if_not_exists=True))
        print(f"  [M2] created: {table.name}")
    except Exception as e:
        print(f"  [M2] {table.name} FAILED: {e}")

if check_done():
    sys.exit(0)

# ════════════════════════════════════════════
# Method 3: raw compiled SQL via text()
# ════════════════════════════════════════════
print("\n=== Method 3: Raw SQL via text() ===")
existing3 = set(inspect(engine).get_table_names())
for table in Base.metadata.sorted_tables:
    if table.name in existing3:
        continue
    try:
        # Compile DDL for current dialect
        ddl = CreateTable(table, if_not_exists=True)
        compiled = ddl.compile(dialect=engine.dialect)
        sql_str = str(compiled).strip()
        with engine.begin() as conn:
            conn.execute(text(sql_str))
        print(f"  [M3] created: {table.name}")
    except Exception as e:
        print(f"  [M3] {table.name} FAILED: {e}")
        # Print the SQL that failed for debugging
        try:
            print(f"       SQL: {sql_str[:200]}")
        except Exception:
            pass

if check_done():
    sys.exit(0)

# ════════════════════════════════════════════
# Final verification
# ════════════════════════════════════════════
final = sorted(inspect(engine).get_table_names())
print(f"\n[init_db] FINAL: {len(final)} tables: {final}")
missing = REQUIRED - set(final)
if missing:
    print(f"❌ CRITICAL: Required tables still missing: {missing}")
    sys.exit(1)

print("✅ All required tables exist")

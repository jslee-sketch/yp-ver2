# scripts/seed_policy_declarations_from_md.py
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("YP_DB_PATH") or (PROJECT_ROOT / "app" / "ypver2.db")).resolve()

# SSOT/문서 소스: "지금 존재하고, 최신으로 보이는" 쪽만 우선
DOC_ROOTS = [
    PROJECT_ROOT / "app" / "policy" / "docs" / "public",
    PROJECT_ROOT / "app" / "policy" / "docs" / "admin",
    PROJECT_ROOT / "app" / "policy" / "docs" / "admin" / "ssot",
]

EXCLUDE_DIR_NAMES = {"__pycache__", ".git", ".venv", "node_modules"}
EXCLUDE_FILE_NAMES = set()  # 필요하면 여기에 추가


@dataclass
class PolicyRow:
    domain: str
    policy_key: str
    title: str
    description_md: str
    version: int = 1
    is_active: int = 1


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iter_md_files(roots: Iterable[Path]) -> List[Path]:
    files: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            if any(x in EXCLUDE_DIR_NAMES for x in p.parts):
                continue
            if p.name in EXCLUDE_FILE_NAMES:
                continue
            files.append(p)
    # 안정적 순서
    return sorted(set(files))


def first_h1_title(md: str, fallback: str) -> str:
    # 첫 "# " 타이틀만 가져옴
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("# "):
            t = s[2:].strip()
            return t if t else fallback
    return fallback


def rel_policy_key(file_path: Path) -> str:
    # key는 "경로 기반"이 제일 안정적임 (나중에 파일 이동만 조심하면 됨)
    # 예: app/policy/docs/public/refund.md -> public/refund
    #     app/policy/docs/admin/ssot/pricing_formula_ssot.md -> admin/ssot/pricing_formula_ssot
    try:
        rel = file_path.relative_to(PROJECT_ROOT / "app" / "policy" / "docs")
        rel_no_ext = rel.as_posix().removesuffix(".md")
        return rel_no_ext
    except Exception:
        return file_path.stem


def domain_from_key(policy_key: str) -> str:
    # 아주 단순/견고 매핑 (필요하면 너 SSOT 도메인 체계에 맞춰 확장)
    k = policy_key.lower()
    if "refund" in k:
        return "REFUND"
    if "shipping" in k:
        return "SHIPPING"
    if "settlement" in k:
        return "SETTLEMENT"
    if "fee" in k or "fees" in k:
        return "FEES"
    if "tier" in k or "tiers" in k:
        return "TIERS"
    if "pricing" in k or "price" in k:
        return "PRICING"
    if "guardrail" in k or "guardrails" in k:
        return "GUARDRAILS"
    if "timeline" in k or "time" in k:
        return "TIME"
    if "participants" in k:
        return "PARTICIPANTS"
    if "pingpong" in k:
        return "PINGPONG"
    if "actuator" in k:
        return "ACTUATOR"
    if "buyer" in k:
        return "BUYER"
    if "seller" in k:
        return "SELLER"
    if "recommender" in k:
        return "RECOMMENDER"
    if "policy_ops" in k or "policy" in k:
        return "POLICY"
    return "GENERAL"


def load_policy_rows() -> List[PolicyRow]:
    rows: List[PolicyRow] = []
    files = iter_md_files(DOC_ROOTS)
    if not files:
        raise SystemExit(f"No md files found under roots: {DOC_ROOTS}")

    for fp in files:
        md = fp.read_text(encoding="utf-8", errors="replace").strip()
        if not md:
            continue
        key = rel_policy_key(fp)
        title = first_h1_title(md, fallback=fp.stem)
        domain = domain_from_key(key)
        rows.append(PolicyRow(domain=domain, policy_key=key, title=title, description_md=md))
    return rows


def ensure_table(cur: sqlite3.Cursor) -> None:
    # 이미 존재하지만, 혹시 로컬 테스트에서 없으면 만들어줌(방어)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_declarations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            policy_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description_md TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_declarations_key_ver ON policy_declarations(policy_key, version)")


def upsert_rows(con: sqlite3.Connection, rows: List[PolicyRow], *, mode: str) -> Tuple[int, int]:
    """
    mode:
      - "append": 기존 있으면 스킵, 없으면 삽입
      - "replace": 기존 모두 비활성화 후 새로 삽입(버전 1로)
    """
    cur = con.cursor()
    ensure_table(cur)

    inserted = 0
    skipped = 0

    if mode == "replace":
        cur.execute("UPDATE policy_declarations SET is_active=0, updated_at=?", (now_utc_iso(),))

    for r in rows:
        # 같은 key의 active 존재하면 스킵(append 기준)
        cur.execute(
            "SELECT id FROM policy_declarations WHERE policy_key=? AND version=?",
            (r.policy_key, r.version),
        )
        found = cur.fetchone()
        if found and mode == "append":
            skipped += 1
            continue

        cur.execute(
            """
            INSERT OR REPLACE INTO policy_declarations
            (domain, policy_key, title, description_md, version, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r.domain,
                r.policy_key,
                r.title,
                r.description_md,
                r.version,
                r.is_active,
                now_utc_iso(),
                now_utc_iso(),
            ),
        )
        inserted += 1

    con.commit()
    return inserted, skipped


def main() -> None:
    mode = (os.environ.get("YP_POLICY_SEED_MODE") or "append").strip().lower()
    if mode not in ("append", "replace"):
        raise SystemExit("YP_POLICY_SEED_MODE must be append|replace")

    print(f"DB={DB_PATH}")
    print(f"MODE={mode}")
    rows = load_policy_rows()
    print(f"MD rows loaded: {len(rows)}")

    con = sqlite3.connect(str(DB_PATH))
    try:
        ins, sk = upsert_rows(con, rows, mode=mode)
        print(f"Inserted={ins}, Skipped={sk}")
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM policy_declarations WHERE is_active=1")
        active = cur.fetchone()[0]
        print(f"Active policies now: {active}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
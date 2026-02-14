# app/database.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

def _default_sqlite_url() -> str:
    """
    ✅ 기본 DB는 repo/app/ypver2.db 로 고정 (SSOT)
    """
    project_root = Path(__file__).resolve().parents[1]  # repo root (..../yp-ver2)
    db_path = (project_root / "app" / "ypver2.db").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"

# ✅ 환경변수 DATABASE_URL이 있으면 그걸 최우선으로 사용
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip() or _default_sqlite_url()

print(f"✅ Using DATABASE_URL: {DATABASE_URL}")
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = DATABASE_URL.replace("sqlite:///", "")
    try:
        print(f"➡️  SQLite file absolute path: {Path(sqlite_path).resolve()}")
    except Exception:
        pass

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
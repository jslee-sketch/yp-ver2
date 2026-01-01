# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import pathlib

# ✅ 이 프로젝트에서 사용할 DB 파일 (Windows에서도 안전하게)
DB_FILE = pathlib.Path(r"C:\Users\user\Desktop\yp-ver2\app\ypver2.db").resolve()

# ✅ 환경변수 무시하고 이 경로만 쓴다
DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"

connect_args = {"check_same_thread": False}

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


print("✅ Using DATABASE_URL:", DATABASE_URL)
print("➡️  SQLite file absolute path:", DB_FILE)
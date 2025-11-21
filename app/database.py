# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# 환경변수에서 DATABASE_URL 읽기, 없으면 SQLite 기본값 사용
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app/ypver2.db")

# SQLite 전용 옵션 (다른 DB에서는 불필요)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
print("✅ Using database:", DATABASE_URL)
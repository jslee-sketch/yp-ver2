# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ✅ 이 프로젝트에서 사용할 "단 하나의" DB 파일 절대경로
DB_FILE = r"C:\Users\user\Desktop\yp-ver2\app\ypver2.db"

# ✅ 환경변수 무시하고 이 경로만 쓴다
DATABASE_URL = f"sqlite:///{DB_FILE}"

# SQLite 옵션
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


# 디버그용 출력
print("✅ Using DATABASE_URL:", DATABASE_URL)
print("➡️  SQLite file absolute path:", os.path.abspath(DB_FILE))
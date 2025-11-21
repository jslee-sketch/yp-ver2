# create_admin.py
from app.database import SessionLocal
from app.models import User
from app.security import get_password_hash

db = SessionLocal()

# 이미 존재하면 중복 방지
existing = db.query(User).filter(User.email == "admin@yeokping.com").first()
if existing:
    print("⚠️  admin@yeokping.com 이미 존재합니다.")
else:
    admin = User(
        email="admin@yeokping.com",
        hashed_password=get_password_hash("admin1234"),  # bcrypt 해시 생성
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.commit()
    print("✅ 관리자 계정 생성 완료")

db.close()
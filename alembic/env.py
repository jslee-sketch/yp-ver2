from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# --- DB 및 모델 import 추가 ---
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.database import Base  # ✅ 우리의 Base
from app import models         # ✅ models.py 불러오기 (테이블 정의된 곳)
target_metadata = Base.metadata

# Alembic Config 객체
config = context.config

# logging 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 시 사용할 metadata 지정
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
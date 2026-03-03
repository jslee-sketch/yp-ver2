# app/services/yaml_version.py
"""YAML 정책 파일 버전 관리 (백업/복원)."""
from __future__ import annotations

import shutil
from pathlib import Path
from datetime import datetime

YAML_DIR = Path("app/policy/params")
BACKUP_DIR = Path("app/policy/params/backups")


def backup_yaml(filename: str) -> str:
    BACKUP_DIR.mkdir(exist_ok=True)
    src = YAML_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"{src} not found")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{filename}.{ts}.bak"
    shutil.copy2(src, dst)
    return str(dst)


def restore_yaml(filename: str, backup_path: str) -> None:
    shutil.copy2(backup_path, YAML_DIR / filename)


def read_yaml_content(filename: str) -> str:
    return (YAML_DIR / filename).read_text(encoding="utf-8")

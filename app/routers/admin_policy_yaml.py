# app/routers/admin_policy_yaml.py
"""Admin YAML policy CRUD — read/write defaults.yaml"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/admin/policy", tags=["admin-policy-yaml"])

_YAML_PATH = Path(__file__).resolve().parent.parent / "policy" / "params" / "defaults.yaml"


@router.get("/yaml")
def get_policy_yaml():
    if not _YAML_PATH.is_file():
        raise HTTPException(status_code=404, detail="defaults.yaml not found")
    content = _YAML_PATH.read_text(encoding="utf-8")
    return {"content": content, "path": str(_YAML_PATH)}


@router.put("/yaml")
def put_policy_yaml(
    payload: dict,
    db: Session = Depends(get_db),
):
    content = payload.get("content", "")
    if not content:
        raise HTTPException(status_code=422, detail="content required")

    # syntax validation
    try:
        import yaml
        yaml.safe_load(content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"YAML syntax error: {e}")

    # backup
    if _YAML_PATH.is_file():
        bak = _YAML_PATH.with_suffix(f".bak.{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(_YAML_PATH, bak)

    _YAML_PATH.write_text(content, encoding="utf-8")

    # EventLog
    try:
        log = models.EventLog(
            event_type="policy_yaml_update",
            actor_type="admin",
            actor_id=0,
            detail=f"defaults.yaml updated ({len(content)} chars)",
        )
        db.add(log)
        db.commit()
    except Exception:
        pass

    # reload runtime
    try:
        from app.policy.runtime import reload_params
        reload_params()
    except Exception:
        pass

    return {"ok": True, "size": len(content)}


@router.get("/yaml/history")
def get_policy_yaml_history():
    folder = _YAML_PATH.parent
    baks = sorted(folder.glob("defaults.bak.*"), reverse=True)
    result = []
    for b in baks[:20]:
        stat = b.stat()
        result.append({
            "filename": b.name,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return result

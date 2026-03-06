# app/routers/admin_policy_docs.py
"""Admin policy docs CRUD — markdown files in app/policy/docs/"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/admin/policy", tags=["admin-policy-docs"])

_DOCS_DIR = Path(__file__).resolve().parent.parent / "policy" / "docs"


def _safe_path(rel: str) -> Path:
    """Resolve and validate path stays within docs dir."""
    p = (_DOCS_DIR / rel).resolve()
    if not str(p).startswith(str(_DOCS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return p


@router.get("/docs")
def list_policy_docs():
    if not _DOCS_DIR.is_dir():
        return []
    result = []
    for f in sorted(_DOCS_DIR.rglob("*.md")):
        rel = f.relative_to(_DOCS_DIR)
        stat = f.stat()
        result.append({
            "path": str(rel).replace("\\", "/"),
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return result


@router.get("/docs/{path:path}")
def get_policy_doc(path: str):
    fp = _safe_path(path)
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return {"path": path, "content": fp.read_text(encoding="utf-8")}


@router.put("/docs/{path:path}")
def update_policy_doc(path: str, payload: dict):
    content = payload.get("content", "")
    fp = _safe_path(path)
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    fp.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "size": len(content)}


@router.post("/docs")
def create_policy_doc(payload: dict):
    path = payload.get("path", "")
    content = payload.get("content", "")
    if not path:
        raise HTTPException(status_code=422, detail="path required")
    fp = _safe_path(path)
    if fp.exists():
        raise HTTPException(status_code=409, detail="Document already exists")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "size": len(content)}

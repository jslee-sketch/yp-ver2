# app/routers/ui_portal.py
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/ui", tags=["🖥️ Portal (NO-AUTH)"])

# 템플릿 폴더는 app/templates 로 가정
try:
    templates = Jinja2Templates(directory="app/templates")
except Exception as e:
    templates = None

@router.get("/ping", response_class=PlainTextResponse)
def ping():
    return "ok\n--\nTrue"

@router.get("/portal")
def portal(request: Request):
    if templates is None:
        # 템플릿 환경이 없으면 간단한 안내 반환
        return PlainTextResponse(
            "Jinja2Templates not available. Please ensure 'jinja2' is installed in this venv.",
            status_code=500,
        )
    # 필요시 SSR 변수 주입
    return templates.TemplateResponse(
        "ui_portal.html",
        {
            "request": request,
            # UI에 기본값 주고 싶다면 여기에 추가 (예: 기본 buyer_id/seller_id)
            "defaults": {
                "buyer_id": 10,
                "seller_id": 1,
            },
        },
    )
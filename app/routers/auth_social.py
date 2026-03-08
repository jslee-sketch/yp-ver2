"""
소셜 로그인 (Kakao / Naver / Google) OAuth2 콜백 처리
- GET  /auth/social/{provider}/authorize  → 인가 URL 반환
- POST /auth/social/{provider}/callback   → 토큰 교환 → JWT 발급
"""

import secrets
import requests as http_requests
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import database, models
from ..security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_password_hash
from ..config.oauth_config import PROVIDER_CONFIG

router = APIRouter(prefix="/auth/social", tags=["auth_social"])

SUPPORTED_PROVIDERS = ("kakao", "naver", "google")


# ── 스키마 ──────────────────────────────────────────────

class AuthorizeResponse(BaseModel):
    url: str

class CallbackRequest(BaseModel):
    code: str
    state: str | None = None

class CallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool


# ── 인가 URL 생성 ────────────────────────────────────────

@router.get("/{provider}/authorize", response_model=AuthorizeResponse)
def social_authorize(provider: str):
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, f"Unsupported provider: {provider}")
    cfg = PROVIDER_CONFIG[provider]
    if not cfg["client_id"]:
        raise HTTPException(501, f"{provider} OAuth not configured (missing client_id)")

    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "state": state,
    }
    if provider == "google":
        params["scope"] = cfg.get("scope", "openid email profile")
    if provider == "naver":
        params["scope"] = ""  # naver는 scope 없이 기본 정보 제공

    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    url = f"{cfg['authorize_url']}?{qs}"
    return AuthorizeResponse(url=url)


# ── 콜백 (코드 → 토큰 → 프로필 → JWT) ────────────────────

@router.post("/{provider}/callback", response_model=CallbackResponse)
def social_callback(
    provider: str,
    body: CallbackRequest,
    db: Session = Depends(database.get_db),
):
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, f"Unsupported provider: {provider}")
    cfg = PROVIDER_CONFIG[provider]
    if not cfg["client_id"]:
        raise HTTPException(501, f"{provider} OAuth not configured")

    # 1) 토큰 교환
    token_data = _exchange_code(provider, cfg, body.code)
    access_token_provider = token_data.get("access_token")
    if not access_token_provider:
        raise HTTPException(400, "Failed to get access token from provider")

    # 2) 프로필 가져오기
    profile = _fetch_profile(provider, cfg, access_token_provider)
    social_id = str(profile["id"])
    email = profile.get("email")
    name = profile.get("name", "")

    # 3) 기존 social identity 검색
    buyer = db.query(models.Buyer).filter(
        models.Buyer.social_provider == provider,
        models.Buyer.social_id == social_id,
    ).first()

    is_new = False

    if not buyer and email:
        # 이메일 매칭으로 기존 계정 연결
        buyer = db.query(models.Buyer).filter(models.Buyer.email == email).first()
        if buyer:
            buyer.social_provider = provider
            buyer.social_id = social_id
            db.commit()

    if not buyer:
        # 신규 생성
        if not email:
            email = f"{provider}_{social_id}@social.yeokping.com"

        sentinel_hash = get_password_hash(secrets.token_urlsafe(32))
        display_name = name or email.split("@")[0]
        # 닉네임 자동 생성 (소셜 로그인)
        auto_nick = f"{provider}_{social_id[:8]}"
        buyer = models.Buyer(
            email=email,
            password_hash=sentinel_hash,
            name=display_name,
            nickname=auto_nick,
            social_provider=provider,
            social_id=social_id,
        )
        db.add(buyer)
        db.commit()
        db.refresh(buyer)
        is_new = True

    # 4) JWT 발급
    jwt_token = create_access_token(
        data={"sub": str(buyer.id), "role": "buyer"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return CallbackResponse(
        access_token=jwt_token,
        is_new_user=is_new,
    )


# ── 내부 헬퍼 ──────────────────────────────────────────

def _exchange_code(provider: str, cfg: dict, code: str) -> dict:
    """인가 코드 → 액세스 토큰 교환"""
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "code": code,
    }
    if cfg.get("client_secret"):
        data["client_secret"] = cfg["client_secret"]

    resp = http_requests.post(cfg["token_url"], data=data, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(400, f"Token exchange failed: {resp.text[:200]}")
    return resp.json()


def _fetch_profile(provider: str, cfg: dict, access_token: str) -> dict:
    """액세스 토큰으로 사용자 프로필 가져오기"""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = http_requests.get(cfg["profile_url"], headers=headers, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(400, f"Profile fetch failed: {resp.text[:200]}")

    raw = resp.json()

    if provider == "kakao":
        account = raw.get("kakao_account", {})
        return {
            "id": raw.get("id"),
            "email": account.get("email"),
            "name": account.get("profile", {}).get("nickname", ""),
        }
    elif provider == "naver":
        resp_data = raw.get("response", {})
        return {
            "id": resp_data.get("id"),
            "email": resp_data.get("email"),
            "name": resp_data.get("name") or resp_data.get("nickname", ""),
        }
    elif provider == "google":
        return {
            "id": raw.get("id"),
            "email": raw.get("email"),
            "name": raw.get("name", ""),
        }
    else:
        raise HTTPException(400, f"Unknown provider: {provider}")

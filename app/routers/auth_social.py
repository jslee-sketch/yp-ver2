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
    access_token: str | None = None    # 기존 유저만 발급
    token_type: str = "bearer"
    is_new_user: bool
    # 신규 유저용 소셜 프로필
    social_provider: str | None = None
    social_id: str | None = None
    social_email: str | None = None
    social_name: str | None = None


class SocialRegisterRequest(BaseModel):
    social_provider: str
    social_id: str
    social_email: str | None = None
    social_name: str | None = None
    role: str  # buyer / seller / actuator
    nickname: str
    # buyer용
    phone: str | None = None
    address: str | None = None
    zip_code: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    payment_method: str | None = None
    # seller용
    business_name: str | None = None
    business_number: str | None = None
    company_phone: str | None = None
    established_date: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    account_holder: str | None = None
    actuator_id: int | None = None
    business_license_image: str | None = None
    ecommerce_permit_image: str | None = None
    bankbook_image: str | None = None
    external_ratings: str | None = None
    # actuator용
    is_business: bool = False
    ecommerce_permit_number: str | None = None
    business_address: str | None = None
    business_zip_code: str | None = None


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

    # 3) 기존 social identity 검색 (Buyer → Seller → Actuator)
    user = db.query(models.Buyer).filter(
        models.Buyer.social_provider == provider,
        models.Buyer.social_id == social_id,
    ).first()
    role_found = "buyer" if user else None

    if not user:
        user = db.query(models.Seller).filter(
            models.Seller.social_provider == provider,
            models.Seller.social_id == social_id,
        ).first()
        if user:
            role_found = "seller"

    if not user:
        user = db.query(models.Actuator).filter(
            models.Actuator.social_provider == provider,
            models.Actuator.social_id == social_id,
        ).first()
        if user:
            role_found = "actuator"

    # 이메일 매칭 (Buyer → Seller → Actuator)
    if not user and email:
        user = db.query(models.Buyer).filter(models.Buyer.email == email).first()
        if user:
            role_found = "buyer"
            user.social_provider = provider
            user.social_id = social_id
            db.commit()

    if not user and email:
        user = db.query(models.Seller).filter(models.Seller.email == email).first()
        if user:
            role_found = "seller"
            user.social_provider = provider
            user.social_id = social_id
            db.commit()

    if not user and email:
        user = db.query(models.Actuator).filter(models.Actuator.email == email).first()
        if user:
            role_found = "actuator"
            user.social_provider = provider
            user.social_id = social_id
            db.commit()

    if not user:
        # 신규: DB 생성 하지 않음, 소셜 프로필만 반환
        return CallbackResponse(
            access_token=None,
            is_new_user=True,
            social_provider=provider,
            social_id=social_id,
            social_email=email,
            social_name=name,
        )

    # 4) 기존 유저 → JWT 발급
    jwt_token = create_access_token(
        data={"sub": str(user.id), "role": role_found},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return CallbackResponse(
        access_token=jwt_token,
        is_new_user=False,
    )


# ── 소셜 회원가입 ───────────────────────────────────────

@router.post("/register", response_model=CallbackResponse)
def social_register(body: SocialRegisterRequest, db: Session = Depends(database.get_db)):
    """소셜 로그인 신규 유저: 역할 선택 후 실제 DB 생성 + JWT 발급"""
    sentinel_hash = get_password_hash(secrets.token_urlsafe(32))
    email = body.social_email or f"{body.social_provider}_{body.social_id}@social.yeokping.com"
    display_name = body.social_name or body.nickname

    if body.role == "buyer":
        user = models.Buyer(
            email=email,
            password_hash=sentinel_hash,
            name=display_name,
            nickname=body.nickname,
            social_provider=body.social_provider,
            social_id=body.social_id,
            phone=body.phone or None,
            address=body.address or None,
            zip_code=body.zip_code or None,
            gender=body.gender or None,
            payment_method=body.payment_method or None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        role_found = "buyer"

    elif body.role == "seller":
        user = models.Seller(
            email=email,
            password_hash=sentinel_hash,
            business_name=body.business_name or display_name,
            nickname=body.nickname,
            business_number=body.business_number or f"SOCIAL-{body.social_id[:10]}",
            social_provider=body.social_provider,
            social_id=body.social_id,
            phone=body.phone or None,
            company_phone=body.company_phone or None,
            address=body.address or None,
            zip_code=body.zip_code or None,
            bank_name=body.bank_name or None,
            account_number=body.account_number or None,
            account_holder=body.account_holder or None,
            actuator_id=body.actuator_id,
            business_license_image=body.business_license_image or None,
            ecommerce_permit_image=body.ecommerce_permit_image or None,
            bankbook_image=body.bankbook_image or None,
            external_ratings=body.external_ratings or None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        role_found = "seller"

    elif body.role == "actuator":
        user = models.Actuator(
            name=display_name,
            email=email,
            phone=body.phone or None,
            password_hash=sentinel_hash,
            nickname=body.nickname,
            social_provider=body.social_provider,
            social_id=body.social_id,
            bank_name=body.bank_name or None,
            account_number=body.account_number or None,
            account_holder=body.account_holder or None,
            bankbook_image=body.bankbook_image or None,
            is_business=body.is_business,
            business_name=body.business_name or None,
            business_number=body.business_number or None,
            ecommerce_permit_number=body.ecommerce_permit_number or None,
            business_address=body.business_address or None,
            business_zip_code=body.business_zip_code or None,
            company_phone=body.company_phone or None,
            business_license_image=body.business_license_image or None,
            ecommerce_permit_image=body.ecommerce_permit_image or None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        role_found = "actuator"
    else:
        raise HTTPException(400, f"Unsupported role: {body.role}")

    jwt_token = create_access_token(
        data={"sub": str(user.id), "role": role_found},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return CallbackResponse(
        access_token=jwt_token,
        is_new_user=True,
        social_provider=body.social_provider,
        social_id=body.social_id,
        social_email=email,
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

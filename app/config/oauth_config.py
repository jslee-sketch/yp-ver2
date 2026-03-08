"""
소셜 로그인 (Kakao/Naver/Google) OAuth 설정
환경변수에서 클라이언트 ID/Secret 로드
"""
import os

# Redirect base (prod vs dev)
SOCIAL_REDIRECT_BASE = os.getenv("SOCIAL_REDIRECT_BASE", "http://localhost:5173")

# Kakao (KAKAO_CLIENT_ID or KAKAO_REST_API_KEY)
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "") or os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", f"{SOCIAL_REDIRECT_BASE}/auth/callback/kakao")

# Naver (NAVER_CLIENT_ID or NAVER_LOGIN_CLIENT_ID)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "") or os.getenv("NAVER_LOGIN_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "") or os.getenv("NAVER_LOGIN_CLIENT_SECRET", "")
NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI", f"{SOCIAL_REDIRECT_BASE}/auth/callback/naver")

# Google
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{SOCIAL_REDIRECT_BASE}/auth/callback/google")

PROVIDER_CONFIG = {
    "kakao": {
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url": "https://kauth.kakao.com/oauth/token",
        "profile_url": "https://kapi.kakao.com/v2/user/me",
        "client_id": KAKAO_CLIENT_ID,
        "client_secret": "",
        "redirect_uri": KAKAO_REDIRECT_URI,
    },
    "naver": {
        "authorize_url": "https://nid.naver.com/oauth2.0/authorize",
        "token_url": "https://nid.naver.com/oauth2.0/token",
        "profile_url": "https://openapi.naver.com/v1/nid/me",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "redirect_uri": NAVER_REDIRECT_URI,
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "profile_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": "openid email profile",
    },
}

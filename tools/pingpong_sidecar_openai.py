# tools/pingpong_sidecar_openai.py
from __future__ import annotations

import os
import re
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
import time 
now_ts = time.time

import requests
from openai import OpenAI
from pathlib import Path as _P
from dotenv import load_dotenv; load_dotenv(_P(__file__).resolve().parent.parent / ".env", override=True)

# ============================================================
# Config
# ============================================================
OPENAI_MODEL = (os.environ.get("YP_OPENAI_MODEL") or "gpt-4o-mini").strip()
INTENT_MODEL = (os.environ.get("YP_INTENT_MODEL") or OPENAI_MODEL).strip()
YP_SERVER_URL = (os.environ.get("YP_SERVER_URL") or "http://127.0.0.1:9000").rstrip("/")
HTTP_TIMEOUT = float(os.environ.get("YP_HTTP_TIMEOUT") or "8.0")
EXTERNAL_TIMEOUT = float(os.environ.get("YP_EXTERNAL_TIMEOUT") or "2.5")
ASK_TIMEOUT = float(os.environ.get("YP_ASK_TIMEOUT") or "4.0")  # ✅ ask(뇌) 전용 타임아웃

DEBUG = (os.environ.get("PINGPONG_SIDECAR_DEBUG") or "false").lower() == "true"
USER_NAME = (os.environ.get("YP_USER_NAME") or "").strip() or None

NAVER_CLIENT_ID = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
NAVER_CLIENT_SECRET = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()

KEEP_TURNS = 8
DEFAULTS_YAML_PATH = ("app", "policy", "params", "defaults.yaml")
KST = ZoneInfo("Asia/Seoul")

HTTP = requests.Session()
HTTP.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PingpongSidecar/1.2",
        "Accept": "*/*",
    }
)

def _dbg(*args: Any) -> None:
    if DEBUG:
        ts = time.strftime("%H:%M:%S")
        print("[DBG]", ts, *args)

# ============================================================
# Exported KB loader (for autotest_v2 imports)
# ============================================================
@dataclass
class KBItem:
    path: str
    text: str
    text_l: str
    weight: float = 1.0

KB: List[KBItem] = []
_KB_LOADED = False

def repo_root() -> Path:
    cur = Path(__file__).resolve()
    for p in [cur.parent, cur.parent.parent, Path.cwd()]:
        if (p / "app").exists():
            return p
    return Path.cwd()

def load_kb() -> None:
    global KB, _KB_LOADED
    if _KB_LOADED:
        return
    root = repo_root()
    allow_suffix = {".md", ".txt", ".yaml", ".yml", ".json"}
    kb: List[KBItem] = []

    def _w(path_l: str) -> float:
        w = 1.0
        if "/policy/" in path_l:
            w *= 1.2
        if path_l.endswith("defaults.yaml") or path_l.endswith("defaults.yml"):
            w *= 1.6
        return w

    scan_dirs = [root / "docs", root / "app" / "policy", root / "app" / "docs"]
    for d in scan_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in allow_suffix:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not text:
                continue
            rel = str(f.relative_to(root)).replace("\\", "/")
            kb.append(KBItem(path=rel, text=text, text_l=text.lower(), weight=_w(rel.lower())))

    KB = kb
    _KB_LOADED = True
    admin_count = sum(1 for it in KB if "/admin/" in it.path.lower())
    public_count = sum(1 for it in KB if "/public/" in it.path.lower())
    total_chars = sum(len(it.text) for it in KB)
    print(f"[OK] KB loaded: {len(KB)} files ({public_count} public, {admin_count} admin, {total_chars:,} chars)", flush=True)

def _kb_allowed_for_role(path_l: str, role: str) -> bool:
    """역할에 따라 KB 파일 접근 제한."""
    role = (role or "").upper()
    # admin/ 문서는 ADMIN만
    if "/docs/admin/" in path_l or "/admin/" in path_l:
        if role != "ADMIN":
            return False
    # guide_buyer.md는 BUYER/ADMIN만 (SELLER는 자기 가이드)
    if "guide_buyer" in path_l:
        return role in ("BUYER", "ADMIN", "")
    # guide_seller.md는 SELLER/ADMIN/ACTUATOR
    if "guide_seller" in path_l:
        return role in ("SELLER", "ADMIN", "ACTUATOR", "")
    # guide_actuator.md는 ACTUATOR/ADMIN만
    if "guide_actuator" in path_l:
        return role in ("ACTUATOR", "ADMIN", "")
    # buyer.md는 BUYER/ADMIN만
    if path_l.endswith("/buyer.md"):
        return role in ("BUYER", "ADMIN", "")
    # screens/ 디자인 문서는 BUYER/SELLER/ADMIN (ACTUATOR 제외 — 화면 설계 불필요)
    if "/screens/" in path_l:
        return role in ("BUYER", "SELLER", "ADMIN", "")
    # spectators_public.md는 BUYER/ADMIN만 (관전 모드는 구매자 전용)
    if "spectators_public" in path_l:
        return role in ("BUYER", "ADMIN", "")
    # buyer.md는 BUYER/ADMIN만
    if path_l.endswith("/buyer.md"):
        return role in ("BUYER", "ADMIN", "")
    # openapi.json은 ADMIN만 (기술 문서)
    if "openapi.json" in path_l:
        return role in ("ADMIN", "")
    # tiers.md는 BUYER/SELLER/ADMIN (등급은 구매자/판매자 전용)
    if "tiers.md" in path_l:
        return role in ("BUYER", "SELLER", "ADMIN", "")
    # 그 외(defaults.yaml, 공통 정책 등)는 모두 허용
    return True


_ADMIN_QUERY_KEYWORDS = {"마이너리티", "이상 감지", "신고 관리", "정책 파라미터", "정책 문서",
                         "정책제안", "정책 제안", "환불 시뮬레이터", "브로드캐스트",
                         "관리자 대시보드", "관리자 배송", "관리자 딜", "관리자 오퍼"}
_BUYER_QUERY_KEYWORDS = {"딜 생성", "가격 챌린지", "관전 모드", "관전자", "포인트 적립",
                         "구매자 등급", "사진으로 찾기", "사진 검색", "음성 검색",
                         "맞춰보기", "슬라이더"}

def retrieve_kb_snippets(query: str, role: str = "") -> str:
    ql = (query or "").lower().strip()
    if not ql:
        return ""
    toks = re.findall(r"[가-힣]{2,}|[a-z]{2,}|[0-9]{1,}", ql)
    if not toks:
        return ""
    role_u = (role or "").upper()
    # 역할별 쿼리 필터링 — 관리자/구매자 전용 질문을 다른 역할에서 차단
    if role_u and role_u != "ADMIN":
        if any(kw in ql for kw in _ADMIN_QUERY_KEYWORDS):
            return ""
    if role_u and role_u not in ("BUYER", "ADMIN"):
        if any(kw in ql for kw in _BUYER_QUERY_KEYWORDS):
            return ""
    scored: List[Tuple[float, KBItem]] = []
    for it in KB:
        path_l = it.path.lower()
        if not _kb_allowed_for_role(path_l, role_u):
            continue
        s = 0.0
        for t in toks[:20]:
            if t in path_l:
                s += 8
            if t in it.text_l:
                s += min(20, it.text_l.count(t) * 2)
        s *= it.weight
        # 역할 가이드 매칭 보너스 (본인 가이드 우선)
        if role_u == "BUYER" and "guide_buyer" in path_l:
            s *= 1.5
        elif role_u == "SELLER" and "guide_seller" in path_l:
            s *= 1.5
        elif role_u == "ADMIN" and "guide_admin" in path_l:
            s *= 1.5
        elif role_u == "ACTUATOR" and "guide_actuator" in path_l:
            s *= 1.5
        if s > 0:
            scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[str] = []
    total = 0
    for s, it in scored[:6]:
        chunk = it.text[:6000]
        block = f"### [자료: {it.path}] (score={int(s)}) ###\n{chunk}"
        if total + len(block) > 16000:
            break
        out.append(block)
        total += len(block)
    _dbg(f"[KB] role={role_u} query={ql[:40]} → {len(out)} docs, {total} chars")
    return "\n\n".join(out)


# ============================================================
# FAQ Direct Mapping — KB retrieve 보완 (키워드 매칭 한계 극복)
# ============================================================
_FAQ_DIRECT_MAP: Dict[str, Any] = {
    # ---- 구매자 ----
    "사진으로 찾기": "딜 생성 Step 1에서 📷 버튼을 클릭하면 제품 사진을 최대 3장 업로드할 수 있습니다. AI가 자동으로 제품을 인식합니다. 경로: /deal/create",
    "사진 찍어서": "딜 생성 Step 1에서 📷 버튼을 클릭하면 제품 사진을 최대 3장 업로드할 수 있습니다. AI가 자동으로 제품을 인식합니다. 경로: /deal/create",
    "사진 검색": "딜 생성 Step 1에서 📷 버튼을 클릭하면 제품 사진을 최대 3장 업로드할 수 있습니다. AI가 자동으로 제품을 인식합니다. 경로: /deal/create",
    "사진으로 딜": "딜 생성 Step 1에서 📷 버튼을 클릭하면 제품 사진을 최대 3장 업로드할 수 있습니다. AI가 자동으로 제품을 인식합니다. 경로: /deal/create",
    "카메라": "딜 생성 Step 1에서 📷 버튼을 클릭하면 제품 사진을 최대 3장 업로드할 수 있습니다. 경로: /deal/create",
    "음성으로 딜": "딜 생성 Step 1에서 🎤 버튼을 클릭하고 마이크에 '갤럭시 S25 110만원'처럼 말하면 AI가 자동으로 인식합니다. 최대 30초 녹음. 경로: /deal/create",
    "음성 검색": "딜 생성 Step 1에서 🎤 버튼을 클릭하고 마이크에 '갤럭시 S25 110만원'처럼 말하면 AI가 자동으로 인식합니다. 경로: /deal/create",
    "음성으로 제품": "딜 생성 Step 1에서 🎤 버튼을 클릭하면 음성으로 제품을 검색할 수 있습니다. 경로: /deal/create",
    "마이크": "딜 생성 Step 1에서 🎤 버튼을 클릭하면 음성으로 제품을 검색할 수 있습니다. 경로: /deal/create",
    "딜 생성 단계": "딜 생성은 5단계입니다. Step 1: 제품 찾기 (텍스트/사진/음성), Step 2: 제품 정보 확인, Step 3: 가격 설정 (가격 챌린지), Step 4: 기타 요청사항, Step 5: 최종 확인 및 딜 만들기. 경로: /deal/create",
    "단계가 몇": "딜 생성은 5단계입니다. Step 1: 제품 찾기, Step 2: 제품 정보 확인, Step 3: 가격 설정, Step 4: 기타 요청사항, Step 5: 최종 확인. 경로: /deal/create",
    "몇 단계": "딜 생성은 5단계입니다. Step 1: 제품 찾기, Step 2: 제품 정보 확인, Step 3: 가격 설정, Step 4: 기타 요청사항, Step 5: 최종 확인. 경로: /deal/create",
    "카카오 로그인": "카카오(💬), 네이버(N), 구글(G) 계정으로 간편 로그인 가능합니다. 소셜 로그인 시 역할(구매자/판매자/액츄에이터)을 선택하고 닉네임을 설정합니다. 기존 이메일 계정과 자동 연동됩니다. 경로: /login",
    "카카오": "카카오(💬) 계정으로 간편 로그인 가능합니다. 소셜 로그인 시 역할을 선택하고 닉네임을 설정합니다. 경로: /login",
    "네이버 로그인": "네이버(N) 계정으로 간편 로그인 가능합니다. 경로: /login",
    "구글 로그인": "구글(G) 계정으로 간편 로그인 가능합니다. 경로: /login",
    "소셜 로그인": "카카오(💬), 네이버(N), 구글(G) 계정으로 간편 로그인 가능합니다. 경로: /login",
    "신뢰도": "시장가 신뢰도 등급: 🟢 높음 (2개+ 소스 15% 이내 일치), 🟡 보통 (30% 이내 또는 1개 소스), 🔴 낮음 (정확한 가격 확인 불가), ⚫ 온라인 판매 불가. 3중 소스: 네이버쇼핑 + 쿠팡 + GPT-4o 교차 검증.",
    "초록 노랑 빨강": "시장가 신뢰도: 🟢 초록 = 높음 (2개+ 소스 일치), 🟡 노랑 = 보통 (1개 소스), 🔴 빨강 = 낮음 (확인 불가).",
    "가격 챌린지": "딜 생성 Step 3에서 예상 가격을 입력하고 [맞춰보기! 🎯] 버튼을 누르면 AI가 네이버+쿠팡+GPT 3중 소스로 시장가를 조사합니다. 슬라이더로 할인율(0~50%)을 조정하면 목표가와 절감액이 실시간 계산됩니다.",
    "맞춰보기": "딜 생성 Step 3에서 [맞춰보기! 🎯] 버튼을 누르면 AI가 3중 소스(네이버+쿠팡+GPT)로 시장가를 조사하고 신뢰도 등급(🟢🟡🔴⚫)을 표시합니다.",
    "목표가 슬라이더": "딜 생성 Step 3에서 슬라이더로 할인율(0~50%)을 조정하면 목표가와 절감액이 실시간 계산됩니다. 경로: /deal/create",
    "슬라이더 조정": "딜 생성 Step 3에서 슬라이더로 할인율(0~50%)을 조정하면 목표가와 절감액이 실시간 계산됩니다. 경로: /deal/create",
    "유사 딜방": "딜 생성 시 비슷한 제품의 기존 딜이 있으면 '비슷한 딜방이 있어요!' 카드가 표시됩니다. [참여 →] 버튼으로 기존 딜에 참여하거나 새로 만들 수 있습니다.",
    "비슷한 딜": "딜 생성 시 비슷한 제품의 기존 딜이 있으면 '비슷한 딜방이 있어요!' 카드가 표시됩니다. [참여 →] 버튼으로 기존 딜에 참여 가능.",
    # ---- 판매자 ----
    "배송비 유형": "배송비 3가지: 무료배송(FREE), 건당 배송비(PER_RESERVATION), 수량당 배송비(PER_ITEM: 기본배송비+개당배송비×수량). 설정: /seller/shipping-policy",
    "배송비 수량": "수량당 배송비(PER_ITEM): 기본배송비 + (개당배송비 × 수량). /seller/shipping-policy에서 설정.",
    "리뷰 답글": "판매자는 /seller/reviews에서 구매자 리뷰에 답글을 작성할 수 있습니다. 구매자 도착 확인 후 30일 이내 리뷰 작성 가능.",
    "판매자 승인": "회원가입 시 '판매자' 선택 → 사업자 정보 입력 → 서류 업로드 → 관리자 승인 (보통 1~2일). 승인 후 오퍼 제출 가능.",
    "세금계산서": "세금계산서는 정산 승인(APPROVED) 시 자동 생성됩니다. /seller/tax-invoices에서 확인하고 [확인] 버튼을 눌러주세요. 관리자가 일괄 발행합니다.",
    "세금계산서 확인": "세금계산서는 /seller/tax-invoices에서 확인할 수 있습니다. PENDING(확인 대기) 건의 [확인] 버튼을 눌러 내용을 확인하세요.",
    "세금계산서 발행": "세금계산서는 정산 승인(APPROVED) 시 자동 생성됩니다. 판매자 확인 후 관리자가 일괄 발행합니다. 경로: /seller/tax-invoices",
    "세금계산서 어디": "세금계산서는 /seller/tax-invoices에서 확인할 수 있습니다.",
    "사업자 정보 수정": "사업자 정보는 /seller/business-info에서 수정할 수 있습니다. 사업자등록증 이미지를 업로드하면 AI가 자동으로 정보를 파싱합니다.",
    "사업자등록증 OCR": "사업자등록증 이미지를 /seller/business-info에서 업로드하면 AI(GPT-4o)가 자동으로 상호/사업자번호/대표자명/업태/종목 등을 파싱합니다.",
    # ---- 관리자 ----
    "마이너리티 리포트": "🔮 마이너리티 리포트는 사용자 행동 분석 대시보드입니다. 구매자 8개 + 판매자 14개 = 22개 행동 수집 포인트. AI 프로파일링, 망설이는 구매자 감지, 판매자 오퍼 기회 매칭, 인기 검색 키워드 분석. 경로: /admin/minority-report",
    "마이너리티": "🔮 마이너리티 리포트: 사용자 행동 분석 대시보드. 22개 수집 포인트(구매자8+판매자14). 경로: /admin/minority-report",
    "행동 분석": "마이너리티 리포트: 구매자 8개(검색/딜조회/가격여정/참여/핑퐁이/카테고리/브랜드/관전) + 판매자 14개(검색/딜조회/오퍼수정/배송/정산/환불/리뷰/문의/정책/속도 등) = 22개 수집 포인트.",
    "행동 수집": "행동 수집 포인트: 구매자 8개 + 판매자 14개 = 총 22개. 경로: /admin/minority-report",
    "넛지 알림": "망설이는 구매자 넛지 알림: 같은 제품을 여러 번 검색하거나 딜방을 방문하지만 생성하지 않는 구매자를 감지 → '이 제품 딜방을 만들어볼까요?' 알림을 자동 발송. 경로: /admin/minority-report",
    "스킵 패턴": "판매자 스킵 패턴 분석: 판매자가 딜을 보고 오퍼를 안 내는 패턴을 분석. 목표가 너무 낮음/카테고리 안 맞음/수량 적음 등 스킵 사유 파악 → 딜 생성 가이드에 반영. 경로: /admin/minority-report",
    "환불 시뮬레이터": "환불 시뮬레이터: 수동 모드(조건 직접 입력) + 예약 조회 모드. 배송비 3가지(무료/건당/수량당). 환불 사유(구매자/판매자/시스템/분쟁) → 귀책+트리거 자동 매핑. 경로: /admin/refund-simulator",
    "ANO": "이상 감지: ANO-### 고유번호 자동 부여. 상태: Open → Processing → Closed. 상세 모달에서 발생일/내용/관련번호/처리결과 관리. 경로: /admin/anomalies",
    "RPT": "신고 관리: RPT-### 고유번호 자동 부여. 이상 감지(ANO)와 동일한 처리 워크플로우. 경로: /admin/reports",
    "defaults.yaml": "정책 관리: /admin/policy-params에서 defaults.yaml 실시간 수정 가능. 결제 제한시간, 오퍼 마감, 쿨링기간, 수수료율 등 SSOT(Single Source of Truth).",
    # ---- 액츄에이터 ----
    "액츄에이터": "액츄에이터는 판매자를 모집하고 지원하는 역할입니다. 추천 코드로 판매자와 연결되며 거래 성사 시 커미션을 받습니다. 커미션: Lv.6 0.5%, Lv.5 0.2%, Lv.4 0.1%, Lv.3↑ 0%.",
    "커미션": "액츄에이터 커미션: Lv.6(신규) 0.5%, Lv.5 0.2%, Lv.4 0.1%, Lv.3 이상 0%. 판매자 정산과 별도 지급.",
    "위탁계약서": "위탁계약서는 /actuator/contract 에서 확인·동의할 수 있습니다. 계약서 전문(14조)을 끝까지 읽고 3개 항목에 체크한 뒤 동의합니다. 계약 미동의 시 커미션 정산 불가.",
    "계약서 동의": "위탁계약서 동의: /actuator/contract → 계약서 스크롤 끝까지 → 체크 3개 → [동의하고 계약 체결]. 한 번 동의하면 재동의 불필요.",
    # ---- 필수 사실 교정 (잘못된 답변 방지) ----
    "감가 일수": "아닙니다! 감가(사용 차감)는 일수 기준이 아닙니다. 반품된 상품의 실제 상태(사용 흔적, 손상, 포장 상태)를 판매자가 검수(PASS/PARTIAL/FAIL)하여 결정합니다. 최대 감가율은 50%이며 초과 시 관리자가 개입합니다.",
    "사용 감가": "감가(사용 차감)는 일수 기준이 아닙니다. 반품된 상품의 실제 상태(사용 흔적, 손상, 포장 상태)를 판매자가 검수하여 결정합니다. PARTIAL이면 감가율(%)을 적용하여 부분 환불합니다. 최대 감가율: 50%.",
    "감가 기준": "감가(사용 차감)는 일수 기준이 아니라 검수 기반입니다. 판매자가 반품 상품을 실물 검수(PASS/PARTIAL/FAIL)하고, 상태에 따라 감가율을 결정합니다.",
    "PG 수수료 누가": "PG 수수료(약 3.3%)는 역핑 플랫폼이 전액 흡수합니다. 구매자나 판매자가 별도로 부담하지 않습니다. 환불 시에도 PG 수수료는 구매자에게 전가되지 않습니다.",
    "PG 수수료 부담": "PG 수수료(약 3.3%)는 역핑 플랫폼이 전액 흡수합니다. 구매자 부담이 아닙니다.",
    "포인트 차감": "포인트 적립은 결제금액의 1%이며, 환불 시에는 적립 포인트를 환불 비율만큼 비례 차감합니다. 고정 -20P가 아닙니다.",
    "Clawback": "Clawback(환수)은 이미 판매자에게 지급 완료(PAID)된 정산을 환수하는 절차입니다. 다음 정산에서 자동 상계되며, 판매자에게 별도 입금을 요구하지 않습니다.",
    "클로백": "Clawback(환수)은 이미 판매자에게 지급 완료(PAID)된 정산을 환수하는 절차입니다. 다음 정산에서 자동 상계됩니다.",
    "원천징수": "개인 액츄에이터 커미션은 원천징수 3.3%(소득세 3% + 지방소득세 0.3%) 공제 후 지급됩니다. 예: 10만원 커미션 → 3,300원 공제 → 96,700원 수령.",
    "3.3%": "개인 액츄에이터 원천징수율: 소득세 3% + 지방소득세 0.3% = 총 3.3%. 사업자 액츄에이터는 원천징수 대신 세금계산서 발행.",
    "액츄에이터 세금": "개인: 원천징수 3.3% 공제 후 지급. 사업자: 세금계산서 발행 (VAT 별도). 원천징수 영수증은 매년 2월 말 교부.",
    "커미션 정산": "모집한 판매자의 거래 성사 시 커미션이 발생합니다. 구매확정→쿨링7일→READY→승인→지급 순서로 진행돼요. 정산 내역: /actuator/settlements",
    "최소 지급액": "최소 지급액은 10,000원입니다. 미달 시 다음 정산으로 이월됩니다.",
    "계좌 등록": "개인 액츄에이터는 /actuator/bank-info에서 본인 명의 계좌를 등록해야 커미션을 받을 수 있어요.",
    "원천징수영수증": "개인 액츄에이터는 /actuator/settlements에서 원천징수영수증 PDF를 다운로드할 수 있어요. 연간 합산 영수증은 매년 2월 말 교부.",
    # ---- 공통 (새 기능) ----
    "FCM": "브라우저 알림을 허용하면 오퍼 도착, 배송 완료, 정산 준비 등 중요 알림을 실시간으로 받을 수 있어요!",
    "푸시 알림": "브라우저 알림을 허용하면 앱을 열지 않아도 중요 알림을 받을 수 있어요! 설정에서 알림 허용을 확인해주세요.",
    "실시간 채팅": "딜방에서 실시간 채팅이 가능해요! 메시지를 보내면 바로 상대방에게 전달됩니다. 입력 중 표시도 나와요.",
    "딜방 채팅": "딜방에서 실시간 채팅이 가능합니다 (WebSocket). 메시지를 보내면 즉시 전달되고, 입력 중 표시/온라인 목록도 지원해요.",
    "추천인": "추천 코드를 공유하면 친구가 가입할 때 추천인 포인트(+20P)를 받을 수 있어요!",
    "추천 코드": "추천 코드를 공유하면 친구가 가입할 때 추천인 포인트(+20P)를 받을 수 있어요! 마이페이지에서 확인하세요.",
    "딜 검색": "딜 목록에서 키워드나 카테고리로 원하는 딜을 검색할 수 있어요. 경로: /deals, /search",
    "포인트 사용": "적립된 포인트는 결제 시 사용할 수 있어요. 마이페이지에서 잔액을 확인하세요. 경로: /points",
    "정산내역서": "판매자/액츄에이터는 정산 상세에서 [PDF 다운로드] 버튼으로 정산내역서를 받을 수 있어요.",
    # ---- 공통 / 역할별 분기 ----
    "핑퐁이": "핑퐁이는 역핑의 AI 어시스턴트입니다. 딜 생성, 오퍼 비교, 배송 추적, 환불 정책, 가격 질문 등 역핑 관련 모든 것을 도와드립니다. 현재 페이지에 맞는 바로가기 버튼도 제공해요!",
    "뭘 도와": {
        "BUYER": "딜 생성(사진/음성/텍스트), 시장가 조회, 가격 챌린지, 배송 추적, 환불 안내, 분쟁 신청 등을 도와드려요! 😊",
        "SELLER": "오퍼 제출, 배송 관리, 정산 확인, 환불 처리, 리뷰 관리, 수수료 안내 등을 도와드려요!",
        "ADMIN": "마이너리티 리포트, 환불 시뮬레이터, 배송 일괄 조회, 이상 감지, 정책 관리 등 관리자 기능을 안내해드려요!",
        "ACTUATOR": "판매자 모집, 커미션 구조, 딜 탐색, 정산 관리 등을 안내해드려요!",
    },
    "도와줄 수 있": {
        "BUYER": "딜 생성(사진/음성/텍스트), 시장가 조회, 가격 챌린지, 배송 추적, 환불 안내, 분쟁 신청 등을 도와드려요! 😊",
        "SELLER": "오퍼 제출, 배송 관리, 정산 확인, 환불 처리, 리뷰 관리, 수수료 안내 등을 도와드려요!",
        "ADMIN": "마이너리티 리포트, 환불 시뮬레이터, 배송 일괄 조회, 이상 감지, 정책 관리 등 관리자 기능을 안내해드려요!",
        "ACTUATOR": "판매자 모집, 커미션 구조, 딜 탐색, 정산 관리 등을 안내해드려요!",
    },
}

# 역할별 접근 제한 정의
_FAQ_ADMIN_ONLY = {"마이너리티 리포트", "마이너리티", "행동 분석", "행동 수집", "넛지 알림",
                   "스킵 패턴", "환불 시뮬레이터", "ANO", "RPT", "defaults.yaml"}
_FAQ_BUYER_ONLY = {"사진으로 찾기", "사진 찍어서", "사진 검색", "사진으로 딜", "카메라",
                   "음성으로 딜", "음성 검색", "음성으로 제품", "마이크",
                   "가격 챌린지", "맞춰보기", "신뢰도", "초록 노랑 빨강",
                   "유사 딜방", "비슷한 딜", "딜 생성 단계", "단계가 몇", "몇 단계",
                   "목표가 슬라이더", "슬라이더 조정",
                   "딜 검색", "포인트 사용", "추천인", "추천 코드"}
_FAQ_ACTUATOR_ONLY = {"위탁계약서", "계약서 동의", "원천징수", "3.3%", "액츄에이터 세금",
                      "커미션 정산", "최소 지급액", "계좌 등록", "원천징수영수증"}


def _faq_direct_lookup(question: str, role: str) -> Optional[str]:
    """FAQ 직접 매핑 — retrieve_kb 보완. 긴 키 우선 매칭."""
    ql = (question or "").lower().strip()
    if not ql:
        return None
    role_u = (role or "").upper()

    best_match: Any = None
    best_len = 0

    for key, answer in _FAQ_DIRECT_MAP.items():
        if key.lower() in ql and len(key) > best_len:
            # 역핑 외 맥락에서 ambiguous 키 스킵 (예: "마이너리티 리포트 영화 줄거리")
            if key in _AMBIGUOUS_FAQ_KEYS and any(nkw in ql for nkw in _NON_YP_CONTEXT):
                continue
            # 역할 체크
            if key in _FAQ_ADMIN_ONLY and role_u != "ADMIN":
                continue
            if key in _FAQ_BUYER_ONLY and role_u not in ("BUYER", "ADMIN"):
                return "이 기능은 구매자 전용 기능입니다. 📍 구매자로 로그인하시면 이용 가능합니다."
            if key in _FAQ_ACTUATOR_ONLY and role_u not in ("ACTUATOR", "ADMIN"):
                return "이 기능은 액추에이터 전용 기능입니다. 📍 액추에이터로 로그인하시면 이용 가능합니다."
            best_match = answer
            best_len = len(key)

    if best_match is None:
        return None
    # 역할별 분기 (dict인 경우)
    if isinstance(best_match, dict):
        return best_match.get(role_u) or best_match.get("BUYER", "")
    return best_match


def _is_generic_answer(answer: str) -> bool:
    """역핑과 관련 없는 일반적인 답변인지 감지"""
    _generic_pats = [
        "앱에서", "앱 내", "일반적으로", "보통은", "설정 화면에서",
        "구글 렌즈", "카메라 아이콘을 눌러", "갤러리에서 선택",
        "다른 앱", "검색 앱에서", "앱 설정",
        "고객센터를 통해", "고객센터에 문의",
        "구체적인 종류에 대한 정보",
        "여러 가지가 있을 수",
        "손가락을 좌우로",
    ]
    return any(p in answer for p in _generic_pats)


def _is_yeokping_related(question: str) -> bool:
    """역핑 플랫폼 관련 질문인지 판별 (free chat vs KB 답변 결정용)"""
    _yk_keywords = [
        "역핑", "딜", "오퍼", "배송", "환불", "정산", "수수료", "판매자", "구매자",
        "액츄에이터", "딜방", "시장가", "목표가", "핑퐁", "가격 챌린지",
        "사진으로 딜", "음성으로 딜", "마이너리티 리포트", "시뮬레이터",
        "카카오 로그인", "네이버 로그인", "구글 로그인", "소셜 로그인",
        "분쟁", "신고", "리뷰", "운송장", "택배", "쿨링",
        "ANO", "RPT", "defaults", "yaml", "넛지", "스킵",
        "낙찰", "관전", "예측", "포인트", "등급",
        "/deal", "/seller", "/admin", "/my-order",
        "예약", "결제", "공동구매", "수취", "구매확정",
    ]
    q = question.lower()
    return any(kw.lower() in q for kw in _yk_keywords)


# FAQ ambiguous key 제외용 (영화/드라마 등 비역핑 맥락 감지)
_AMBIGUOUS_FAQ_KEYS = {"마이너리티 리포트", "마이너리티"}
_NON_YP_CONTEXT = ["영화", "줄거리", "감독", "배우", "출연", "시리즈", "드라마", "소설"]


# ============================================================
# Safety: Sensitive topic filter (법적 리스크 방어)
# ============================================================
_SENSITIVE_TOPICS: Dict[str, Dict[str, Any]] = {
    "politics": {
        "keywords": ["대통령", "국회", "여당", "야당", "보수", "진보", "탄핵", "선거", "투표",
                      "정당", "민주당", "국민의힘", "좌파", "우파", "정치"],
        "response": "오 정치 얘기는 사람마다 생각이 달라서 제가 뭐라 말씀드리긴 어렵네요 😅 대신 역핑에서 좋은 딜 찾아드릴까요?",
    },
    "religion": {
        "keywords": ["기독교", "불교", "이슬람", "천주교", "교회", "절에", "사찰", "성경", "코란",
                      "하나님", "부처님", "알라", "예수", "종교", "신앙"],
        "response": "종교는 정말 깊은 주제라 제가 섣불리 말씀드리긴 어렵네요 🙏 역핑 관련 궁금한 건 자신 있어요!",
    },
    "discrimination": {
        "keywords": ["혐오", "차별", "인종", "성차별", "여혐", "남혐", "장애인 비하", "외국인 혐오",
                      "흑인", "동남아", "조선족"],
        "response": "모든 사람은 소중하니까요 😊 혹시 역핑에서 찾으시는 제품 있으세요?",
    },
    "crime": {
        "keywords": ["살인", "폭행", "마약", "대마", "필로폰", "해킹 방법", "불법 도박", "몰카",
                      "성범죄", "사기 치는 법", "협박", "납치"],
        "response": "앗 그건 제가 도와드리기 어려운 영역이에요 😅 역핑에서 합법적으로 좋은 딜 찾아드릴까요?",
    },
    "profanity": {
        "keywords": ["시발", "씨발", "ㅅㅂ", "ㅆㅂ", "개새끼", "병신", "ㅂㅅ", "지랄", "ㅈㄹ",
                      "꺼져", "닥쳐", "미친놈", "미친년", "존나", "ㅈㄴ"],
        "response": "헉 😳 조금 순화해서 말씀해 주시면 더 잘 도와드릴 수 있어요! 뭐가 궁금하셨어요?",
        "log": True,
    },
    "adult": {
        "keywords": ["야동", "포르노", "성인물", "섹스", "자위", "매춘", "성매매", "av배우",
                      "19금", "음란"],
        "response": "앗 그건 제 전문 분야가 아니에요 😅 역핑 쇼핑 관련이면 자신 있는데!",
    },
    "self_harm": {
        "keywords": ["자살", "자해", "죽고 싶", "삶이 힘들", "극단적 선택", "목숨"],
        "response": "많이 힘드시죠... 혼자 감당하지 마시고 전문 상담 받아보세요 💙\n"
                     "자살예방상담전화: 1393\n"
                     "정신건강위기상담전화: 1577-0199\n"
                     "언제든 도움받으실 수 있어요.",
    },
    "medical": {
        "keywords": ["암 치료", "약 처방", "진단해줘", "증상이", "병원 추천", "항암제", "수술 방법",
                      "우울증 약", "당뇨 치료", "혈압 약"],
        "response": "건강 관련은 꼭 전문의 선생님과 상담하시는 게 좋아요! 🏥 역핑에서 궁금한 건 제가 도와드릴게요 😊",
    },
    "legal": {
        "keywords": ["소송 방법", "고소 하려면", "변호사 추천", "법적 책임", "형사 고발", "민사 소송",
                      "합의금", "벌금 얼마"],
        "response": "법률 문제는 변호사님과 상담하시는 게 정확해요 ⚖️ 역핑 관련이면 제가 도와드릴게요!",
    },
    "investment": {
        "keywords": ["주식 추천", "코인 추천", "투자 종목", "몇 배 오를", "매수 타이밍", "공매도",
                      "선물 거래", "레버리지", "떡상"],
        "response": "투자는 전문가 의견이 중요해요 📊 역핑에서 좋은 딜 찾는 건 도와드릴 수 있어요!",
    },
}


def _check_sensitive_topic(question: str) -> Optional[Tuple[str, str, bool]]:
    """민감 토픽 감지. 매칭 시 (category, response, should_log) 반환, 아니면 None."""
    q = question.lower()
    for cat, info in _SENSITIVE_TOPICS.items():
        for kw in info["keywords"]:
            if kw.lower() in q:
                return (cat, info["response"], info.get("log", False))
    return None


# ============================================================
# Exported time SSOT loader (for autotest_v2 imports)
# ============================================================
SSOT_TIME: Dict[str, float] = {}
_TIME_LOADED = False

def load_time_values_from_defaults() -> None:
    global SSOT_TIME, _TIME_LOADED
    if _TIME_LOADED:
        return
    root = repo_root()
    path = root.joinpath(*DEFAULTS_YAML_PATH)
    if not path.exists():
        SSOT_TIME = {}
        _TIME_LOADED = True
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        SSOT_TIME = {}
        _TIME_LOADED = True
        return

    out: Dict[str, float] = {}
    in_time = False
    base_indent: Optional[int] = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s*time\s*:\s*$", line):
            in_time = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_time:
            continue
        indent = len(line) - len(line.lstrip())
        if base_indent is not None and indent <= base_indent:
            break
        m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", line)
        if not m:
            continue
        out[m.group(1).strip()] = float(m.group(2))
    SSOT_TIME = out
    _TIME_LOADED = True

def fmt_time_value(key: str, v: float) -> str:
    if key.endswith("_minutes") or key.endswith("_priority_minutes") or key.endswith("_timeout_minutes"):
        return f"{int(round(v))}분"
    if key.endswith("_days"):
        return f"{int(round(v))}일"
    if key.endswith("_hours"):
        if v < 1:
            return f"{int(round(v * 60))}분"
        if float(v).is_integer():
            return f"{int(v)}시간"
        hh = int(v)
        mm = int(round((v - hh) * 60))
        return f"{hh}시간 {mm}분" if mm > 0 else f"{hh}시간"
    return str(int(v)) if float(v).is_integer() else str(v)

# ============================================================
# Patterns / IDs
# ============================================================
_YEOKPING_HINT_PAT = re.compile(
    r"(역핑|딜|deal\b|오퍼|offer\b|예약|reservation\b|환불|취소|refund|cancel|"
    r"배송|shipping|수수료|fee|포인트|point|정산|settlement|등급|티어|tier|레벨|level|"
    r"deadline|결제|payment|쿨링|cooling|공동구매|액츄에이터|actuator|"
    r"관리자|분쟁|클레임|어필|이의\s*제기|dispute|claim|appeal)",
    re.IGNORECASE,
)

PRICE_PAT = re.compile(r"(최저가|가격|얼마|price)", re.IGNORECASE)
WEATHER_PAT = re.compile(r"(날씨|weather|forecast|강수|기온|미세먼지|자외선)", re.IGNORECASE)
# 쇼핑 사이트명만으로 구성된 검색어 감지 (eq fallback용)
_SITE_ONLY_PAT = re.compile(
    r"^(다나와|에누리|쿠팡|지마켓|옥션|11번가|인터파크|네이버\s*쇼핑)\s*$",
    re.IGNORECASE,
)
# 쇼핑 사이트 + 가격 의도 조합 감지 (SMALLTALK 오분류 방지)
_SHOP_PRICE_PAT = re.compile(
    r"(다나와|에누리|쿠팡|지마켓|옥션|11번가|네이버\s*쇼핑).*(찾|검색|알려|얼마|가격|최저)",
    re.IGNORECASE,
)
# 문맥 기반 역핑 승격용 범용 키워드 (직전 2턴 YEOKPING 컨텍스트에서만 작동)
_CONTEXT_YK_PAT = re.compile(
    r"(레벨|등급|수수료|혜택|조건|승급|티어|tier|level)",
    re.IGNORECASE,
)
# 실제 날씨 조회 쿼리 판정용 (단순 언급과 구분)
_WEATHER_QUERY_PAT = re.compile(
    r"(날씨\s*(어때|어떤|어떻게|알려|예보|맞아|괜찮|맑|흐린|비|눈|기온|강수)|"
    r"(오늘|내일|모레|이번\s*주|주말)\s*(날씨|기온)|"
    r"기온|강수확률|미세먼지|황사|자외선지수|weather|forecast)",
    re.IGNORECASE,
)
NEWS_PAT = re.compile(r"(뉴스|헤드라인|해드라인|headline|news)", re.IGNORECASE)

FINANCE_PAT = re.compile(r"(종합주가지수|코스피|kospi|코스닥|kosdaq|종가(?!집)|주가|증시|지수|환율|원/달러|usd|krw|달러|엔화|유로|환전|고시환율|매매기준율)", re.IGNORECASE)

EXTERNAL_ASK_PAT = re.compile(
    r"(검색|찾아|조회|요약|알려|뉴스|헤드라인|해드라인|날씨|기온|강수|미세먼지|price|가격|최저가|얼마|시세)",
    re.IGNORECASE,
)


TIME_Q_PAT = re.compile(
    r"(몇\s*(시간|분|일)|기간|지속|유효|마감|남은\s*시간|deadline|until|"
    r"쿨링|cooling|환불\s*가능|취소\s*가능|무상\s*환불|결제창|payment\s*window|우선\s*시간|priority|타임아웃|timeout|윈도우|window|제한\s*시간|time\s*limit)",
    re.IGNORECASE,
)
HOWTO_PAT = re.compile(r"(어떻게|방법|절차|순서|가이드|설명|정의|뭐야|무엇|만들|생성|등록|가입)", re.IGNORECASE)
# 특정 엔티티 ID(한국어·영어)가 있는 인스턴스 한정 시간 질문 → YEOKPING_GENERAL로 서버 조회
INSTANCE_TIME_PAT = re.compile(
    r"(딜|오퍼|예약|deal|offer|reservation)\s*(?:[_\s]?(?:id|번호))?\s*#?\s*\d+.*(언제|남은\s*시간|마감|정확한|까지)",
    re.IGNORECASE,
)
# yes/no 가능성 질문: "취소 가능해?", "환불 가능해?" → YEOKPING_GENERAL
_YESNO_END_PAT = re.compile(
    r"(가능해|가능해요|가능한가요|가능합니까|가능할까|돼요|될까요|되나요|되나\s*\??)\s*\??$",
    re.IGNORECASE,
)
# 조건부 결과 질문: "쿨링기간 지나면 정산 돼?" → YEOKPING_GENERAL
_AFTER_TIME_PAT = re.compile(
    r"(지나면|지나고|이후|끝나면|완료되면|지난\s*후).*(돼|되나|될까|해줘|하면|어떻게)",
    re.IGNORECASE,
)
# "내 reservation/딜/오퍼" 소유 참조 → YEOKPING_GENERAL (서버 조회)
_ENTITY_POSSESS_PAT = re.compile(
    r"(내\s*(딜|오퍼|예약|reservation|deal|offer)|my\s*(deal|offer|reservation))",
    re.IGNORECASE,
)
# "정산 기간/일정/언제" → 정산은 프로세스 질문 → YEOKPING_GENERAL
_SETTLE_TIME_PAT = re.compile(r"정산\s*(기간|일정|언제|시기|주기|얼마)", re.IGNORECASE)
# "포인트" + 기간 질문 → YEOKPING_GENERAL (포인트 정책은 서버 조회)
_POINT_TOPIC_PAT = re.compile(r"포인트", re.IGNORECASE)
# 잔액 조회 의도만 → call_preview_me() 호출
# 정책 질문(유효기간/적립기준/결제/환불)은 매칭 안 됨 → pingpong/ask fall-through
_POINT_BALANCE_PAT = re.compile(
    r"(잔액|내\s*포인트|포인트\s*(얼마|남|몇)|남은\s*포인트|몇\s*점)",
    re.IGNORECASE,
)

_ID_ONLY_PAT = re.compile(r"^\s*#?\s*(\d{1,9})\s*(번|호)?\s*(?:이야|입니다|예요|요)?\s*[.!?]?\s*$")
_LINK_REQ_PAT = re.compile(r"(출처|링크|url|네이버|구글|다나와|쿠팡)", re.IGNORECASE)

# ============================================================
# LLM Intent Classification
# ============================================================
@dataclass
class IntentResult:
    kind: str
    # TIME_POLICY, EXTERNAL_WEATHER, EXTERNAL_NEWS, EXTERNAL_PRICE,
    # EXTERNAL_FINANCE, YEOKPING_GENERAL, SMALLTALK
    external_query: Optional[str] = None
    from_fallback: bool = False

_intent_cache: Dict[str, Tuple[float, "IntentResult"]] = {}
_INTENT_CACHE_TTL = 60.0  # seconds

_INTENT_SYSTEM = """\
CRITICAL: Your ENTIRE response must be exactly one JSON object on a single line. \
Nothing before it, nothing after it. No markdown fences, no explanation, no greeting.

RESPONSE FORMAT: {"intent": "INTENT_NAME", "query": null}

You classify messages for 역핑(Yeokping), a Korean group-buying platform.

INTENT VALUES (pick exactly one):
  TIME_POLICY      - Generic platform policy DURATION question only
                     e.g. "쿨링 기간이 며칠이야?", "오퍼 마감이 몇 시간?", "결제 제한시간은?"
                     NOT for questions about a specific numbered entity (deal #N, offer #N, reservation #N)
  EXTERNAL_WEATHER - Weather query
  EXTERNAL_NEWS    - News/headline query
  EXTERNAL_PRICE   - Price query containing a brand or model name
                     (갤럭시, 아이폰, LG 그램, 맥북, RTX, 노트북 모델명 등)
  EXTERNAL_FINANCE - Financial market data: 환율, 주가, 코스피/코스닥, 금리, 지수 등
  YEOKPING_GENERAL - Yeokping platform question (refund, fees, shipping, points, how-to,
                     disputes, admin reports, and ALL questions about a specific deal/offer/reservation)
  SMALLTALK        - Everything else (default when unsure)

CLASSIFICATION RULES:

[RULE 1 — Entity+Number = YEOKPING_GENERAL, NOT TIME_POLICY]
If the question references a specific deal, offer, or reservation by number or ID,
it is ALWAYS YEOKPING_GENERAL regardless of time-related words:
  "딜 10번 상태가 어떻게 돼?" → YEOKPING_GENERAL  (딜 + 번호)
  "오퍼 11번 이미 낙찰됐어?" → YEOKPING_GENERAL  (오퍼 + 번호)
  "deal_id 15 마감이 언제야?" → YEOKPING_GENERAL  (deal_id + 번호, even with "마감")
  "딜 33번 정산 언제 돼?" → YEOKPING_GENERAL      (딜 + 번호, even with "정산/언제")
  "reservation 7번 쿨링기간이 얼마야?" → YEOKPING_GENERAL  (reservation + 번호)

[RULE 2 — TIME_POLICY is ONLY generic "how long?" policy questions]
TIME_POLICY applies ONLY when asking about the platform's DEFAULT policy duration,
with no specific entity number attached:
  "쿨링 기간이 며칠이야?" → TIME_POLICY          (no entity number → generic rule)
  "오퍼 마감이 몇 시간?" → TIME_POLICY            (no entity number → generic rule)
  "결제 제한시간은 얼마야?" → TIME_POLICY         (no entity number → generic rule)
NOT TIME_POLICY:
  "쿨링기간 지나면 정산 돼?" → YEOKPING_GENERAL  (asking what HAPPENS after, not how long)
  "내 reservation 취소 가능 기간이 얼마야?" → YEOKPING_GENERAL  (내 = specific user's entity)
  "취소 가능해?" → YEOKPING_GENERAL               (yes/no possibility, not a duration)
  "환불 가능해?" → YEOKPING_GENERAL               (yes/no possibility, not a duration)

[RULE 3 — Platform actions = YEOKPING_GENERAL]
Actions performed inside the Yeokping platform → YEOKPING_GENERAL:
  "관리자한테 신고할 수 있어?" → YEOKPING_GENERAL  (신고 = platform report action)
  "판매자 분쟁 어떻게 해?" → YEOKPING_GENERAL      (분쟁 = platform dispute)
  "클레임 넣으려면?" → YEOKPING_GENERAL            (클레임 = platform claim)

[RULE 4 — Other classification rules]
- "마감" in non-Yeokping context (지원서/입학/취업/공모전/시험/이벤트 마감 등) → SMALLTALK
- Yeokping-exclusive terms → YEOKPING_GENERAL even without "역핑" prefix:
    액츄에이터, actuator, 딜방, 딜룸, 오퍼, 역입찰, 쿨링, 역핑, yeokping,
    공동구매 플랫폼, 구매자 포인트, 판매자 수수료, 정산, 예약, 구매확정
- EXTERNAL_FINANCE is ONLY for financial market data. Person income/salary/earnings
  (e.g. "박찬호 얼마 벌었어", "손흥민 연봉", "BTS 수입") → SMALLTALK, NOT EXTERNAL_FINANCE
- Price + brand/model name → EXTERNAL_PRICE. "얼마야?" alone → SMALLTALK
- "수수료 얼마?" → YEOKPING_GENERAL (platform fee, not product price)
- "query": search string for EXTERNAL_* intents, null for everything else
- When in doubt → SMALLTALK

EXAMPLE OUTPUTS (these are COMPLETE valid responses):
{"intent": "SMALLTALK", "query": null}
{"intent": "EXTERNAL_PRICE", "query": "갤럭시 S25"}
{"intent": "TIME_POLICY", "query": null}
{"intent": "YEOKPING_GENERAL", "query": null}
"""


def classify_intent(
    q: str,
    prev_mode: str,
    recent_history: List[Dict[str, str]],
    client: OpenAI,
) -> "IntentResult":
    """LLM으로 의도 분류. 실패 시 _intent_fallback_regex()로 graceful degradation."""
    cache_key = f"{q}||{prev_mode}"
    now = time.time()
    if cache_key in _intent_cache:
        ts, cached = _intent_cache[cache_key]
        if now - ts < _INTENT_CACHE_TTL:
            return cached

    ctx_line = ""
    if recent_history and prev_mode == "yeokping":
        last_bot = (recent_history[-1].get("bot") or "")[:80]
        ctx_line = f"\n[Previous bot response snippet]: {last_bot}"

    user_text = f"[User]: {q}{ctx_line}"
    raw_json = ""

    try:
        resp = client.chat.completions.create(
            model=INTENT_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user", "content": user_text},
            ],
            max_completion_tokens=150,
        )
        raw_json = (resp.choices[0].message.content or "").strip()
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json).rstrip("`").strip()
        if not raw_json:
            finish_reason = (resp.choices[0].finish_reason or "unknown")
            _dbg(
                "classify_intent: LLM returned empty response"
                f" (finish_reason={finish_reason!r},"
                f" model={INTENT_MODEL!r},"
                f" max_tokens=60)"
            )
            raise ValueError("empty LLM response")
        data = json.loads(raw_json)
        kind = str(data.get("intent") or "SMALLTALK").strip().upper()
        _valid = {
            "TIME_POLICY", "EXTERNAL_WEATHER", "EXTERNAL_NEWS",
            "EXTERNAL_PRICE", "EXTERNAL_FINANCE",
            "YEOKPING_GENERAL", "SMALLTALK",
        }
        if kind not in _valid:
            kind = "SMALLTALK"
        query = data.get("query") or None
        result = IntentResult(kind=kind, external_query=query)
    except Exception as e:
        _dbg(f"classify_intent LLM failed ({type(e).__name__}: {e}) | raw={raw_json!r}")
        result = _intent_fallback_regex(q, prev_mode)

    # ✅ 역핑 전용어 안전망: LLM이 SMALLTALK으로 분류했지만 역핑 핵심 키워드가 있으면 오버라이드
    # "마감" 단독 매칭 제외 (입학 마감, 취업 마감 등 일반 질문 오작동 방지)
    if result.kind == "SMALLTALK" and is_yeokping_related(q):
        _yk_tokens = re.findall(
            r"(역핑|공동구매|오퍼|offer|딜|deal|액츄에이터|예약|reservation|환불|수수료|정산|쿨링|배송비)",
            q, re.IGNORECASE,
        )
        if _yk_tokens:
            result = IntentResult(kind="YEOKPING_GENERAL")

    # ✅ 쇼핑 사이트 안전망: "에누리에서도 찾아줘" 등 SMALLTALK 오분류 방지
    if result.kind == "SMALLTALK" and _SHOP_PRICE_PAT.search(q):
        result = IntentResult(kind="EXTERNAL_PRICE", external_query=S.last_price_query or q)

    # ✅ 문맥 기반 안전망: 직전 2턴이 YEOKPING이면 범용 키워드도 역핑으로 승격
    # ("레벨", "등급" 등은 _YEOKPING_HINT_PAT에 넣으면 게임/일반 질문까지 오작동)
    if result.kind == "SMALLTALK":
        _has_recent_yk = any("YEOKPING" in i for i in (S.recent_intents or []))
        if _has_recent_yk and _CONTEXT_YK_PAT.search(q):
            result = IntentResult(kind="YEOKPING_GENERAL")

    _intent_cache[cache_key] = (now, result)
    return result


def _intent_fallback_regex(q: str, prev_mode: str) -> "IntentResult":
    """LLM 실패 시 기존 regex 로직으로 분류. from_fallback=True 마킹."""
    if FINANCE_PAT.search(q):
        return IntentResult(kind="EXTERNAL_FINANCE", from_fallback=True)
    if _WEATHER_QUERY_PAT.search(q):
        return IntentResult(kind="EXTERNAL_WEATHER", from_fallback=True)
    if NEWS_PAT.search(q):
        return IntentResult(kind="EXTERNAL_NEWS", from_fallback=True)
    if not _EARNINGS_PAT.search(q):
        if (PRICE_PAT.search(q) or _PRICE_CONTEXT_PAT.search(q)) and _PRODUCT_HINT_PAT.search(q):
            return IntentResult(kind="EXTERNAL_PRICE", from_fallback=True)
    if is_yeokping_related(q) or prev_mode == "yeokping":
        if TIME_Q_PAT.search(q) and not HOWTO_PAT.search(q) and not INSTANCE_TIME_PAT.search(q):
            # 다음 케이스는 YEOKPING_GENERAL이 맞음 — TIME_POLICY 제외
            _is_time_policy = not (
                _YESNO_END_PAT.search(q)       # "취소 가능해?", "환불 가능해?" (가능 여부 질문)
                or _AFTER_TIME_PAT.search(q)   # "쿨링기간 지나면 정산 돼?" (조건부 결과)
                or _ENTITY_POSSESS_PAT.search(q)  # "내 reservation 취소 가능 기간"
                or _SETTLE_TIME_PAT.search(q)  # "정산 기간이 얼마야?"
                or _POINT_TOPIC_PAT.search(q)  # "포인트 유효기간은?"
            )
            if _is_time_policy:
                return IntentResult(kind="TIME_POLICY", from_fallback=True)
    if is_yeokping_related(q):
        return IntentResult(kind="YEOKPING_GENERAL", from_fallback=True)
    if prev_mode == "yeokping" and parse_id_only(q) is not None:
        return IntentResult(kind="YEOKPING_GENERAL", from_fallback=True)
    # 가격 비교 사이트 지명 + 이전에 외부 검색 문맥이었으면 → EXTERNAL_PRICE
    # (예: "에누리에서도 찾아줘" — prev_mode="external" after 맥북 가격 질문)
    if _SHOPPING_SITE_PAT.search(q) and prev_mode == "external":
        return IntentResult(kind="EXTERNAL_PRICE", from_fallback=True)
    return IntentResult(kind="SMALLTALK", from_fallback=True)


def is_yeokping_related(q: str) -> bool:
    return bool(_YEOKPING_HINT_PAT.search(q or ""))


def extract_ids_from_text(q: str) -> Dict[str, Optional[int]]:
    q = (q or "").strip()
    out: Dict[str, Optional[int]] = {"deal_id": None, "offer_id": None, "reservation_id": None}

    def _looks_like_duration(text: str) -> bool:
        # "13분" 같은 duration만 제외. "13번"은 제외하면 안 됨.
        return bool(re.search(r"\d+\s*(시간|분|일|주|개월|년)\b", text))

    def _pick(pat: str) -> Optional[int]:
        m = re.search(pat, q, re.IGNORECASE)
        if not m:
            return None
        try:
            v = int(m.group(1))
            return v if v > 0 else None
        except Exception:
            return None

    if _looks_like_duration(q):
        return out

    # ✅ 핵심: "예약13", "예약번호13번", "예약번호#13", "reservation 13" 전부 커버
    out["reservation_id"] = _pick(
        r"(?:예약(?:\s*번호)?|reservation)\s*(?:번호|id)?\s*#?\s*(\d{1,9})\s*(?:번|호)?"
    )
    out["offer_id"] = _pick(
        r"(?:오퍼(?:\s*번호)?|offer)\s*(?:번호|id)?\s*#?\s*(\d{1,9})\s*(?:번|호)?"
    )
    out["deal_id"] = _pick(
        r"(?:딜방(?:\s*번호)?|딜(?:\s*번호)?|deal)\s*(?:번호|id)?\s*#?\s*(\d{1,9})\s*(?:번|호)?"
    )

    return out

# 가격 비교 사이트 직접 지명 → 이전 외부(external) 문맥에서 EXTERNAL_PRICE 처리
_SHOPPING_SITE_PAT = re.compile(
    r"(다나와|에누리|쿠팡|지마켓|옥션|11번가|인터파크|네이버\s*쇼핑)",
    re.IGNORECASE,
)

# ============================================================
# External gating (OPTION 1): only Weather/News/Product-Price
# ============================================================

_EARNINGS_PAT = re.compile(
    r"(연봉|수입|소득|재산|자산|순자산|계약금|총\s*수입|총\s*연봉|"
    r"얼마\s*벌|얼마나\s*벌|돈\s*많이\s*벌|salary|income|net\s*worth|earnings)",
    re.IGNORECASE,
)

_PRICE_CONTEXT_PAT = re.compile(
    r"(가격|최저가|시세|원|만원|할인|쿠폰|재고|구매|구입|판매|"
    r"model|모델|spec|스펙|ram|ssd|hdd|cpu|gpu|win11|windows\s*11)",
    re.IGNORECASE,
)

# 아주 러프한 "제품/브랜드/모델명" 힌트 (필요하면 리스트 늘려도 됨)
_PRODUCT_HINT_PAT = re.compile(
    r"(노트북|그램|laptop|폰|스마트폰|iphone|galaxy|맥북|macbook|"
    r"lg\s*그램|lggram|samsung|apple|lenovo|asus|msi|dell|hp|acer|"
    r"\b[A-Z]{2,}\d{2,}\b|\b\d{4}\b)",  # 모델명/연식 힌트
    re.IGNORECASE,
)

_EXTERNAL_STOPWORDS = [
    "대략", "대략적인", "대충", "좀", "알려줘", "알려", "말해줘", "말해", "추천해줘", "추천",
    "찾아줘", "찾아", "검색", "조회", "요약", "헤드라인", "뉴스", "날씨", "기온", "강수", "미세먼지",
    "시장가격", "시중가", "최저가", "가격", "얼마", "시세", "부탁", "가능", "해줘", "주세요",
]

def _compact_query_for_external(kind: str, q: str) -> str:
    """
    external 검색용 쿼리를 '짧고 의미있게' 축약한다.
    - 옵션1 기준: weather/news/price만 들어온다.
    """
    s = (q or "").strip()
    if not s:
        return s

    # 공백 정리
    s = re.sub(r"\s+", " ", s)

    # 스펙 흔한 오타/축약 정규화 (필요 최소만)
    s = re.sub(r"\bwin\s*11\b", "Windows 11", s, flags=re.IGNORECASE)
    s = re.sub(r"\b1tm\b", "1TB", s, flags=re.IGNORECASE)      # 흔한 오타 가정
    s = re.sub(r"\b516mb\b", "16GB", s, flags=re.IGNORECASE)   # 흔한 오타 가정
    s = s.replace("1TM", "1TB").replace("516MB", "16GB")

    # 불필요 문장부 제거(가격/뉴스/날씨 공통)
    for w in _EXTERNAL_STOPWORDS:
        s = re.sub(rf"\b{re.escape(w)}\b", " ", s, flags=re.IGNORECASE)

    s = re.sub(r"\s+", " ", s).strip()

    # kind별 최소 보정
    if kind == "weather":
        # 지역이 있으면 남기고, 없으면 질문 자체로도 OK
        return s or q
    if kind == "news":
        # "주제 키워드"만 남기는 게 목표
        return s or q
    if kind == "price":
        # 가격은 너무 짧아지면 오히려 망하니, 최소 길이 보정
        # (브랜드/제품명/스펙이 거의 안 남으면 원문을 쓴다)
        if len(s) < 6:
            return q
        return s

    return s or q

def infer_external_kind_option1(q: str) -> Optional[str]:
    """
    옵션 1: weather/news/price만 external로 보낸다.
    - price는 "제품/모델/브랜드" 힌트가 있을 때만
    - 연봉/재산/얼마 벌었어 같은 건 price로 절대 보내지 않음
    """
    text = (q or "").strip()
    if not text:
        return None

    # 1) 날씨
    if WEATHER_PAT.search(text):
        return "weather"

    # 2) 뉴스
    if NEWS_PAT.search(text):
        return "news"

    # 3) 제품가격/시세
    # "얼마 벌었어/연봉/재산" 류는 price에서 제외
    if _EARNINGS_PAT.search(text):
        return None

    # ✅ finance는 숫자 계산/정책이 아니라 "링크 안내 external"로 처리 (ask로 보내지 않기)
    if FINANCE_PAT.search(q or ""):
        return "finance"

    # 가격/시세 의도가 있고 + 제품 힌트가 있어야만 external(price)
    if PRICE_PAT.search(text) or _PRICE_CONTEXT_PAT.search(text):
        if _PRODUCT_HINT_PAT.search(text):
            return "price"
        return None

    return None



def parse_id_only(raw: str) -> Optional[int]:
    m = _ID_ONLY_PAT.match((raw or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

# ============================================================
# Deterministic time policy answer (policy questions only)
# ============================================================
def maybe_answer_time_policy_only(q: str) -> Optional[str]:
    q = (q or "").strip()
    if not q:
        return None
    if HOWTO_PAT.search(q):
        return None
    if not TIME_Q_PAT.search(q):
        return None
    if INSTANCE_TIME_PAT.search(q):
        return None

    rows: List[str] = []

    def add(label: str, key: str) -> None:
        v = SSOT_TIME.get(key)
        if v is None:
            return
        rows.append(f"{label}은 {fmt_time_value(key, v)}입니다.")

    # deal
    if re.search(r"(딜방|딜|deal).*(모집|마감|유효|지속|기간)", q, re.IGNORECASE):
        add("딜방 모집/마감 기본", "deal_deadline_hours")

    # offer
    if re.search(r"(오퍼|offer).*(수정|editable|edit)", q, re.IGNORECASE):
        add("오퍼 수정 가능 구간", "offer_editable_window_hours")
    if re.search(r"(오퍼|offer).*(마감|유효|지속|기간)", q, re.IGNORECASE):
        add("오퍼 마감 기본", "offer_deadline_hours")

    # payment
    if re.search(r"(결제창|payment\s*window|오퍼\s*마감\s*후\s*결제)", q, re.IGNORECASE):
        add("오퍼 마감 후 결제창", "buyer_payment_window_hours")
    if re.search(r"(예약|reservation).*(결제|타임아웃|제한|timeout)|결제\s*제한\s*시간", q, re.IGNORECASE):
        add("예약 후 결제 제한시간", "payment_timeout_minutes")

    # refund/cooling
    if re.search(r"(쿨링|cooling|환불\s*가능|취소\s*가능|무상\s*환불)", q, re.IGNORECASE):
        add("쿨링(환불 가능 기간) 기본", "cooling_days")

    # leader priority
    if re.search(r"(방장|리더|leader).*(우선|priority)", q, re.IGNORECASE):
        add("방장 우선 시간", "buyer_leader_priority_minutes")

    # seller decision
    if re.search(r"(판매자|seller).*(결정|decision).*(제한|timeout|시간|기간)", q, re.IGNORECASE):
        add("판매자 결정 제한시간", "seller_decision_timeout_hours")
    if re.search(r"(판매자|seller).*(결정).*(윈도우|window)", q, re.IGNORECASE):
        v = SSOT_TIME.get("seller_decision_window_hours")
        if v is not None:
            if abs(v - 0.5) < 1e-9:
                rows.append("판매자 결정 윈도우는 30분입니다.")
            else:
                rows.append(f"판매자 결정 윈도우는 {fmt_time_value('seller_decision_window_hours', v)}입니다.")

    if not rows:
        add("쿨링(환불 가능 기간) 기본", "cooling_days")

    if not rows:
        return None

    return " ".join(rows) + " (defaults.yaml SSOT 기준)"

# ============================================================
# External fetch (budgeted)
#  - ALWAYS returns links (list, can be empty)
#  - price: invalidate absurd low for expensive items
# ============================================================
_PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+)\s*원")
STOPWORDS_PRICE_QUERY = {
    "가격","최저가","얼마","좀","검색","검색해","검색해줘","알려줘","알려","가능","가능해","수","있어","있나요",
    "찾아","찾아줘","정보","부탁","해줄","해줘","모두","다","전부","전체",
}
EXPENSIVE_HINT = re.compile(
    r"(노트북|laptop|그램|gram|갤럭시북|galaxy\s*book|macbook|아이폰|iphone|갤럭시\s*s|rtx|oled|tv|"
    r"냉장고|세탁기|카메라|gpu|i7|i9|m3|m4|nt\d+|[A-Z]{2,}\d{3,})",
    re.IGNORECASE,
)

def _to_int_krw(s: str) -> Optional[int]:
    try:
        return int(s.replace(",", ""))
    except Exception:
        return None

def normalize_price_query(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"[?？!！]+$", "", s)
    toks = re.findall(r"[가-힣A-Za-z0-9]+", s)
    kept = [t for t in toks if t.lower() not in STOPWORDS_PRICE_QUERY]
    out = " ".join(kept).strip()
    return out if len(out) >= 2 else s

def _percentile(xs: List[int], p: float) -> Optional[int]:
    if not xs:
        return None
    xs2 = sorted(xs)
    k = int(round((len(xs2) - 1) * p))
    k = max(0, min(k, len(xs2) - 1))
    return xs2[k]

def fetch_naver_shopping(query: str, display: int = 3) -> list:
    """
    네이버 쇼핑 검색 API 호출.
    Returns: [{"title": "...", "lprice": "1051000", "hprice": "...",
               "mallName": "...", "link": "...", "brand": "...", "maker": "..."}, ...]
    실패 시 빈 리스트 반환.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": display, "sort": "sim"},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("items", [])
    except Exception:
        pass
    return []


def fetch_price_external(q: str) -> Dict[str, Any]:
    query = normalize_price_query(q)
    links = [
        {"title": f"네이버쇼핑 '{query}'", "url": f"https://search.shopping.naver.com/search/all?query={quote_plus(query)}"},
        {"title": f"다나와 '{query}'", "url": f"https://search.danawa.com/dsearch.php?k1={quote_plus(query)}"},
        {"title": f"쿠팡 '{query}'", "url": f"https://www.coupang.com/np/search?q={quote_plus(query)}"},
    ]

    nums: List[int] = []
    try:
        r = HTTP.get(links[1]["url"], timeout=EXTERNAL_TIMEOUT)
        html = r.text or ""
        for m in _PRICE_RE.finditer(html):
            v = _to_int_krw(m.group(1))
            if v:
                nums.append(v)
    except Exception:
        nums = []

    nums = sorted(nums)[:300]
    low = min(nums) if nums else None
    p10 = _percentile(nums, 0.10) if nums else None
    p50 = _percentile(nums, 0.50) if nums else None
    p90 = _percentile(nums, 0.90) if nums else None

    if EXPENSIVE_HINT.search(query) and low is not None and low < 50000:
        return {"kind": "price", "ok": False, "links_only": True, "query": query, "links": links}

    ok = bool(nums and low is not None and p90 is not None)
    return {"kind": "price", "ok": ok, "links_only": (not ok), "query": query, "low_estimate": low, "range": {"p10": p10, "p50": p50, "p90": p90}, "links": links}

def fetch_news_external(q: str) -> Dict[str, Any]:
    query = normalize_external_query(q)
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    links = [
        {"title": f"구글뉴스 '{query}'", "url": f"https://news.google.com/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"},
        {"title": f"네이버뉴스 '{query}'", "url": f"https://search.naver.com/search.naver?where=news&query={quote_plus(query)}"},
    ]
    try:
        r = HTTP.get(rss_url, timeout=EXTERNAL_TIMEOUT)
        if r.status_code != 200:
            return {"kind": "news", "ok": False, "links": links}
        root = ET.fromstring(r.text)
    
        items = []
        for it in root.findall(".//item")[:5]:
            t = (it.findtext("title") or "").strip()
            u = (it.findtext("link") or "").strip()
            if t and u:
                items.append({"title": t, "url": u})

        headlines = [x["title"] for x in items][:3]
        return {"kind": "news", "ok": bool(items), "items": items, "headlines": headlines, "links": links}

    except Exception:
        return {"kind": "news", "ok": False, "links": links}

CITY_COORDS = {
    "서울": (37.5665, 126.9780),
    "부산": (35.1796, 129.0756),
    "인천": (37.4563, 126.7052),
    "대구": (35.8714, 128.6014),
    "대전": (36.3504, 127.3845),
    "광주": (35.1595, 126.8526),
    "울산": (35.5384, 129.3114),
    "수원": (37.2636, 127.0286),
    "제주": (33.4996, 126.5312),
}

def fetch_weather_external(q: str) -> Dict[str, Any]:
    city = "서울"
    for c in CITY_COORDS.keys():
        if c in q:
            city = c
            break
    lat, lon = CITY_COORDS[city]
    links = [
        {"title": "기상청 날씨 예보", "url": "https://www.weather.go.kr/w/index.do"},
        {"title": f"네이버 '{city} 날씨'", "url": f"https://search.naver.com/search.naver?query={quote_plus(city+' 날씨')}"},
        {"title": f"구글 '{city} weather'", "url": f"https://www.google.com/search?q={quote_plus(city+' weather')}"},
    ]
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max", "timezone": "Asia/Seoul"}
        r = HTTP.get(url, params=params, timeout=EXTERNAL_TIMEOUT)
        if r.status_code != 200:
            return {"kind": "weather", "ok": False, "city": city, "links": links}
        data = r.json()
        daily = data.get("daily") or {}
        dates = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        pmax = daily.get("precipitation_probability_max") or []
        items = []
        for i in range(min(3, len(dates))):
            items.append({"date": dates[i], "tmax": tmax[i], "tmin": tmin[i], "precip": pmax[i]})
        return {"kind": "weather", "ok": bool(items), "city": city, "daily_3d": items, "links": links}
    except Exception:
        return {"kind": "weather", "ok": False, "city": city, "links": links}

def external_fetch(q: str) -> Dict[str, Any]:
    if WEATHER_PAT.search(q):
        return fetch_weather_external(q)
    if NEWS_PAT.search(q):
        return fetch_news_external(q)
    if PRICE_PAT.search(q):
        return fetch_price_external(q)
    return {"kind": "none", "ok": False, "links": []}

# ============================================================
# Server calls: preview + refund_preview
# ============================================================
def _http_get_json(url: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.get(url, params=params, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": None}


def _http_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.post(url, json=payload, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


def call_preview(entity: str, _id: int, user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/{entity}/{_id}", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_preview_me(user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/me", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_refund_preview(reservation_id: int, role: str) -> Dict[str, Any]:
    """
    Role-based refund preview:
    - ADMIN: /admin/refund/preview  (POST)
    - BUYER/SELLER: /v3_6/reservations/refund/preview (POST)  # buyer-safe
    """
    role_u = (role or "").upper().strip()

    # --- ADMIN: keep legacy admin endpoint ---
    if role_u == "ADMIN":
        fault_party = "BUYER"
        trigger = "BUYER_CANCEL"
        if role_u == "SELLER":
            fault_party = "SELLER"
            trigger = "SELLER_CANCEL"
        return _http_get_json(
            f"{YP_SERVER_URL}/admin/refund/preview",
            {"reservation_id": int(reservation_id), "fault_party": fault_party, "trigger": trigger},
            timeout=HTTP_TIMEOUT,
        )

    # --- BUYER/SELLER: v3_6 endpoint (most likely POST) ---
    # We intentionally do NOT send fault_party/trigger here unless your v3_6 API requires it.
    # If v3_6 requires extra fields, add them here.
    payload = {
        "reservation_id": int(reservation_id),
        "role": role_u,  # harmless if ignored, useful if v3_6 wants it
    }

    # use dedicated ask/refund timeout if you want (same idea as ask timeout)
    refund_timeout = float(os.environ.get("YP_REFUND_TIMEOUT") or 0) or max(2.0, float(HTTP_TIMEOUT) / 2.0)

    try:
        r = HTTP.post(f"{YP_SERVER_URL}/v3_6/reservations/refund/preview", json=payload, timeout=refund_timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


def call_refund_preview_v36(reservation_id: int, role: str) -> Dict[str, Any]:
    payload = {"reservation_id": int(reservation_id), "role": (role or "BUYER").upper()}
    # v3_6는 POST
    try:
        r = HTTP.post(f"{YP_SERVER_URL}/v3_6/reservations/refund/preview", json=payload, timeout=HTTP_TIMEOUT)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


def answer_from_refund_preview_v36(pre: Dict[str, Any]) -> str:
    if not isinstance(pre, dict):
        return "지금은 환불 프리뷰 응답을 해석할 수 없어요."

    st = int(pre.get("_http_status") or 0)
    if st >= 500 or pre.get("error") == "OFFLINE":
        return "예약 환불 프리뷰 조회가 지금 실패했어요. 잠시 후 다시 시도해 주세요."
    if st >= 300:
        detail = pre.get("detail") or pre.get("msg") or pre.get("error") or "요청이 처리되지 않았습니다."
        return f"예약 환불 프리뷰 조회가 지금 실패했어요: {detail}"

    ctx = pre.get("context") if isinstance(pre.get("context"), dict) else {}
    decision = pre.get("decision") if isinstance(pre.get("decision"), dict) else {}

    total = ctx.get("amount_total")
    goods = ctx.get("amount_goods")
    ship = ctx.get("amount_shipping")

    note = decision.get("note") or decision.get("reason") or decision.get("summary")

    if total is None:
        return "환불 프리뷰는 조회됐지만, 금액 계산 결과가 비어 있어요."

    msg = f"환불 프리뷰 기준 총 {int(total):,}원"
    if goods is not None or ship is not None:
        msg += f" (상품 {int(goods or 0):,}원 / 배송 {int(ship or 0):,}원)"
    msg += " 입니다."
    if note:
        msg += f"\n• {str(note).strip()}"
    return msg




# --- Ask(Brain) call ---
def call_pingpong_ask(
    *,
    screen: str,
    role: str,
    question: str,
    mode: str = "read_only",
    max_chat_messages: int = 10,
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Server brain endpoint: POST /v3_6/pingpong/ask
    - 항상 dict 반환 (+ _http_status 포함)
    - offline이면 {"error":"OFFLINE", ...}
    """
    payload = {
        "screen": (screen or "DEAL_ROOM"),
        "role": (role or "BUYER").upper(),
        "question": (question or "").strip(),
        "mode": (mode or "read_only"),
        "max_chat_messages": int(max_chat_messages or 10),
        "context": context or {},
    }

    # ✅ ask 전용 타임아웃: env 우선, 없으면 (HTTP_TIMEOUT/2) 폴백
    ask_timeout = float(os.environ.get("YP_ASK_TIMEOUT") or 0) or max(1.5, float(HTTP_TIMEOUT) / 2.0)

    try:
        r = HTTP.post(f"{YP_SERVER_URL}/v3_6/pingpong/ask", json=payload, timeout=ask_timeout)
        try:
            obj = r.json()
        except Exception:
            obj = {"detail": (r.text or "").strip()}
        if isinstance(obj, dict):
            obj["_http_status"] = r.status_code
            return obj
        return {"detail": str(obj), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}



def answer_from_refund_preview(pre: Dict[str, Any]) -> str:
    if not isinstance(pre, dict):
        return "지금은 환불 프리뷰 응답을 해석할 수 없어요."
    st = int(pre.get("_http_status") or 0)
    if st >= 500 or pre.get("error") == "OFFLINE":
        return "예약 환불 프리뷰 조회가 지금 실패했어요. 잠시 후 다시 시도해 주세요."
    if st >= 300:
        detail = pre.get("detail") or pre.get("msg") or pre.get("error") or "요청이 처리되지 않았습니다."
        return f"예약 환불 프리뷰 조회가 지금 실패했어요: {detail}"

    ctx = pre.get("ctx") if isinstance(pre.get("ctx"), dict) else {}
    meta = pre.get("meta") if isinstance(pre.get("meta"), dict) else {}
    decision = pre.get("decision") if isinstance(pre.get("decision"), dict) else {}

    total = meta.get("amount_total_refund") or ctx.get("amount_total")
    goods = meta.get("amount_goods_refund") or ctx.get("amount_goods")
    ship = meta.get("amount_shipping_refund") or ctx.get("amount_shipping")
    note = meta.get("decision_note") or decision.get("note")

    if total is None:
        return "환불 프리뷰는 조회됐지만, 금액 계산 결과가 비어 있어요."

    msg = f"예약 환불 프리뷰 기준으로 총 {int(total):,}원"
    if goods is not None or ship is not None:
        msg += f" (상품 {int(goods or 0):,}원 / 배송 {int(ship or 0):,}원)"
    msg += " 입니다."
    if note:
        msg += f" {str(note)}"
    return msg



def _http_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.post(url, json=payload, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


#--------------------------------
# 동일질문/동일id 조합일 경우, 이전 결과를 재활용
#--------------------------------
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

def cached_call(key: str, ttl: float, fn):
    now = now_ts()
    hit = _CACHE.get(key)
    if hit:
        ts, val = hit
        if now - ts <= ttl:
            return val
    val = fn()
    _CACHE[key] = (now, val)
    return val

# ============================================================
# Conversation state
# ============================================================
@dataclass
class ConversationState:
    role: str = "BUYER"
    user_id: int = 1
    user_name: Optional[str] = None

    pending_kind: Optional[str] = None   # reservation/offer/deal
    pending_template: Optional[str] = None

    last_ids: Dict[str, Optional[int]] = field(default_factory=lambda: {"deal_id": None, "offer_id": None, "reservation_id": None})
    last_mode: str = "chitchat"
    last_links: List[Dict[str, str]] = field(default_factory=list)

    last_ask_obj: Dict[str, Any] = field(default_factory=dict)
    last_ask_used_policies: List[Dict[str, Any]] = field(default_factory=list)
    last_ask_question: str = ""

    # ✅ last external context (for follow-up link requests)
    last_external_kind: str = ""  # "news" / "weather" / "price"
    last_external_query: str = ""  # normalized external query (for "출처" display)
    last_price_query: str = ""    # 마지막 실제 제품 검색어 (사이트명 아닌 것만, SITE_ONLY fallback용)
    last_news_items: List[Dict[str, str]] = field(default_factory=list)

    last_used_policies: List[Dict[str, Any]] = field(default_factory=list)
    last_ask_debug: Dict[str, Any] = field(default_factory=dict)
    last_answer_kind: str = ""
    last_server_refs: List[Dict[str, Any]] = field(default_factory=list)
    recent_intents: List[str] = field(default_factory=list)  # 최근 2턴 intent.kind 추적

    history: List[Dict[str, str]] = field(default_factory=list)

S = ConversationState()

def observe_user_query_intent(state: ConversationState, q: str) -> None:
    ql = (q or "").lower()
    if re.search(r"(환불|취소|refund|cancel)", ql):
        state.pending_kind = "reservation"
        state.pending_template = "예약#{id} 환불 가능 여부와 환불 금액 알려줘"
        return
    if re.search(r"(오퍼|offer)", ql):
        state.pending_kind = "offer"
        state.pending_template = "오퍼#{id} 상태/마감/조건 알려줘"
        return
    if re.search(r"(딜방|딜|deal)", ql):
        state.pending_kind = "deal"
        state.pending_template = "딜#{id} 상태/마감 알려줘"
        return

def normalize_user_input(state: ConversationState, raw: str) -> str:
    n = parse_id_only(raw)
    if n is None:
        return raw
    if state.pending_kind and state.pending_template:
        return state.pending_template.format(id=n)
    return raw

def update_last_ids_from_text(state: ConversationState, q: str) -> None:
    ids = extract_ids_from_text(q)
    for k in ("deal_id", "offer_id", "reservation_id"):
        if ids.get(k) is not None:
            state.last_ids[k] = ids[k]

def likely_followup_is_yeokping(prev_mode: str, raw: str) -> bool:
    if prev_mode != "yeokping":
        return False
    if parse_id_only(raw) is not None:
        return True
    return bool(re.search(r"(그럼|그거|왜|맞지|아니|다시|확인)", raw))

def _merge_links(a: List[Dict[str, str]], b: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for src in (a or []) + (b or []):
        if not isinstance(src, dict):
            continue
        url = (src.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": (src.get("title") or url).strip(), "url": url})
    return out

# ============================================================
# OpenAI only for smalltalk/explain (no internal facts)
# ============================================================
def instructions_for(category: str, user_name: Optional[str], role: str = "") -> str:
    name = f"{user_name}님" if user_name else "고객님"
    role_u = (role or "").upper()
    role_label = {"BUYER": "구매자", "SELLER": "판매자", "ADMIN": "관리자", "ACTUATOR": "액추에이터"}.get(role_u, "")

    # 역할별 톤 힌트
    tone_map = {
        "BUYER": "친근하고 쉬운 말투로 설명해. 바로가기 링크를 포함해.",
        "SELLER": "비즈니스 톤. 정산/수수료/배송 중심으로 답변해.",
        "ADMIN": "전문적 톤. 시스템 관리 관점에서 답변해. 관리자 전용 기능(마이너리티 리포트, 환불 시뮬레이터, 이상 감지, 정책 파라미터 등)도 안내 가능.",
        "ACTUATOR": "판매자 지원 관점에서 답변해.",
    }
    tone = tone_map.get(role_u, "친근한 톤으로 답변해.")

    if category == "free_chat":
        return f"""
너는 역핑(역경매 공동구매 플랫폼)의 AI 어시스턴트 '핑퐁이'야.
현재 대화 상대: {role_label or '사용자'}
호칭: "{name}"

지금은 역핑과 직접 관련 없는 일반 대화야.
밝고 친근하게 자유롭게 답변해줘.
답변 마지막에 자연스럽게 "혹시 역핑에서 궁금한 것도 있으면 물어봐 주세요! 😊" 를 붙여줘.
한국어로 답변. 3~5문장으로 간결하게.

[SAFETY RULES — 반드시 준수]
1. 정치/종교/차별/혐오 관련 의견을 절대 제시하지 마. 중립을 유지해.
2. 의료/법률/투자 조언을 하지 마. "전문가와 상담하세요"로 안내해.
3. 불법 행위를 조장하거나 방법을 알려주지 마.
4. 욕설/비속어에 감정적으로 반응하지 마. 차분하게 대응해.
5. 개인정보(주민번호/계좌번호/비밀번호 등)를 요청하거나 노출하지 마.
6. 자해/자살 관련 발언에는 반드시 전문 상담 기관(1393, 1577-0199)을 안내해.
""".strip()

    if category == "smalltalk":
        return f"""
너는 역핑(역경매 공동구매 플랫폼)의 AI 어시스턴트 '핑퐁이'야.
현재 대화 상대: {role_label or '사용자'}
호칭: "{name}"

[Rules]
1) 역핑/SSOT/서버/preview/DB/정책/내부시스템 같은 단어를 절대 꺼내지 마.
2) "자료가 없어서", "확인할 수 없어서" 같은 메타 발화 금지.
3) "제가 지금 조회해올게요/잠깐만 기다려" 같은 약속은 하지 마. 필요하면 링크/방법을 제시해.
4) 밝고 친근하게 자유롭게 답변해줘. 답변 마지막에 "혹시 역핑에서 궁금한 것도 있으면 물어봐 주세요! 😊" 를 붙여줘.
5) 1~4문장. {tone}
""".strip()
    if category == "explain":
        return f"""
너는 역핑(역경매 공동구매 플랫폼)의 AI 어시스턴트 '핑퐁이'야.
현재 대화 상대: {role_label or '사용자'}
호칭: "{name}"

=== 답변 규칙 (반드시 준수) ===

1. 지식베이스(DOCS)에 있는 내용만 답변하세요.
   - DOCS에 없는 내용은 절대 추측하거나 지어내지 마세요.
   - 모르는 것은 "해당 내용은 제가 안내드리기 어렵습니다." 라고 답하세요.
   - 특히 영화, 뉴스, 일반 상식 등 역핑과 관련 없는 답변은 절대 하지 마세요.
   - "마이너리티 리포트"는 영화가 아니라 역핑의 사용자 행동 분석 대시보드입니다. DOCS에 있을 때만 설명하세요.

2. 다른 역할의 기능에 대한 질문:
   - 구매자 전용 기능(사진 딜 생성, 음성 검색, 가격 챌린지 등)을 판매자/액추에이터가 물으면: "이 기능은 구매자 전용 기능입니다."
   - 판매자 전용 기능(오퍼 제출, 배송 처리, 정산 관리 등)을 구매자가 물으면: "이 기능은 판매자 전용 기능입니다."
   - 관리자 전용 기능(마이너리티 리포트, 환불 시뮬레이터, 이상 감지 등)을 일반 유저가 물으면: "해당 내용은 안내드리기 어렵습니다."
   - 중요: "제공되지 않는 기능입니다", "없는 기능입니다" 라고 하지 마세요. 역핑에 존재하는 기능이지만 현재 역할에서 사용할 수 없는 것일 수 있습니다.

3. 역할별 톤: {tone}

4. 답변 포맷:
   - 관련 페이지가 있으면 경로를 포함하세요: /deals, /my-orders, /seller/offers 등
   - 답변은 간결하게 3~5문장 이내.
   - 숫자/정책값은 DOCS 기준으로 정확하게.

[필수 사실 — DOCS 유무와 관계없이 반드시 준수]
- PG 수수료(약 3.3%)는 역핑 플랫폼이 전액 흡수. 구매자가 PG 수수료를 부담한다고 절대 답하지 마세요.
- 감가(사용 차감)는 일수 기준이 아닙니다. 반품 상품의 실제 상태(사용 흔적, 손상, 포장)를 판매자가 검수하여 결정합니다. "일수 기준"이라고 절대 답하지 마세요.
- 포인트 적립은 결제금액의 1%, 환불 시 적립 포인트를 환불 비율만큼 비례 차감 (고정 -20P 아님).
- Clawback은 이미 지급 완료(PAID)된 정산을 다음 정산에서 자동 상계하는 환수 절차.
- AI 중재는 구조화된 해결안(환불유형, 금액근거, 법적근거, 넛지)을 제시, 강제 아닌 합의 기반.
""".strip()
    return f"한국어로 2~6문장. 호칭은 {name}. 역핑 플랫폼 관련 질문만 답변해."


def openai_generate(client: OpenAI, category: str, question: str, docs: str, history: List[Dict[str, str]], user_name: Optional[str], role: str = "") -> str:
    hist = history[-KEEP_TURNS:]
    hist_txt = ""
    if hist:
        lines = []
        for t in hist:
            u = (t.get("user") or "").strip()
            a = (t.get("bot") or "").strip()
            if u:
                lines.append(f"사용자: {u}")
            if a:
                lines.append(f"핑퐁이: {a}")
        hist_txt = "\n".join(lines)

    # DOCS가 비어 있으면 일반 지식으로 답변 생성 방지 (explain 카테고리만)
    no_docs_guard = ""
    if not docs and category == "explain":
        no_docs_guard = (
            "\n\n[중요] DOCS가 비어 있습니다. "
            "역핑 플랫폼과 관련 없는 일반 상식/외부 정보로 답변하지 마세요. "
            "\"해당 내용은 제가 안내드리기 어렵습니다. 딜, 오퍼, 배송, 환불 등 역핑 관련 질문을 해주세요!\" 라고 답하세요."
        )

    prompt = f"""
[최근 대화]
{hist_txt if hist_txt else "(없음)"}

[질문]
{question}

[DOCS]
{docs if docs else "(없음)"}{no_docs_guard}
""".strip()

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": instructions_for(category, user_name, role)},
            {"role": "user", "content": prompt},
        ],
        max_tokens=450,
        temperature=0.3,
        timeout=30,
    )
    return (resp.choices[0].message.content or "").strip()

def _fmt_kst_min(dt: datetime) -> str:
    # YYYY-MM-DD HH:MM (KST)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")

def _parse_dt_any(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        # epoch seconds
        try:
            return datetime.fromtimestamp(float(v), tz=KST)
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # tolerate "Z"
        s = s.replace("Z", "+00:00")
        # tolerate space
        s = s.replace(" ", "T") if "T" not in s and ":" in s else s
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None

def _find_created_at(obj: Any) -> Optional[datetime]:
    """Try to find created_at in nested dicts."""
    if isinstance(obj, dict):
        for k in ("created_at", "createdAt", "created_time", "createdTime", "created"):
            if k in obj:
                dt = _parse_dt_any(obj.get(k))
                if dt:
                    return dt
        # search shallowly in common nests
        for k in ("pack", "ctx", "meta", "reservation", "deal", "offer", "data"):
            dt = _find_created_at(obj.get(k))
            if dt:
                return dt
    elif isinstance(obj, list):
        for it in obj[:5]:
            dt = _find_created_at(it)
            if dt:
                return dt
    return None

def deeplink_for(kind: str, _id: int, sub: str = "") -> str:
    # 앱 전용 딥링크 (웹 없음)
    if kind == "reservation":
        base = f"yeokping://preview/reservation/{_id}"
        return base + (f"/{sub}" if sub else "")
    if kind == "offer":
        return f"yeokping://preview/offer/{_id}"
    if kind == "dealroom":
        return f"yeokping://preview/dealroom/{_id}"
    if kind == "me":
        return f"yeokping://preview/me/{_id}"
    return f"yeokping://preview/me/{S.user_id}"

def header_with_created(kind_kr: str, _id: int, created_at: Optional[datetime]) -> str:
    if created_at:
        return f"{kind_kr} #{_id} · 생성 {_fmt_kst_min(created_at)} (KST)"
    return f"{kind_kr} #{_id} · 생성시각 확인 필요"

def render_button(label: str, link: str) -> str:
    # CLI에서는 버튼을 텍스트로 표현 (앱 UI에서는 실제 버튼으로 매핑)
    return f"[{label}]({link})"


def finalize(answer: str, evidence: str) -> str:
    a = (answer or "").strip()
    a = re.sub(r"(?:\n*\[근거:[^\]]*\]\s*)+$", "", a, flags=re.IGNORECASE).strip()
    return a + f"\n[근거: {evidence}]"


def _dig(obj: Any, keys: List[str]) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur

def _first_str(*vals: Any) -> Optional[str]:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None

def _first_int(*vals: Any) -> Optional[int]:
    for v in vals:
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return None

def _topic_for_reservation(q: str) -> str:
    # refund / payment / shipping / general
    if re.search(r"(환불|취소|refund|cancel|쿨링|cooling|반품|교환)", q, re.IGNORECASE):
        return "refund"
    if re.search(r"(결제|영수증|결제창|payment|타임아웃|timeout|실패|승인|카드)", q, re.IGNORECASE):
        return "payment"
    if re.search(r"(배송|송장|택배|tracking|shipment|shipping|도착|출고|지연)", q, re.IGNORECASE):
        return "shipping"
    return "reservation"

def _summarize_reservation_payment(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보(가능하면): 상태, 금액, 제한시간/메모
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    # 흔한 키 후보들
    status = _first_str(
        _dig(pack, ["reservation", "status"]),
        _dig(pack, ["status"]),
        _dig(pre, ["ctx", "status"]),
    )
    amount = _first_int(
        _dig(pack, ["reservation", "amount_total"]),
        _dig(pack, ["amount_total"]),
        _dig(pre, ["ctx", "amount_total"]),
    )
    timeout_min = _first_int(
        _dig(pack, ["reservation", "payment_timeout_minutes"]),
        _dig(pre, ["ctx", "payment_timeout_minutes"]),
    )
    lines: List[str] = []
    if status:
        lines.append(f"• 결제/예약 상태: {status}")
    if amount is not None:
        lines.append(f"• 결제 금액: {amount:,}원")
    if timeout_min is not None:
        lines.append(f"• 결제 제한시간: {timeout_min}분")
    return lines[:3]

def _summarize_reservation_shipping(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 배송상태, 택배사/송장, 최근 업데이트
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    ship_status = _first_str(
        _dig(pack, ["reservation", "shipping_status"]),
        _dig(pack, ["shipping", "status"]),
        _dig(pre, ["ctx", "shipping_status"]),
    )
    carrier = _first_str(
        _dig(pack, ["shipping", "carrier"]),
        _dig(pack, ["reservation", "shipping_carrier"]),
    )
    tracking = _first_str(
        _dig(pack, ["shipping", "tracking_no"]),
        _dig(pack, ["reservation", "tracking_no"]),
    )
    updated = _first_str(
        _dig(pack, ["shipping", "updated_at"]),
        _dig(pack, ["reservation", "shipping_updated_at"]),
    )
    lines: List[str] = []
    if ship_status:
        lines.append(f"• 배송 상태: {ship_status}")
    if carrier or tracking:
        lines.append(f"• 송장: {carrier or '택배'} {tracking or ''}".strip())
    if updated:
        lines.append(f"• 최근 업데이트: {updated}")
    return lines[:3]

def _summarize_offer(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 가격/조건/마감
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    price = _first_int(_dig(pack, ["offer", "price"]), _dig(pack, ["price"]))
    ship = _first_str(_dig(pack, ["offer", "shipping"]), _dig(pack, ["shipping"]))
    deadline = _first_str(_dig(pack, ["offer", "deadline_at"]), _dig(pack, ["deadline_at"]))
    lines: List[str] = []
    if price is not None:
        lines.append(f"• 제안가: {price:,}원")
    if ship:
        lines.append(f"• 배송: {ship}")
    if deadline:
        lines.append(f"• 마감: {deadline}")
    return lines[:3]

def _summarize_dealroom(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 모집현황/마감/타겟 등(가능한 것만)
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    cur = _first_int(_dig(pack, ["deal", "buyer_count"]), _dig(pack, ["buyer_count"]))
    target = _first_int(_dig(pack, ["deal", "target_buyer_count"]), _dig(pack, ["target_buyer_count"]))
    deadline = _first_str(_dig(pack, ["deal", "deadline_at"]), _dig(pack, ["deadline_at"]))
    lines: List[str] = []
    if cur is not None and target is not None:
        lines.append(f"• 참여 현황: {cur}/{target}")
    elif cur is not None:
        lines.append(f"• 참여자 수: {cur}")
    if deadline:
        lines.append(f"• 마감: {deadline}")
    return lines[:3]



# ============================================================
# External query normalization (for links/search)
#   - Remove chatty filler ("아... 오케이", "알려줘" ...)
#   - Keep short, keyword-like query
# ============================================================
STOPWORDS_EXTERNAL_QUERY = {
    # filler / interjection
    "아", "아아", "음", "어", "오케이", "ok", "ㅇㅋ", "ㅎㅎ", "ㅋㅋ",
    # request verbs
    "알려줘", "알려", "말해줘", "말해", "찾아줘", "찾아", "보여줘", "보여",
    "검색", "검색해", "검색해줘", "부탁", "해줘", "해줄",
    # time/quantity fluff
    "오늘", "지금", "방금", "하나만", "한개만",
    # common wrappers
    "관련", "관련한", "헤드라인",
    # common intent words that should not become query
    "뉴스", "기사", "헤드라인", "해드라인", "url", "링크",
    "뽑아줘", "뽑아", "줘", "줄래", "줄래요", "줘요",
    "하나", "하나만", "한", "개", "한개", "한개만",
    "관련", "관련한",
}

def normalize_external_query(text: str, *, max_len: int = 80) -> str:
    s = (text or "").strip()
    # trailing punctuation
    s = re.sub(r"[?？!！.。]+$", "", s)
    s = re.sub(r"\s+", " ", s)

    toks = re.findall(r"[가-힣A-Za-z0-9]+", s)
    kept = []
    for t in toks:
        tl = t.lower()
        if tl in STOPWORDS_EXTERNAL_QUERY:
            continue
        kept.append(t)

    out = " ".join(kept).strip()
    if len(out) < 2:
        out = s

    if len(out) > max_len:
        out = out[:max_len].rstrip()
    return out


_EXTERNAL_DISCLAIMER = "\n\n참고: 저는 역핑 플랫폼 안내 전문이에요! 딜, 오퍼, 배송, 환불 등에 대해 더 물어봐 주세요 😊"

def _finalize_external(msg: str) -> str:
    """External 결과에 역핑 안내 면책 추가 + finalize."""
    return finalize(msg + _EXTERNAL_DISCLAIMER, "external")

def handle_external(raw: str, q: str) -> Optional[str]:
    """
    External handler SSOT:
    - External is triggered ONLY when:
        (EXTERNAL_ASK_PAT matches AND topic matches) OR topic matches strongly
    - Prevent smalltalk from leaking into external.
    - Always refresh S.last_links for this request (or clear).
    - Support follow-up: "URL/링크" after news headlines.
    """

    # 0) follow-up: previously fetched news -> user asks url/link
    if re.search(r"(url|링크|주소)", raw, re.IGNORECASE) and S.last_external_kind == "news" and S.last_news_items:
        it = S.last_news_items[0]
        msg = f"가장 위 제목 링크예요: {it.get('url')}"
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return _finalize_external(msg)

    # ✅ Finance fast-path: FINANCE_PAT이 매칭되면 쇼핑 가격 핸들러보다 먼저 처리.
    # 환율/주가 쿼리가 PRICE_PAT("얼마")에도 걸리기 때문에 반드시 여기서 선점해야 함.
    if FINANCE_PAT.search(q):
        eq = q.strip() or "환율"
        links = [
            {"title": "네이버 금융", "url": "https://finance.naver.com/"},
            {"title": "다음 금융", "url": "https://finance.daum.net/"},
            {"title": "한국거래소(KRX)", "url": "https://global.krx.co.kr/"},
            {"title": "한국은행 환율/통계(ECOS)", "url": "https://ecos.bok.or.kr/"},
        ]
        msg = (
            "실시간 환율·주가 숫자를 제가 직접 확정해 드리기 어려워요. "
            "뇌피셜 수치를 드리는 것보다 아래 공신력 있는 곳에서 바로 확인하시는 게 정확합니다:\n"
            + "\n".join([f"- {x['title']}: {x['url']}" for x in links])
        )
        S.last_links = links
        S.last_external_kind = "finance"
        S.last_external_query = eq
        return _finalize_external(msg)

    # kind는 무조건 여기서 먼저 초기화
    kind: str = ""

    # 1) detect topics by raw(q)
    wants_weather = bool(WEATHER_PAT.search(q))
    wants_news = bool(NEWS_PAT.search(q))
    wants_price = bool(PRICE_PAT.search(q))

    has_topic = bool(wants_weather or wants_news or wants_price)
    has_intent = bool(EXTERNAL_ASK_PAT.search(q))

    # 2) strict gate: to avoid "너는 안 추워?" leaking into external
    #    - must have topic AND intent
    if not (has_topic and has_intent):
        return None

    # 3) choose kind by topic
    if wants_weather:
        kind = "weather"
    elif wants_news:
        kind = "news"
    else:
        kind = "price"

    # 4) normalize query for search/links
    eq = normalize_external_query(q)

    # 4-a) eq가 쇼핑 사이트명뿐이면 마지막 제품 검색어로 대체 (price 한정)
    if kind == "price" and _SITE_ONLY_PAT.match(eq) and S.last_price_query and len(S.last_price_query) > 3:
        eq = S.last_price_query

    # 5) save SSOT for "출처"
    S.last_external_kind = kind
    S.last_external_query = eq
    if kind == "price" and not _SITE_ONLY_PAT.match(eq) and len(eq) > 3:
        S.last_price_query = eq

    # 6) fetch by kind
    if kind == "weather":
        ext = fetch_weather_external(eq)
    elif kind == "news":
        ext = fetch_news_external(eq)
    else:
        ext = fetch_price_external(eq)

    # 7) build links (prefer ext.links, fallback by kind)
    links = ext.get("links") if isinstance(ext, dict) else []
    if isinstance(links, list) and links:
        S.last_links = _merge_links([], links)
    else:
        if kind == "news":
            S.last_links = _merge_links([], [
                {"title": f"구글뉴스 '{eq}'", "url": f"https://news.google.com/search?q={quote_plus(eq)}&hl=ko&gl=KR&ceid=KR:ko"},
                {"title": f"네이버뉴스 '{eq}'", "url": f"https://search.naver.com/search.naver?where=news&query={quote_plus(eq)}"},
            ])
        elif kind == "weather":
            S.last_links = _merge_links([], [
                {"title": "기상청 날씨 예보", "url": "https://www.weather.go.kr/w/index.do"},
                {"title": f"네이버 '{eq} 날씨'", "url": f"https://search.naver.com/search.naver?query={quote_plus(eq+' 날씨')}"},
                {"title": f"구글 '{eq} weather'", "url": f"https://www.google.com/search?q={quote_plus(eq+' weather')}"},
            ])
        else:
            S.last_links = _merge_links([], [
                {"title": f"네이버쇼핑 '{eq}'", "url": f"https://search.shopping.naver.com/search/all?query={quote_plus(eq)}"},
                {"title": f"다나와 '{eq}'", "url": f"https://search.danawa.com/dsearch.php?k1={quote_plus(eq)}"},
                {"title": f"쿠팡 '{eq}'", "url": f"https://www.coupang.com/np/search?q={quote_plus(eq)}"},
            ])

    # 8) if fetch failed, still provide links
    if not isinstance(ext, dict) or not ext.get("ok"):
        msg = "지금은 실시간 조회가 불안정합니다."
        if S.last_links:
            msg += "\n" + "\n".join([f"- {x['title']}: {x['url']}" for x in S.last_links[:2] if x.get("url")])
        else:
            msg += " 필요하시면 '출처'라고 입력해 주세요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return _finalize_external(msg)

    # 9) success rendering
    if kind == "weather":
        city = ext.get("city") or "서울"
        items = ext.get("daily_3d") or []
        if items:
            d0 = items[0]
            msg = f"{city} 기준 {d0.get('date')} 예상 최고 {d0.get('tmax')}° / 최저 {d0.get('tmin')}°, 강수확률 {d0.get('precip')}% 입니다."
        else:
            msg = "날씨 정보를 가져오지 못했어요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return _finalize_external(msg)

    if kind == "news":
        # store items for follow-up URL requests
        S.last_news_items = ext.get("items") or []
        heads = ext.get("headlines") or []
        if heads:
            msg = "오늘 뉴스로는 이런 제목들이 보여요: " + " / ".join(heads[:3])
        else:
            msg = "뉴스 제목을 가져오지 못했어요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return _finalize_external(msg)

    # price — 링크는 eq로 항상 직접 생성 (네이버쇼핑 봇차단 제외)
    # (eq fallback은 fetch 직전 4-a 단계에서 이미 처리됨)
    _eq_enc = quote_plus(eq)
    _price_links_text = (
        f"- 다나와: https://search.danawa.com/dsearch.php?k1={_eq_enc}\n"
        f"- 에누리: https://www.enuri.com/search.jsp?keyword={_eq_enc}\n"
        f"- 쿠팡: https://www.coupang.com/np/search?q={_eq_enc}"
    )

    if ext.get("links_only") or not ext.get("ok"):
        # 1순위: 네이버 쇼핑 API로 실제 가격 조회
        _naver_msg = ""
        _naver_items = fetch_naver_shopping(eq)
        if _naver_items:
            _priced = [it for it in _naver_items if it.get("lprice")]
            if _priced:
                _priced.sort(key=lambda x: int(x["lprice"]))
                _cheapest = _priced[0]
                _lp = int(_cheapest["lprice"])
                _title = re.sub(r"<[^>]+>", "", _cheapest.get("title", eq))
                _price_str = f"{_lp:,}원 (약 {_lp // 10000}만원대)" if _lp >= 10000 else f"{_lp:,}원"
                _hp = int(_cheapest.get("hprice", "0") or "0")
                _range_str = f"\n  가격 범위: {_lp:,}원 ~ {_hp:,}원" if _hp > _lp else ""
                _mall = _cheapest.get("mallName", "")
                _mall_str = f" ({_mall})" if _mall else ""
                _naver_msg = (
                    f"🛒 {_title}\n"
                    f"  최저가: {_price_str}{_mall_str}{_range_str}\n"
                    f"  (네이버쇼핑 기준, 실제 가격과 다를 수 있습니다)\n"
                )

        if _naver_msg:
            msg = f"{_naver_msg}\n자세한 비교는 아래에서 확인해 보세요:\n{_price_links_text}"
        else:
            msg = f"가격 정보를 직접 조회하지 못했어요. 아래에서 확인해 보세요:\n{_price_links_text}"
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return _finalize_external(msg)

    low = ext.get("low_estimate")
    rg = ext.get("range") or {}
    p10, p50, p90 = rg.get("p10"), rg.get("p50"), rg.get("p90")
    msg = (
        f"최저가 추정 {int(low):,}원 / 대략 {int(p10):,}~{int(p90):,}원 범위"
        f" (중앙값 {int(p50):,}원) 정도로 보여요. (실시간 변동 가능)\n"
        f"{_price_links_text}"
    )
    S.last_mode = "external"
    S.history.append({"user": q, "bot": msg})
    S.history[:] = S.history[-KEEP_TURNS:]
    return _finalize_external(msg)



def infer_screen_from_state(state: "ConversationState") -> str:
    # 최소 침습: ID가 있으면 그 엔티티 중심, 없으면 DEAL_ROOM
    if state.last_ids.get("reservation_id"):
        return "RESERVATION"
    if state.last_ids.get("offer_id"):
        return "OFFER"
    if state.last_ids.get("deal_id"):
        return "DEAL_ROOM"
    return "DEAL_ROOM"


def render_ask_answer_for_user(obj: Dict[str, Any]) -> str:
    if not isinstance(obj, dict):
        return "지금은 답변을 만들지 못했어요."

    st = int(obj.get("_http_status") or 0)
    if st >= 500 or obj.get("error") == "OFFLINE":
        return "지금 서버 답변이 불안정해요. 잠시 후 다시 물어봐 주세요."
    if st >= 300:
        detail = obj.get("detail") or obj.get("error") or "요청이 처리되지 않았습니다."
        return f"지금은 답변을 가져오지 못했어요: {detail}"

    answer = (obj.get("answer") or "").strip()
    if not answer:
        return "지금은 답변이 비어 있어요. 질문을 조금만 더 구체적으로 말해줄래요?"

    # (선택) 근거 1~3개만 가볍게
    used = obj.get("used_policies") or []
    if isinstance(used, list) and used:
        refs: List[str] = []
        for p in used[:3]:
            if isinstance(p, dict):
                t = (p.get("title") or p.get("policy_key") or "").strip()
                if t:
                    refs.append(t)
        if refs:
            answer += "\n\n(근거: " + " / ".join(refs[:3]) + ")"

    return answer


# ============================================================
# Core step (exported for autotest_v2)
# ============================================================
def step_once(raw: str, client: OpenAI) -> str:

    global S

    raw = (raw or "").strip()
    if not raw:
        return ""

    # (안전) KB/SSOT 로딩은 한번만
    load_kb()
    load_time_values_from_defaults()

    # ------------------------------------------------------------
    # 0) "출처/근거" command
    #   - 1순위: last_used_policies (ask가 쓴 정책)
    #   - 2순위: last_links (external: 날씨/뉴스/가격)
    # ------------------------------------------------------------
    # "출처/근거" command (문장형도 커버)
    # - 예: "근거", "근거는?", "근거 보여줘", "출처 링크", "source?", "refs"
    _cmd = (raw or "").strip().lower()
    _cmd_norm = re.sub(r"\s+", " ", _cmd)

    # 끝의 물음표/느낌표/마침표 제거한 버전도 같이 본다
    _cmd_trim = re.sub(r"[.?!]+$", "", _cmd_norm).strip()

    def _is_refs_command(text: str) -> bool:
        if not text:
            return False
        # 아주 짧은 “명령형”만 커맨드로 취급 (일반 문장 오탐 방지)
        # 예: "근거는?" -> trim 후 "근거는" 로 매칭
        return bool(re.fullmatch(r"(출처|링크|source|refs|references|근거|근거도|근거는|근거좀|근거요|근거\s*보여줘|출처\s*보여줘|링크\s*보여줘)", text))

    if _is_refs_command(_cmd_trim):
        # ✅ 0) 마지막 답변 타입 기준으로 우선순위 결정
        # - server 답변 직후: last_server_refs 먼저
        # - ask 답변 직후: last_used_policies 먼저
        last_kind = (getattr(S, "last_answer_kind", None) or "").strip().lower()

        def _render_used_policies() -> Optional[str]:
            if not getattr(S, "last_used_policies", None):
                return None
            ups = S.last_used_policies or []
            if not ups:
                return None
            lines = ["요청하신 근거(사용한 정책)입니다."]
            for p in ups[:10]:
                if isinstance(p, dict):
                    k = (p.get("policy_key") or "").strip()
                    t = (p.get("title") or "").strip()
                    if k and t:
                        lines.append(f"- {k} : {t}")
                    elif t:
                        lines.append(f"- {t}")
                    elif k:
                        lines.append(f"- {k}")
            return "\n".join(lines)

        def _render_server_refs() -> Optional[str]:
            if not getattr(S, "last_server_refs", None):
                return None
            refs = S.last_server_refs or []
            if not refs:
                return None
            lines = ["요청하신 근거(최근 서버 조회/프리뷰)입니다."]
            for r in refs[:10]:
                if isinstance(r, dict):
                    k = (r.get("policy_key") or "").strip()
                    t = (r.get("title") or "").strip()
                    if k and t:
                        lines.append(f"- {k} : {t}")
                    elif t:
                        lines.append(f"- {t}")
                    elif k:
                        lines.append(f"- {k}")
            return "\n".join(lines)

        # ✅ 1) last_answer_kind가 server면 server refs 먼저
        if last_kind == "server":
            txt = _render_server_refs()
            if txt:
                return finalize(txt, "server")
            txt = _render_used_policies()
            if txt:
                return finalize(txt, "server")

        # ✅ 2) last_answer_kind가 ask면 used_policies 먼저
        if last_kind == "ask":
            txt = _render_used_policies()
            if txt:
                return finalize(txt, "server")
            txt = _render_server_refs()
            if txt:
                return finalize(txt, "server")

        # ✅ 3) 타입이 없으면(초기/예외) 기존 우선순위 유지: ask → server
        txt = _render_used_policies()
        if txt:
            return finalize(txt, "server")

        txt = _render_server_refs()
        if txt:
            return finalize(txt, "server")

        # 2) 없으면 external 링크(날씨/뉴스/가격) 출처 (✅ 너 기존 코드 그대로)
        if getattr(S, "last_links", None) and S.last_links:
            lines = ["요청하신 출처 링크입니다."]
            if getattr(S, "last_external_query", None):
                if S.last_external_query:
                    lines.append(f"(검색어: {S.last_external_query})")
            for it in S.last_links[:10]:
                if isinstance(it, dict):
                    title = (it.get("title") or "").strip()
                    url = (it.get("url") or "").strip()
                    if title or url:
                        lines.append(f"- {title} : {url}")
            return finalize("\n".join(lines), "external")

        return finalize("(지금 보여드릴 근거/출처가 없어요.)", "없음")


    # ------------------------------------------------------------
    # 1) observe + normalize + id-tracking
    # ------------------------------------------------------------
    prev_mode = S.last_mode
    observe_user_query_intent(S, raw)

    q = normalize_user_input(S, raw)
    update_last_ids_from_text(S, q)

    # ✅ 회귀 방지: 일반 대화로 넘어가면 pending을 해제(환불 고착 방지)
    #   - 단, 숫자만 던지는 follow-up(id-only)은 pending 유지
    if not is_yeokping_related(q) and not EXTERNAL_ASK_PAT.search(q):
        if parse_id_only(raw) is None:
            S.pending_kind = None
            S.pending_template = None

    # ------------------------------------------------------------
    # 2) ID-first SSOT (instance) — if ID is present, go server + button UX
    #   - reservation: refund/payment/shipping/general
    #   - offer: offer preview
    #   - deal: dealroom preview
    # ------------------------------------------------------------
    ids_now = extract_ids_from_text(q)
    _dbg(
        "gate_idfirst",
        {"raw": raw, "q": q, "ids_now": ids_now, "pending": S.pending_kind, "last_ids": S.last_ids},
    )

    rid_now = ids_now.get("reservation_id")
    oid_now = ids_now.get("offer_id")
    did_now = ids_now.get("deal_id")

    # --- reservation id path ---
    if rid_now:
        rid_int = int(rid_now)
        topic = _topic_for_reservation(q)

        # created_at (best effort)
        created_at = None
        pre_res: Optional[Dict[str, Any]] = None
        try:
            pre_res = call_preview("reservation", rid_int, S.user_id, S.role)
            created_at = _find_created_at(pre_res)
        except Exception:
            pre_res = None
            created_at = None

        head = header_with_created("예약", rid_int, created_at)

        # (1) refund -> refund preview
        if topic == "refund":
            # ✅ BUYER/SELLER 는 v3_6 refund preview 응답구조(context/decision) 우선
            use_v36 = (S.role or "").upper() in ("BUYER", "SELLER")

            if use_v36:
                pre = call_refund_preview_v36(rid_int, S.role)  # <-- 너가 추가한 함수
                summary = answer_from_refund_preview_v36(pre)   # <-- 너가 추가한 함수
            else:
                pre = call_refund_preview(rid_int, S.role)
                summary = answer_from_refund_preview(pre)

            link = deeplink_for("reservation", rid_int, "refund")
            btn = render_button("환불 프리뷰 열기", link)

            st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
            offline = isinstance(pre, dict) and pre.get("error") == "OFFLINE"
            if offline or st >= 300 or not isinstance(pre, dict):
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 환불 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            # ✅ 성공: 요약 + 버튼
            msg = f"{head}\n\n{summary}\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]

            # ✅ "근거" 커맨드용: 방금 답변은 server 기반
            S.last_answer_kind = "server"
            S.last_server_refs = [
                {"policy_key": "server:/v3_6/reservations/refund/preview", "title": f"환불 프리뷰(실시간) — reservation_id={rid_int}"},
                {"policy_key": f"deeplink:yeokping://preview/reservation/{rid_int}/refund", "title": "환불 프리뷰 화면 딥링크"},
            ]

            return finalize(msg, "server")

        # (2) payment -> reservation preview + payment screen
        if topic == "payment":
            link = deeplink_for("reservation", rid_int, "payment")
            btn = render_button("결제 프리뷰 열기", link)

            if not isinstance(pre_res, dict) or int(pre_res.get("_http_status") or 0) >= 300:
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 결제 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            lines = _summarize_reservation_payment(pre_res) or ["• 결제 요약 정보를 만들지 못했어요."]
            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (3) shipping -> reservation preview + shipping screen
        if topic == "shipping":
            link = deeplink_for("reservation", rid_int, "shipping")
            btn = render_button("배송 프리뷰 열기", link)

            if not isinstance(pre_res, dict) or int(pre_res.get("_http_status") or 0) >= 300:
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 배송 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            lines = _summarize_reservation_shipping(pre_res) or ["• 배송 요약 정보를 만들지 못했어요."]
            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (4) general reservation preview screen
        link = deeplink_for("reservation", rid_int, "")
        btn = render_button("예약 프리뷰 열기", link)

        if not isinstance(pre_res, dict) or int(pre_res.get("_http_status") or 0) >= 300:
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 예약 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        pack = pre_res.get("pack") if isinstance(pre_res.get("pack"), dict) else {}
        status = _first_str(
            _dig(pack, ["reservation", "status"]),
            _dig(pack, ["status"]),
            _dig(pre_res, ["ctx", "status"]),
        )
        amount = _first_int(
            _dig(pack, ["reservation", "amount_total"]),
            _dig(pack, ["amount_total"]),
            _dig(pre_res, ["ctx", "amount_total"]),
        )

        lines: List[str] = []
        if status:
            lines.append(f"• 예약 상태: {status}")
        if amount is not None:
            lines.append(f"• 금액: {amount:,}원")
        if not lines:
            lines = ["• 예약 요약 정보를 만들지 못했어요."]

        msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # --- offer id path ---
    if oid_now:
        oid_int = int(oid_now)
        pre = call_preview("offer", oid_int, S.user_id, S.role)
        created_at = _find_created_at(pre)
        head = header_with_created("오퍼", oid_int, created_at)
        link = deeplink_for("offer", oid_int, "")
        btn = render_button("오퍼 프리뷰 열기", link)

        st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
        if st >= 300 or not isinstance(pre, dict):
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 오퍼 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        lines = _summarize_offer(pre) or ["• 오퍼 요약 정보를 만들지 못했어요."]
        msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # --- deal id path (dealroom) ---
    if did_now:
        did_int = int(did_now)
        pre = call_preview("deal", did_int, S.user_id, S.role)
        created_at = _find_created_at(pre)
        head = header_with_created("딜방", did_int, created_at)
        link = deeplink_for("dealroom", did_int, "")
        btn = render_button("딜방 프리뷰 열기", link)

        st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
        if st >= 300 or not isinstance(pre, dict):
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 딜방 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        lines = _summarize_dealroom(pre) or ["• 딜방 요약 정보를 만들지 못했어요."]
        msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")


    # ------------------------------------------------------------
    # 2.5) FAQ 직접 매핑 — intent 분류보다 먼저! (ADMIN FAQ 스킵 방지)
    # ------------------------------------------------------------
    _faq_top = _faq_direct_lookup(q, S.role)
    if _faq_top:
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": _faq_top})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(_faq_top, "faq")

    # ------------------------------------------------------------
    # 2.7) Safety: 민감 토픽 필터 (법적 리스크 방어)
    # ------------------------------------------------------------
    _sensitive = _check_sensitive_topic(q)
    if _sensitive:
        _s_cat, _s_resp, _s_log = _sensitive
        if _s_log:
            _dbg(f"[SAFETY] profanity detected: role={S.role}, q={q[:60]}")
            # 욕설 로깅 (운영 모니터링용)
            try:
                import logging
                logging.getLogger("pingpong.safety").warning(
                    "PROFANITY user=%s role=%s q=%s", S.user_id, S.role, q[:120]
                )
            except Exception:
                pass
        S.last_mode = "safety"
        S.history.append({"user": q, "bot": _s_resp})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(_s_resp, f"safety:{_s_cat}")

    # ------------------------------------------------------------
    # 3~5) LLM intent classification (replaces regex gates)
    # ------------------------------------------------------------
    intent = classify_intent(q, prev_mode, S.history[-2:], client)
    _dbg("intent", intent)
    # 최근 2턴 intent 기록 (문맥 기반 안전망용)
    S.recent_intents.append(intent.kind)
    S.recent_intents = S.recent_intents[-2:]

    # TIME_POLICY
    if intent.kind == "TIME_POLICY":
        time_ans = maybe_answer_time_policy_only(q)
        if time_ans:
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": time_ans})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(time_ans, "docs")
        # 시간정책 키워드지만 구체적 답 없으면 역핑 일반으로 fallthrough
        intent = IntentResult(kind="YEOKPING_GENERAL")

    # EXTERNAL_* (weather/news/price/finance)
    if intent.kind.startswith("EXTERNAL_"):
        ext_kind_lower = intent.kind.split("_", 1)[1].lower()
        q_ext = intent.external_query or q
        ext_ans = handle_external(raw, q_ext)
        if ext_ans:
            return ext_ans
        # EXTERNAL_WEATHER: handle_external이 None 반환(gate 미통과)해도 LLM fallthrough 금지
        # → 기상청 링크로 확정 응답 (뇌피셜 방지)
        if intent.kind == "EXTERNAL_WEATHER":
            _wm = (
                "날씨 정보를 바로 가져오지 못했어요. "
                "아래 기상청에서 직접 확인해 주세요:\n"
                "- 기상청 날씨 예보: https://www.weather.go.kr/w/index.do"
            )
            S.last_mode = "external"
            S.history.append({"user": q, "bot": _wm})
            S.history[:] = S.history[-KEEP_TURNS:]
            return _finalize_external(_wm)
        # EXTERNAL_PRICE: handle_external이 None 반환해도 LLM fallthrough 금지
        # → external_query(제품명)로 쇼핑 링크 직접 반환 (쇼핑 사이트명만이면 last_price_query 사용)
        if intent.kind == "EXTERNAL_PRICE":
            _raw_eq = (intent.external_query or q).strip()
            if not _SITE_ONLY_PAT.match(_raw_eq) and len(_raw_eq) > 3:
                S.last_price_query = _raw_eq  # 실제 제품명이면 저장
            if _SITE_ONLY_PAT.match(_raw_eq) and S.last_price_query and len(S.last_price_query) > 3:
                _raw_eq = S.last_price_query
            _eq_enc = quote_plus(_raw_eq)
            _price_links = (
                f"- 다나와: https://search.danawa.com/dsearch.php?k1={_eq_enc}\n"
                f"- 에누리: https://www.enuri.com/search.jsp?keyword={_eq_enc}\n"
                f"- 쿠팡: https://www.coupang.com/np/search?q={_eq_enc}"
            )
            # 네이버 쇼핑 API로 실제 가격 조회 (handle_external gate 미통과 케이스)
            _naver_msg = ""
            _naver_items = fetch_naver_shopping(_raw_eq)
            if _naver_items:
                _priced = [it for it in _naver_items if it.get("lprice")]
                if _priced:
                    _priced.sort(key=lambda x: int(x["lprice"]))
                    _cheapest = _priced[0]
                    _lp = int(_cheapest["lprice"])
                    _title = re.sub(r"<[^>]+>", "", _cheapest.get("title", _raw_eq))
                    _price_str = f"{_lp:,}원 (약 {_lp // 10000}만원대)" if _lp >= 10000 else f"{_lp:,}원"
                    _hp = int(_cheapest.get("hprice", "0") or "0")
                    _range_str = f"\n  가격 범위: {_lp:,}원 ~ {_hp:,}원" if _hp > _lp else ""
                    _mall = _cheapest.get("mallName", "")
                    _mall_str = f" ({_mall})" if _mall else ""
                    _naver_msg = (
                        f"🛒 {_title}\n"
                        f"  최저가: {_price_str}{_mall_str}{_range_str}\n"
                        f"  (네이버쇼핑 기준, 실제 가격과 다를 수 있습니다)\n"
                    )

            if _naver_msg:
                _pm = f"{_naver_msg}\n자세한 비교는 아래에서 확인해 보세요:\n{_price_links}"
            else:
                _pm = f"가격 정보를 직접 조회하지 못했어요. 아래에서 확인해 보세요:\n{_price_links}"
            S.last_mode = "external"
            S.history.append({"user": q, "bot": _pm})
            S.history[:] = S.history[-KEEP_TURNS:]
            return _finalize_external(_pm)
        # EXTERNAL_NEWS: handle_external이 None 반환해도 뇌피셜 뉴스 금지
        if intent.kind == "EXTERNAL_NEWS":
            _eq = (intent.external_query or q).strip()
            _eq_enc = quote_plus(_eq)
            _nm = (
                "뉴스 헤드라인을 바로 가져오지 못했어요. 아래에서 확인해 보세요:\n"
                f"- 구글뉴스: https://news.google.com/search?q={_eq_enc}&hl=ko&gl=KR&ceid=KR:ko\n"
                f"- 네이버뉴스: https://search.naver.com/search.naver?where=news&query={_eq_enc}"
            )
            S.last_mode = "external"
            S.history.append({"user": q, "bot": _nm})
            S.history[:] = S.history[-KEEP_TURNS:]
            return _finalize_external(_nm)
        # 기타 external 실패 → smalltalk fallthrough

    # YEOKPING_GENERAL
    if intent.kind == "YEOKPING_GENERAL":
        # points deterministic (server preview/me)
        if _POINT_BALANCE_PAT.search(q):
            me = call_preview_me(S.user_id, S.role)
            if isinstance(me, dict) and me.get("ok") and isinstance(me.get("pack"), dict):
                pack = me.get("pack") or {}
                points = pack.get("points") if isinstance(pack.get("points"), dict) else None
                bal = points.get("balance") if isinstance(points, dict) else None
                if bal is not None:
                    msg = f"현재 포인트 잔액은 {int(bal):,}점으로 보입니다."
                    S.last_mode = "yeokping"
                    S.history.append({"user": q, "bot": msg})
                    S.history[:] = S.history[-KEEP_TURNS:]
                    return finalize(msg, "server")

            msg = "지금은 포인트 잔액을 가져오지 못했어요. (preview/me 확인 실패)"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (FAQ는 intent 분류 전에 이미 체크됨 — 여기 도달 시 FAQ 미히트 확정)

        # ------------------------------------------------------------
        # pingpong ask (/v3_6/pingpong/ask)
        # ------------------------------------------------------------
        screen = "DEAL_ROOM"
        ctx = {
            "sidecar": {
                "last_ids": dict(S.last_ids),
                "prev_mode": S.last_mode,
            }
        }

        ask_timeout = float(os.environ.get("YP_ASK_TIMEOUT") or 0) or max(1.5, float(HTTP_TIMEOUT) / 2.0)
        ask_obj: Dict[str, Any] = call_pingpong_ask(
            screen=screen,
            role=S.role,
            question=q,
            mode="read_only",
            max_chat_messages=10,
            context=ctx,
            timeout=ask_timeout,
        )

        # ✅ 근거 저장 (출처/근거 커맨드에서 보여주기 위함)
        S.last_used_policies = ask_obj.get("used_policies") if isinstance(ask_obj, dict) else []

        msg = _render_ask_answer_for_user(ask_obj)
        S.last_answer_kind = "ask"
        S.last_used_policies = (ask_obj.get("used_policies") or []) if isinstance(ask_obj, dict) else []

        st = int(ask_obj.get("_http_status") or 0) if isinstance(ask_obj, dict) else 0
        offline = isinstance(ask_obj, dict) and ask_obj.get("error") == "OFFLINE"
        if offline or st >= 500:
            # (FAQ는 intent 전에 이미 체크됨)
            docs = retrieve_kb_snippets(q, role=S.role)
            msg = openai_generate(client, "explain", q, docs, S.history, S.user_name, S.role)
            if _is_generic_answer(msg):
                if _is_yeokping_related(q):
                    msg = "해당 역핑 기능에 대한 정보를 찾지 못했어요. 다른 질문을 해주시면 도움드리겠습니다! 😊"
                else:
                    msg = openai_generate(client, "free_chat", q, "", S.history, S.user_name, S.role)
                    S.last_mode = "chitchat"
                    S.history.append({"user": q, "bot": msg})
                    S.history[:] = S.history[-KEEP_TURNS:]
                    return finalize(msg, "free_chat")
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "docs" if docs else "없음")

        # ✅ brain 200 OK지만 답변이 빈약한 경우 KB fallback
        _weak_phrases = ["답변이 비어", "확인 중", "잠시 후", "답변을 만들지 못", "구체적으로 말해"]
        _answer_raw = (ask_obj.get("answer") or "") if isinstance(ask_obj, dict) else ""
        _is_weak = (not _answer_raw.strip()) or any(p in msg for p in _weak_phrases)
        if _is_weak:
            docs = retrieve_kb_snippets(q, role=S.role)
            if docs:
                msg = openai_generate(client, "explain", q, docs, S.history, S.user_name, S.role)
                if _is_generic_answer(msg):
                    if _is_yeokping_related(q):
                        msg = "해당 역핑 기능에 대한 정보를 찾지 못했어요. 다른 질문을 해주시면 도움드리겠습니다! 😊"
                    else:
                        msg = openai_generate(client, "free_chat", q, "", S.history, S.user_name, S.role)
                        S.last_mode = "chitchat"
                        S.history.append({"user": q, "bot": msg})
                        S.history[:] = S.history[-KEEP_TURNS:]
                        return finalize(msg, "free_chat")
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "docs_fallback")

        # ✅ server 답변이 역핑 무관 일반 답변이면 → 역핑이면 차단, 아니면 자유 답변
        if _is_generic_answer(msg):
            if _is_yeokping_related(q):
                msg = "해당 역핑 기능에 대한 정보를 찾지 못했어요. 다른 질문을 해주시면 도움드리겠습니다! 😊"
            else:
                msg = openai_generate(client, "free_chat", q, "", S.history, S.user_name, S.role)
                S.last_mode = "chitchat"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "free_chat")

        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # SMALLTALK (또는 EXTERNAL_* fallthrough) → 자유 답변!
    ans = openai_generate(client, "free_chat", q, "", S.history, S.user_name, S.role)
    S.last_mode = "chitchat"
    S.history.append({"user": q, "bot": ans})
    S.history[:] = S.history[-KEEP_TURNS:]
    return finalize(ans, "free_chat")



def _infer_screen_from_state() -> str:
    # ✅ 무조건 DEAL_ROOM로 박아도 되지만, 최소한의 힌트로 분기
    # (너희 server pingpong.py의 _choose_policy_domains(body.screen) 때문)
    if S.last_ids.get("reservation_id"):
        return "RESERVATION"
    if S.last_ids.get("offer_id"):
        return "OFFER"
    if S.last_ids.get("deal_id"):
        return "DEAL_ROOM"
    return "DEAL_ROOM"


def _render_ask_answer_for_user(obj: Dict[str, Any]) -> str:
    # ask가 JSON으로 주는 answer/actions/used_policies를 "입" 톤으로 짧게 정리
    if not isinstance(obj, dict):
        return "지금은 답변을 만들지 못했어요."

    st = int(obj.get("_http_status") or 0)
    if st >= 500 or obj.get("error") == "OFFLINE":
        return "지금 서버 답변이 불안정해요. 잠시 후 다시 물어봐 주세요."
    if st >= 300:
        detail = obj.get("detail") or obj.get("error") or "요청이 처리되지 않았습니다."
        return f"지금은 답변을 가져오지 못했어요: {detail}"

    answer = (obj.get("answer") or "").strip()
    if not answer:
        return "지금은 답변이 비어 있어요. 질문을 조금만 더 구체적으로 말해줄래요?"

    # (선택) 정책 출처 1~3개만 가볍게 노출
    used = obj.get("used_policies") or obj.get("usedPolicies") or []
    if isinstance(used, list) and used:
        refs: List[str] = []
        for p in used[:3]:
            if isinstance(p, dict):
                t = (p.get("title") or p.get("policy_key") or p.get("policyKey") or "").strip()
                if t:
                    refs.append(t)
            elif isinstance(p, str) and p.strip():
                refs.append(p.strip())
        if refs:
            answer += "\n\n(근거: " + " / ".join(refs[:3]) + ")"

    if (S.role or "").upper() in ("BUYER", "SELLER"):
        answer = answer.replace("admin/", "public/")


    return answer



# ============================================================
# Interactive main
# ============================================================
def main() -> None:
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        print("❌ OPENAI_API_KEY가 없습니다.\n   (PowerShell) $env:OPENAI_API_KEY='...'\n")
        return

    client = OpenAI()
    load_kb()
    load_time_values_from_defaults()

    print("\n" + "=" * 60)
    print("🤖 Pingpong Sidecar (OpenAI) v1.2 — preview_pack + refund_preview + external(budgeted)")
    print(f"   server={YP_SERVER_URL}")
    print(f"   model={OPENAI_MODEL}")
    print(f"   server_timeout={HTTP_TIMEOUT:.1f}s / external_timeout={EXTERNAL_TIMEOUT:.1f}s")
    print("=" * 60)

    role_map = {"1": "ADMIN", "2": "SELLER", "3": "BUYER"}
    c = input("권한 선택 (1:Admin, 2:Seller, 3:Buyer): ").strip()
    S.role = role_map.get(c, "BUYER")

    uid_in = input("user_id (기본 1): ").strip()
    S.user_id = int(uid_in) if uid_in.isdigit() else 1
    S.user_name = USER_NAME

    print(f"\n✅ [{S.role}] 시작 (종료: exit/quit). '출처'라고 치면 마지막 링크를 보여줌.\n")

    while True:
        raw = input("나: ").strip()
        if raw.lower() in ("exit", "quit"):
            break
        ans = step_once(raw, client)
        if ans:
            print(f"\n핑퐁이: {ans}\n")



if __name__ == "__main__":
    main()
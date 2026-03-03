#!/usr/bin/env python3
"""
tools/pingpong_autotest.py

핑퐁이 자동 테스트 — 200 케이스 (단발 100 + 꼬리물기 100턴)
결과는 tools/autotest_result.json 으로 저장.

사용법:
  python tools/pingpong_autotest.py            # 전체 200개
  python tools/pingpong_autotest.py --single   # 단발 100개만
  python tools/pingpong_autotest.py --multi    # 꼬리물기 100턴만
  python tools/pingpong_autotest.py --quick    # 단발 30개 샘플
  python tools/pingpong_autotest.py --delay 0.5  # 딜레이(초, 기본 0.3)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

# Windows cp949 터미널에서 Unicode 특수문자 출력 시 크래시 방지
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from openai import OpenAI
import pingpong_sidecar_openai as _sidecar          # type: ignore
from pingpong_sidecar_openai import (                # type: ignore
    INTENT_MODEL,
    IntentResult,
    ConversationState,
    classify_intent,
    step_once,
)

# ══════════════════════════════════════════════════════════════
# 데이터 구조
# ══════════════════════════════════════════════════════════════

@dataclass
class Case:
    q: str
    expected: str
    alt: Optional[str] = None
    note: str = ""

@dataclass
class Turn:
    q: str
    expected: str
    alt: Optional[str] = None

@dataclass
class Scenario:
    name: str
    turns: List[Turn]

@dataclass
class TestRecord:
    question: str
    expected_kind: str
    actual_kind: str
    passed: bool
    answer: str
    alt_kind: Optional[str] = None
    from_fallback: bool = False
    scenario: Optional[str] = None
    turn: Optional[int] = None


# ══════════════════════════════════════════════════════════════
# 단발 케이스 100개
# ══════════════════════════════════════════════════════════════

_POLICY: List[Case] = [
    Case("수수료가 얼마야?",                              "YEOKPING_GENERAL"),
    Case("역핑 수수료 어떻게 돼?",                       "YEOKPING_GENERAL"),
    Case("PG 수수료는 누가 부담해?",                    "YEOKPING_GENERAL"),
    Case("판매자 수수료가 얼마야?",                      "YEOKPING_GENERAL"),
    Case("환불하면 수수료 있어?",                        "YEOKPING_GENERAL"),
    Case("배송비 정책이 어떻게 돼?",                    "YEOKPING_GENERAL"),
    Case("역핑 포인트 유효기간이 어떻게 돼?",            "YEOKPING_GENERAL"),
    Case("포인트 적립 기준이 뭐야?",                    "YEOKPING_GENERAL"),
    Case("환불 후 포인트는 어떻게 돼?",                 "YEOKPING_GENERAL"),
    Case("포인트로 결제할 수 있어?",                    "YEOKPING_GENERAL"),
    Case("딜 개설 방법이 뭐야?",                        "YEOKPING_GENERAL"),
    Case("오퍼 올리는 방법이 뭐야?",                   "YEOKPING_GENERAL"),
    Case("오퍼 수정 가능해?",                           "YEOKPING_GENERAL"),
    Case("오퍼 낙찰 기준이 뭐야?",                     "YEOKPING_GENERAL"),
    Case("역입찰이 뭔가요?",                             "YEOKPING_GENERAL"),
    Case("액츄에이터가 뭐야?",                           "YEOKPING_GENERAL"),
    Case("액츄에이터 수수료가 얼마야?",                  "YEOKPING_GENERAL"),
    Case("딜방 개설 조건이 뭐야?",                      "YEOKPING_GENERAL"),
    Case("딜룸 참여 방법이 뭐야?",                      "YEOKPING_GENERAL"),
    Case("예약이 뭐야?",                                 "YEOKPING_GENERAL"),
    Case("예약 취소 가능해?",                            "YEOKPING_GENERAL"),
    Case("구매확정 어떻게 해?",                         "YEOKPING_GENERAL"),
    Case("부분환불 되나요?",                             "YEOKPING_GENERAL"),
    Case("전액환불 조건이 뭐야?",                       "YEOKPING_GENERAL"),
    Case("배송 후 환불은 어떻게 해?",                   "YEOKPING_GENERAL"),
    Case("정산 언제 돼?",                                "YEOKPING_GENERAL"),
    Case("정산 지연되면 어떻게 해?",                    "YEOKPING_GENERAL"),
    Case("판매자 레벨 올리는 조건이 뭐야?",             "YEOKPING_GENERAL"),
    Case("역핑 회원 등급 혜택이 뭐야?",                 "YEOKPING_GENERAL"),
    Case("정산 전 환불이랑 정산 후 환불 차이가 뭐야?",  "YEOKPING_GENERAL"),
]

_FALSEPOS: List[Case] = [
    Case("마감이 언제야?",                    "SMALLTALK",      note="맥락 불명"),
    Case("입학 마감일이 언제야?",             "SMALLTALK",      note="비역핑 마감"),
    Case("취업 지원 마감이 언제야?",         "SMALLTALK",      note="비역핑 마감"),
    Case("공모전 마감이 언제야?",             "SMALLTALK",      note="비역핑 마감"),
    Case("시험 접수 마감이 언제야?",         "SMALLTALK",      note="비역핑 마감"),
    Case("이벤트 마감일이 언제야?",          "SMALLTALK",      note="비역핑 마감"),
    Case("딜 마감 기간이 얼마야?",           "TIME_POLICY",    note="역핑 내부 시간정책"),
    Case("오퍼 마감은 며칠이야?",            "TIME_POLICY",    note="역핑 내부 시간정책"),
    Case("쿨링기간이 얼마야?",               "TIME_POLICY",    alt="YEOKPING_GENERAL"),
    Case("결제 제한시간이 얼마야?",          "TIME_POLICY",    note="역핑 내부 시간정책"),
    Case("박찬호 얼마 벌었어?",              "SMALLTALK",      note="인물 수입 오탐"),
    Case("손흥민 연봉이 얼마야?",            "SMALLTALK",      note="인물 연봉 오탐"),
    Case("BTS 수입이 얼마야?",               "SMALLTALK",      note="인물 수입 오탐"),
    Case("김연아 재산이 얼마야?",            "SMALLTALK",      note="인물 재산 오탐"),
    Case("종가집 김치 가격 얼마야?",         "EXTERNAL_PRICE", note="종가(집) 브랜드"),
    Case("종가집 깍두기 최저가 알려줘",      "EXTERNAL_PRICE", note="종가(집) 브랜드"),
    Case("얼마야?",                           "SMALLTALK",      note="맥락 없는 얼마"),
    Case("얼마면 되겠어?",                    "SMALLTALK"),
    Case("오퍼가 뭐야?",                      "YEOKPING_GENERAL", note="역핑 전용어"),
    Case("딜방이 뭐야?",                      "YEOKPING_GENERAL", note="역핑 전용어"),
    Case("역입찰이 어떻게 돼?",              "YEOKPING_GENERAL", note="역핑 전용어"),
    Case("쿨링이 뭐야?",                      "YEOKPING_GENERAL", alt="TIME_POLICY"),
    Case("정산이 뭐야?",                      "YEOKPING_GENERAL", note="역핑 전용어"),
    Case("액츄에이터는 누가 해?",            "YEOKPING_GENERAL", note="역핑 전용어"),
    Case("안녕",                               "SMALLTALK"),
    Case("너 잘 지내?",                        "SMALLTALK"),
    Case("밥 먹었어?",                         "SMALLTALK"),
    Case("오늘 기분이 어때?",                 "SMALLTALK"),
    Case("고마워",                              "SMALLTALK"),
    Case("그렇구나",                            "SMALLTALK"),
]

_EXTERNAL: List[Case] = [
    Case("오늘 서울 날씨 어때?",              "EXTERNAL_WEATHER"),
    Case("내일 부산 날씨 알려줘",             "EXTERNAL_WEATHER"),
    Case("주말 날씨가 어때?",                 "EXTERNAL_WEATHER"),
    Case("강수확률이 얼마야?",                "EXTERNAL_WEATHER"),
    Case("미세먼지 오늘 어때?",               "EXTERNAL_WEATHER"),
    Case("달러 환율이 얼마야?",               "EXTERNAL_FINANCE"),
    Case("원/달러 환율 알려줘",               "EXTERNAL_FINANCE"),
    Case("코스피 지금 얼마야?",               "EXTERNAL_FINANCE"),
    Case("코스닥 오늘 종가가 얼마야?",        "EXTERNAL_FINANCE"),
    Case("엔화 환율 알려줘",                  "EXTERNAL_FINANCE"),
    Case("오늘 뉴스 알려줘",                  "EXTERNAL_NEWS"),
    Case("최신 IT 뉴스 있어?",                "EXTERNAL_NEWS"),
    Case("반도체 관련 뉴스 있어?",            "EXTERNAL_NEWS"),
    Case("갤럭시 S25 가격이 얼마야?",         "EXTERNAL_PRICE"),
    Case("아이폰 16 최저가가 얼마야?",        "EXTERNAL_PRICE"),
    Case("LG 그램 노트북 가격 알려줘",        "EXTERNAL_PRICE"),
    Case("RTX 4090 가격이 얼마야?",           "EXTERNAL_PRICE"),
    Case("맥북 M4 Pro 최저가가 얼마야?",      "EXTERNAL_PRICE"),
    Case("다이슨 청소기 가격 알려줘",         "EXTERNAL_PRICE"),
    Case("삼성 비스포크 냉장고 최저가는?",    "EXTERNAL_PRICE"),
]

_ID_CASES: List[Case] = [
    Case("예약 1번 환불 방법이 뭐야?",             "YEOKPING_GENERAL"),
    Case("reservation_id 5 취소 방법이 뭐야?",     "YEOKPING_GENERAL"),
    Case("오퍼 3번 수정할 수 있어?",               "YEOKPING_GENERAL"),
    Case("딜 10번 상태가 어떻게 돼?",              "YEOKPING_GENERAL"),
    Case("예약번호 7 환불 정책이 어떻게 돼?",      "YEOKPING_GENERAL"),
    Case("offer_id=2 가격이 얼마야?",               "YEOKPING_GENERAL"),
    Case("deal_id 15 마감이 언제야?",               "YEOKPING_GENERAL"),
    Case("예약 취소 시 수수료가 있어?",            "YEOKPING_GENERAL"),
    Case("오퍼 5번 낙찰 기준이 뭐야?",            "YEOKPING_GENERAL"),
    Case("딜방 3 참여자가 몇 명이야?",             "YEOKPING_GENERAL"),
    Case("예약 ID 12번 환불 신청 어떻게 해?",      "YEOKPING_GENERAL"),
    Case("내 reservation 취소 가능 기간이 얼마야?","YEOKPING_GENERAL"),
    Case("오퍼 ID 9 배송비가 얼마야?",             "YEOKPING_GENERAL"),
    Case("딜 20번 쿨링기간이 얼마야?",             "YEOKPING_GENERAL", alt="TIME_POLICY"),
    Case("예약 2번 부분환불 되나요?",              "YEOKPING_GENERAL"),
    Case("오퍼 7번 판매자 수수료가 얼마야?",       "YEOKPING_GENERAL"),
    Case("reservation 4번 포인트 환불 되나요?",    "YEOKPING_GENERAL"),
    Case("딜 33번 정산 언제 돼?",                  "YEOKPING_GENERAL"),
    Case("내 예약 취소하면 위약금 있어?",          "YEOKPING_GENERAL"),
    Case("오퍼 11번 이미 낙찰됐어?",               "YEOKPING_GENERAL"),
]

SINGLE_CASES: List[Case] = _POLICY + _FALSEPOS + _EXTERNAL + _ID_CASES
assert len(SINGLE_CASES) == 100

# ── v2 단품 추가 (15건) ─────────────────────────────────────
_SINGLE_V2: List[Case] = [
    # A. 네이버 API 엣지케이스 (5건)
    Case("에어팟 프로 2세대 가격 알려줘",              "EXTERNAL_PRICE"),
    Case("쌀 20kg 가격 얼마야?",                        "EXTERNAL_PRICE"),
    Case("아이패드 미니 7세대 최저가 알려줘",          "EXTERNAL_PRICE"),
    Case("닌텐도 스위치 2 가격이 얼마야?",             "EXTERNAL_PRICE"),
    Case("RTX 5090 가격 알려줘",                        "EXTERNAL_PRICE"),
    # B. 의도 경계 스트레스 (6건)
    Case("역핑에서 갤럭시 S25 딜 만들면 가격이 얼마쯤 될까?", "YEOKPING_GENERAL"),
    Case("수수료가 너무 비싸면 환불받을 수 있어?",     "YEOKPING_GENERAL"),
    Case("포인트로 맥북 살 수 있어?",                  "YEOKPING_GENERAL"),
    Case("오늘 비 오는데 배송 괜찮을까?",              "SMALLTALK",          alt="YEOKPING_GENERAL"),
    Case("뉴스에서 본 건데 역핑 같은 서비스가 뜬대",  "YEOKPING_GENERAL"),
    Case("환율이 오르면 수수료도 올라?",               "YEOKPING_GENERAL"),
    # C. 스몰톡 새 유형 (4건)
    Case("심심한데 뭐 하면 좋을까?",                   "SMALLTALK"),
    Case("오늘 점심 뭐 먹지?",                          "SMALLTALK"),
    Case("역핑 직원이야?",                              "SMALLTALK"),
    Case("너 이름이 뭐야?",                             "SMALLTALK"),
]
SINGLE_CASES_V2: List[Case] = SINGLE_CASES + _SINGLE_V2
assert len(SINGLE_CASES_V2) == 115


# ══════════════════════════════════════════════════════════════
# 꼬리물기 시나리오 10 × 10턴 = 100턴
# ══════════════════════════════════════════════════════════════

SCENARIOS: List[Scenario] = [
    Scenario("S01_수수료→레벨→혜택", [
        Turn("역핑 수수료가 어떻게 돼?",             "YEOKPING_GENERAL"),
        Turn("그러면 레벨업하면 수수료 달라져?",     "YEOKPING_GENERAL"),
        Turn("레벨 올리는 조건이 뭐야?",             "YEOKPING_GENERAL"),
        Turn("레벨 2 혜택은 뭐야?",                  "YEOKPING_GENERAL"),
        Turn("포인트도 레벨이랑 연관 있어?",         "YEOKPING_GENERAL"),
        Turn("포인트 적립 기준이 뭐야?",             "YEOKPING_GENERAL"),
        Turn("포인트 유효기간은?",                    "YEOKPING_GENERAL"),
        Turn("포인트로 수수료 낼 수 있어?",          "YEOKPING_GENERAL"),
        Turn("환불받으면 포인트는 어떻게 돼?",       "YEOKPING_GENERAL"),
        Turn("부분환불도 포인트 돌려줘?",            "YEOKPING_GENERAL"),
    ]),
    Scenario("S02_딜방개설→오퍼→예약→환불", [
        Turn("딜방 어떻게 개설해?",                  "YEOKPING_GENERAL"),
        Turn("오퍼 올리는 방법이 뭐야?",            "YEOKPING_GENERAL"),
        Turn("오퍼 수정 기간이 얼마야?",             "TIME_POLICY", alt="YEOKPING_GENERAL"),
        Turn("예약이 뭐야?",                          "YEOKPING_GENERAL"),
        Turn("예약 취소 가능해?",                     "YEOKPING_GENERAL"),
        Turn("취소 수수료가 있어?",                  "YEOKPING_GENERAL"),
        Turn("배송 후 환불은?",                       "YEOKPING_GENERAL"),
        Turn("환불 처리 기간이 얼마야?",             "TIME_POLICY", alt="YEOKPING_GENERAL"),
        Turn("정산은 언제 돼?",                       "YEOKPING_GENERAL"),
        Turn("정산 지연되면 어떻게 해?",             "YEOKPING_GENERAL"),
    ]),
    Scenario("S03_날씨→스몰톡→역핑전환", [
        Turn("오늘 서울 날씨 어때?",                  "EXTERNAL_WEATHER"),
        Turn("내일은?",                               "EXTERNAL_WEATHER", alt="SMALLTALK"),
        Turn("비 맞으면 기분 별로지",                "SMALLTALK"),
        Turn("근데 역핑이 뭐야?",                     "YEOKPING_GENERAL"),
        Turn("공동구매 플랫폼이야?",                  "YEOKPING_GENERAL"),
        Turn("딜이 뭔가요?",                           "YEOKPING_GENERAL"),
        Turn("수수료가 얼마야?",                       "YEOKPING_GENERAL"),
        Turn("환불 정책은?",                           "YEOKPING_GENERAL"),
        Turn("내일 날씨 다시 알려줘",                 "EXTERNAL_WEATHER"),
        Turn("고마워",                                  "SMALLTALK"),
    ]),
    Scenario("S04_환율→뉴스→제품가격→역핑", [
        Turn("달러 환율이 얼마야?",                   "EXTERNAL_FINANCE"),
        Turn("엔화는?",                               "EXTERNAL_FINANCE"),
        Turn("오늘 경제 뉴스 뭐 있어?",              "EXTERNAL_NEWS"),
        Turn("갤럭시 S25 가격은?",                    "EXTERNAL_PRICE"),
        Turn("다나와 최저가가 얼마야?",               "EXTERNAL_PRICE"),
        Turn("역핑에서 이 제품 공구 할 수 있어?",     "YEOKPING_GENERAL"),
        Turn("딜 개설하려면 어떻게 해?",              "YEOKPING_GENERAL"),
        Turn("수수료가 얼마야?",                       "YEOKPING_GENERAL"),
        Turn("정산은 어떻게 돼?",                      "YEOKPING_GENERAL"),
        Turn("감사해요",                               "SMALLTALK"),
    ]),
    Scenario("S05_환불분쟁", [
        Turn("환불 신청하고 싶어",                    "YEOKPING_GENERAL"),
        Turn("판매자가 거부하면 어떻게 해?",          "YEOKPING_GENERAL"),
        Turn("관리자한테 신고할 수 있어?",            "YEOKPING_GENERAL"),
        Turn("분쟁 해결 기간이 얼마야?",              "TIME_POLICY", alt="YEOKPING_GENERAL"),
        Turn("환불 금액 계산 어떻게 해?",             "YEOKPING_GENERAL"),
        Turn("수수료는 누가 부담해?",                 "YEOKPING_GENERAL"),
        Turn("배송비는?",                              "YEOKPING_GENERAL"),
        Turn("포인트 환불되나?",                       "YEOKPING_GENERAL"),
        Turn("정산 전 환불이랑 정산 후 환불이 달라?", "YEOKPING_GENERAL"),
        Turn("언제 환불금이 들어와?",                 "YEOKPING_GENERAL"),
    ]),
    Scenario("S06_판매자온보딩", [
        Turn("판매자 등록 어떻게 해?",               "YEOKPING_GENERAL"),
        Turn("액츄에이터가 뭐야?",                    "YEOKPING_GENERAL"),
        Turn("액츄에이터 수수료가 얼마야?",           "YEOKPING_GENERAL"),
        Turn("딜이랑 오퍼 차이가 뭐야?",             "YEOKPING_GENERAL"),
        Turn("오퍼 낙찰 기준이 뭐야?",               "YEOKPING_GENERAL"),
        Turn("역입찰이 뭔가요?",                       "YEOKPING_GENERAL"),
        Turn("쿨링기간이 얼마야?",                    "TIME_POLICY", alt="YEOKPING_GENERAL"),
        Turn("정산 조건이 어떻게 돼?",               "YEOKPING_GENERAL"),
        Turn("판매자 등급 올리면 혜택이 뭐야?",      "YEOKPING_GENERAL"),
        Turn("오퍼 수정 언제까지 가능해?",            "TIME_POLICY", alt="YEOKPING_GENERAL"),
    ]),
    Scenario("S07_스몰톡→역핑유입", [
        Turn("안녕",                                   "SMALLTALK"),
        Turn("오늘 날씨 좀 추운 것 같아",             "SMALLTALK", alt="EXTERNAL_WEATHER"),
        Turn("밥 먹었어?",                             "SMALLTALK"),
        Turn("역핑이라는 앱 알아?",                   "YEOKPING_GENERAL"),
        Turn("공동구매 앱이야?",                       "YEOKPING_GENERAL"),
        Turn("수수료 없어?",                           "YEOKPING_GENERAL"),
        Turn("배송은 어떻게 해?",                      "YEOKPING_GENERAL"),
        Turn("환불 가능해?",                            "YEOKPING_GENERAL"),
        Turn("포인트도 있어?",                          "YEOKPING_GENERAL"),
        Turn("써봐야겠다",                              "SMALLTALK"),
    ]),
    Scenario("S08_제품가격리서치→딜개설", [
        Turn("맥북 M4 Pro 가격 알려줘",               "EXTERNAL_PRICE"),
        Turn("다나와 최저가가 얼마야?",               "EXTERNAL_PRICE"),
        Turn("에누리에서도 찾아줘",                    "EXTERNAL_PRICE"),
        Turn("역핑에서 공동구매하면 더 저렴해?",      "YEOKPING_GENERAL"),
        Turn("딜 개설하면 내가 판매자가 되는 거야?",  "YEOKPING_GENERAL"),
        Turn("오퍼 올리는 방법이 뭐야?",             "YEOKPING_GENERAL"),
        Turn("수수료가 얼마야?",                       "YEOKPING_GENERAL"),
        Turn("정산 기간이 얼마야?",                    "YEOKPING_GENERAL"),
        Turn("쿨링기간이 뭐야?",                       "YEOKPING_GENERAL", alt="TIME_POLICY"),
        Turn("맥북 공구 해봐야겠다",                   "SMALLTALK"),
    ]),
    Scenario("S09_뉴스→시사→역핑전환", [
        Turn("오늘 경제 뉴스 알려줘",                 "EXTERNAL_NEWS"),
        Turn("반도체 관련 뉴스 있어?",               "EXTERNAL_NEWS"),
        Turn("삼성전자 주가가 얼마야?",              "EXTERNAL_FINANCE"),
        Turn("역핑에서 삼성 제품 공구 할 수 있어?",  "YEOKPING_GENERAL"),
        Turn("딜 개설 조건이 뭐야?",                  "YEOKPING_GENERAL"),
        Turn("오퍼가 뭐야?",                           "YEOKPING_GENERAL"),
        Turn("예약이랑 오퍼 차이가 뭐야?",           "YEOKPING_GENERAL"),
        Turn("환불하면 수수료 있어?",                 "YEOKPING_GENERAL"),
        Turn("정산은 언제 돼?",                        "YEOKPING_GENERAL"),
        Turn("알겠어 감사해",                          "SMALLTALK"),
    ]),
    Scenario("S10_여행날씨→역핑전환", [
        Turn("오늘 제주도 날씨 어때?",               "EXTERNAL_WEATHER"),
        Turn("비 올 것 같아?",                        "EXTERNAL_WEATHER"),
        Turn("여행 가기 좋은 날씨야?",               "EXTERNAL_WEATHER", alt="SMALLTALK"),
        Turn("역핑에서 여행용품 살 수 있어?",         "YEOKPING_GENERAL"),
        Turn("딜 개설 어떻게 해?",                    "YEOKPING_GENERAL"),
        Turn("공동구매 참여자 제한 있어?",            "YEOKPING_GENERAL"),
        Turn("오퍼 마감 기간이 얼마야?",              "TIME_POLICY"),
        Turn("결제 제한시간이 얼마야?",               "TIME_POLICY"),
        Turn("쿨링기간 지나면 정산 돼?",              "YEOKPING_GENERAL"),
        Turn("고마워",                                  "SMALLTALK", alt="YEOKPING_GENERAL"),
    ]),
]

# ══════════════════════════════════════════════════════════════
# v2 시나리오 추가: S11, S12 (4턴씩)
# ══════════════════════════════════════════════════════════════
SCENARIOS += [
    Scenario("S11_가격->딜의향->수수료->결제", [
        Turn("에어팟 프로 2세대 가격 좀 봐줘",        "EXTERNAL_PRICE"),
        Turn("이 가격이면 역핑에서 딜 만들어볼까?",   "YEOKPING_GENERAL"),
        Turn("딜 개설하면 수수료가 얼마나 나와?",     "YEOKPING_GENERAL"),
        Turn("결제는 어떤 방식으로 해?",              "YEOKPING_GENERAL"),
    ]),
    Scenario("S12_스몰톡->뉴스->가격->역핑전환", [
        Turn("오늘 기분이 좋아!",                      "SMALLTALK"),
        Turn("오늘 IT 뉴스 뭐 있어?",                  "EXTERNAL_NEWS"),
        Turn("아이패드 미니 최저가 알려줘",            "EXTERNAL_PRICE"),
        Turn("역핑에서 공동구매하면 더 싸질까?",       "YEOKPING_GENERAL"),
    ]),
]

assert len(SCENARIOS) == 12
assert all(len(s.turns) >= 4 for s in SCENARIOS)


# ══════════════════════════════════════════════════════════════
# 유틸리티
# ══════════════════════════════════════════════════════════════

def _reset_state() -> None:
    """사이드카 글로벌 상태 초기화."""
    _sidecar.S = ConversationState()


def _is_pass(actual: str, expected: str, alt: Optional[str]) -> bool:
    return actual == expected or (alt is not None and actual == alt)


def _get_intent_and_answer(q: str, client: OpenAI) -> Tuple[IntentResult, str]:
    """
    1) classify_intent → 캐시 저장
    2) step_once       → 캐시 히트로 intent 재사용, 실제 답변 반환
    step_once 오류 시 answer = "[step_once 오류: ...]"
    """
    prev_mode = _sidecar.S.last_mode
    history_slice = list(_sidecar.S.history[-2:])
    intent = classify_intent(q, prev_mode, history_slice, client)
    try:
        answer = step_once(q, client)
    except Exception as exc:
        answer = f"[step_once 오류: {exc}]"
    return intent, answer


# ══════════════════════════════════════════════════════════════
# 테스트 러너
# ══════════════════════════════════════════════════════════════

def run_single(
    cases: List[Case],
    client: OpenAI,
    delay: float,
    label: str = "단발",
) -> Tuple[List[TestRecord], int, int]:
    total = len(cases)
    passed = 0
    records: List[TestRecord] = []

    print(f"\n{'='*64}")
    print(f"[{label}] {total}개 케이스")
    print(f"{'='*64}")

    for i, c in enumerate(cases, 1):
        _reset_state()
        intent, answer = _get_intent_and_answer(c.q, client)

        ok = _is_pass(intent.kind, c.expected, c.alt)
        if ok:
            passed += 1

        mark = "v" if ok else "X"
        fb   = " [fallback]" if intent.from_fallback else ""
        alt_s = f" (또는 {c.alt})" if c.alt else ""
        note_s = f" <- {c.note}" if c.note else ""
        print(f"  [{i:03d}] {mark} 실제={intent.kind}  기대={c.expected}{alt_s}{fb}{note_s}")
        print(f"        Q: {c.q}")
        print(f"        A: {answer[:120].strip()}")

        records.append(TestRecord(
            question=c.q,
            expected_kind=c.expected,
            actual_kind=intent.kind,
            passed=ok,
            answer=answer.strip(),
            alt_kind=c.alt,
            from_fallback=intent.from_fallback,
        ))

        if i < total:
            time.sleep(delay)

    print(f"\n[{label}] {passed}/{total} 통과")
    return records, total, passed


def run_multi(
    scenarios: List[Scenario],
    client: OpenAI,
    delay: float,
) -> Tuple[List[TestRecord], int, int]:
    total_turns = sum(len(s.turns) for s in scenarios)
    passed = 0
    records: List[TestRecord] = []

    print(f"\n{'='*64}")
    print(f"[꼬리물기] {len(scenarios)}개 시나리오 / {total_turns}턴")
    print(f"{'='*64}")

    for s in scenarios:
        print(f"\n  -- {s.name} --")
        _reset_state()

        for t_idx, turn in enumerate(s.turns, 1):
            intent, answer = _get_intent_and_answer(turn.q, client)

            ok = _is_pass(intent.kind, turn.expected, turn.alt)
            if ok:
                passed += 1

            mark  = "v" if ok else "X"
            fb    = " [fallback]" if intent.from_fallback else ""
            alt_s = f" (또는 {turn.alt})" if turn.alt else ""
            print(f"    T{t_idx:02d} {mark} 실제={intent.kind}  기대={turn.expected}{alt_s}{fb}")
            print(f"         Q: {turn.q}")
            print(f"         A: {answer[:100].strip()}")

            records.append(TestRecord(
                question=turn.q,
                expected_kind=turn.expected,
                actual_kind=intent.kind,
                passed=ok,
                answer=answer.strip(),
                alt_kind=turn.alt,
                from_fallback=intent.from_fallback,
                scenario=s.name,
                turn=t_idx,
            ))

            if t_idx < len(s.turns):
                time.sleep(delay)

    print(f"\n[꼬리물기] {passed}/{total_turns} 통과")
    return records, total_turns, passed


# ══════════════════════════════════════════════════════════════
# JSON 저장
# ══════════════════════════════════════════════════════════════

def save_json(
    records: List[TestRecord],
    grand_total: int,
    grand_passed: int,
    out_path: str,
) -> None:
    accuracy = round(grand_passed / grand_total * 100, 1) if grand_total else 0.0
    payload: Dict[str, Any] = {
        "summary": {
            "total": grand_total,
            "correct": grand_passed,
            "accuracy": accuracy,
            "tested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "intent_model": INTENT_MODEL,
        },
        "results": [
            {
                "question": r.question,
                "expected_kind": r.expected_kind,
                "actual_kind": r.actual_kind,
                "passed": r.passed,
                "answer": r.answer,
                **({"alt_kind": r.alt_kind} if r.alt_kind else {}),
                **({"from_fallback": True} if r.from_fallback else {}),
                **({"scenario": r.scenario, "turn": r.turn}
                   if r.scenario is not None else {}),
            }
            for r in records
        ],
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n>> 결과 저장: {out_path}")


# ══════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="핑퐁이 자동 테스트")
    parser.add_argument("--single", action="store_true", help="단발 100개만")
    parser.add_argument("--multi",  action="store_true", help="꼬리물기 100턴만")
    parser.add_argument("--quick",  action="store_true", help="단발 30개 랜덤 샘플")
    parser.add_argument("--delay",  type=float, default=0.3,
                        help="API 호출 간 딜레이(초, 기본 0.3)")
    parser.add_argument("--out",    type=str,
                        default=os.path.join(_HERE, "autotest_result.json"),
                        help="결과 JSON 경로")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY 환경변수가 없습니다.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    print(f"의도 분류 모델: {INTENT_MODEL}  |  딜레이: {args.delay}s")
    print(f"출력 경로: {args.out}")

    all_records: List[TestRecord] = []
    grand_total = 0
    grand_passed = 0
    run_all = not (args.single or args.multi or args.quick)

    if args.quick:
        sample = random.sample(SINGLE_CASES_V2, 30)
        recs, t, p = run_single(sample, client, args.delay, label="빠른샘플(30)")
        all_records.extend(recs); grand_total += t; grand_passed += p

    if run_all or args.single:
        recs, t, p = run_single(SINGLE_CASES_V2, client, args.delay, label="단발(v2)")
        all_records.extend(recs); grand_total += t; grand_passed += p

    if run_all or args.multi:
        recs, t, p = run_multi(SCENARIOS, client, args.delay)
        all_records.extend(recs); grand_total += t; grand_passed += p

    pct = grand_passed / grand_total * 100 if grand_total else 0.0
    print(f"\n{'='*64}")
    print(f"최종: {grand_passed}/{grand_total} 통과 ({pct:.1f}%)")
    print("PASS (90%+)" if pct >= 90 else ("WARN (75~89%)" if pct >= 75 else "FAIL (<75%)"))
    print(f"{'='*64}")

    save_json(all_records, grand_total, grand_passed, args.out)


if __name__ == "__main__":
    main()

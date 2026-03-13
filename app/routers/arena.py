# app/routers/arena.py
# 역핑 배틀 아레나 — 6개 미니게임 + 실시간 배틀 맵 + 랭킹
import random
import math
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db, engine
from app.security import get_current_user
from app.models import ArenaPlayer, ArenaGame, ArenaRegionStats
from app.database import Base

# 아레나 테이블 자동 생성
try:
    Base.metadata.create_all(bind=engine)
except Exception as _e:
    print(f"[arena] create_all: {_e}")

router = APIRouter(prefix="/arena", tags=["arena"])

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────
DAILY_LIMIT = 30
GAME_TYPES = {"rps", "mjb", "yut", "math", "quiz", "reaction"}

LEVEL_THRESHOLDS = [
    (500, "legend"),
    (200, "champion"),
    (50, "fighter"),
    (0, "rookie"),
]

QUIZ_QUESTIONS = [
    {"q": "역핑에서 '역'은 무엇의 약자?", "choices": ["역경매", "역할", "역사", "역전"], "answer": 0, "lang": "ko"},
    {"q": "공동구매에서 참여자가 많아지면 가격은?", "choices": ["올라간다", "내려간다", "변동없다", "랜덤"], "answer": 1, "lang": "ko"},
    {"q": "역핑의 '핑'은 무엇을 의미?", "choices": ["핑퐁(소통)", "핑크", "핑거", "핑계"], "answer": 0, "lang": "ko"},
    {"q": "대한민국의 수도는?", "choices": ["부산", "서울", "인천", "대전"], "answer": 1, "lang": "ko"},
    {"q": "1+1=?", "choices": ["1", "2", "3", "11"], "answer": 1, "lang": "ko"},
    {"q": "지구에서 가장 큰 대양은?", "choices": ["대서양", "인도양", "태평양", "북극해"], "answer": 2, "lang": "ko"},
    {"q": "역핑 플랫폼의 정산 상태 중 첫 단계는?", "choices": ["READY", "HOLD", "PAID", "APPROVED"], "answer": 1, "lang": "ko"},
    {"q": "빛의 속도는 초속 약 몇 km?", "choices": ["30만", "15만", "3만", "100만"], "answer": 0, "lang": "ko"},
    {"q": "파이썬을 만든 사람은?", "choices": ["제임스 고슬링", "귀도 반 로섬", "리누스 토르발스", "데니스 리치"], "answer": 1, "lang": "ko"},
    {"q": "역핑에서 셀러 인증 후 다음 단계는?", "choices": ["오퍼 생성", "딜 생성", "리뷰 작성", "환불 요청"], "answer": 0, "lang": "ko"},
    {"q": "What does RPS stand for?", "choices": ["Rock Paper Scissors", "Real Player Score", "Random Point System", "Rank Play Stage"], "answer": 0, "lang": "en"},
    {"q": "じゃんけんで「グー」は何?", "choices": ["パー", "チョキ", "グー(石)", "なし"], "answer": 2, "lang": "ja"},
    {"q": "猜拳中'石头'赢什么?", "choices": ["布", "剪刀", "石头", "都不赢"], "answer": 1, "lang": "zh"},
    {"q": "¿Cuál gana a tijera en piedra-papel-tijera?", "choices": ["Papel", "Piedra", "Tijera", "Ninguno"], "answer": 1, "lang": "es"},
    {"q": "HTTP 상태코드 404의 의미는?", "choices": ["서버 에러", "인증 필요", "찾을 수 없음", "리다이렉트"], "answer": 2, "lang": "ko"},
]

# ─────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────
def _calc_level(total_games: int) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if total_games >= threshold:
            return level
    return "rookie"


def _check_daily_limit(player: ArenaPlayer):
    today = date.today().isoformat()
    if player.daily_reset_date != today:
        player.daily_game_count = 0
        player.daily_reset_date = today
    if player.daily_game_count >= DAILY_LIMIT:
        raise HTTPException(status_code=429, detail=f"Daily limit reached ({DAILY_LIMIT} games)")
    player.daily_game_count += 1


def _get_or_create_player(db: Session, user) -> ArenaPlayer:
    player = db.query(ArenaPlayer).filter(ArenaPlayer.user_id == user.id).first()
    if not player:
        player = ArenaPlayer(user_id=user.id, nickname=getattr(user, "name", None) or f"player_{user.id}")
        db.add(player)
        db.flush()
    return player


# ─────────────────────────────────────────────
# 게임 핸들러
# ─────────────────────────────────────────────
RPS_MAP = {"rock": 0, "paper": 1, "scissors": 2}
RPS_NAMES = ["rock", "paper", "scissors"]

def _play_rps(player: ArenaPlayer, data: dict) -> dict:
    choice = data.get("choice", "rock").lower()
    if choice not in RPS_MAP:
        choice = "rock"
    cpu = random.choice(RPS_NAMES)
    diff = (RPS_MAP[choice] - RPS_MAP[cpu]) % 3
    if diff == 0:
        result, pts = "draw", 1
        player.rps_draws += 1
    elif diff == 1:
        result, pts = "win", 3
        player.rps_wins += 1
    else:
        result, pts = "lose", 0
        player.rps_losses += 1
    return {"result": result, "player_choice": choice, "cpu_choice": cpu, "points": pts,
            "detail": {"player": choice, "cpu": cpu}}


def _play_mjb(player: ArenaPlayer, data: dict) -> dict:
    """묵찌빠: 가위바위보 승자가 공격, 같으면 승리"""
    choice = data.get("choice", "rock").lower()
    if choice not in RPS_MAP:
        choice = "rock"
    cpu = random.choice(RPS_NAMES)
    is_attacker = data.get("is_attacker", False)

    if choice == cpu:
        # 같으면 공격자 승리
        if is_attacker:
            result, pts = "win", 5
            player.mjb_wins += 1
        else:
            result, pts = "lose", 0
            player.mjb_losses += 1
    else:
        diff = (RPS_MAP[choice] - RPS_MAP[cpu]) % 3
        if diff == 1:
            result, pts = "attack", 2  # 공격권 획득
        else:
            result, pts = "defend", 1  # 수비
    return {"result": result, "player_choice": choice, "cpu_choice": cpu, "points": pts,
            "is_attacker": is_attacker, "detail": {"player": choice, "cpu": cpu, "attacker": is_attacker}}


def _play_yut(player: ArenaPlayer, data: dict) -> dict:
    """윷놀이: 4개 윷 던지기, 결과에 따라 점수"""
    sticks = [random.choice([0, 1]) for _ in range(4)]  # 0=배, 1=등
    backs = sum(sticks)
    yut_names = {0: "모", 1: "도", 2: "개", 3: "걸", 4: "윷"}
    # 빽도 체크: 1개만 등이면서 특수조건
    if backs == 0:
        name, move, pts = "모", 5, 5
    elif backs == 1:
        name, move, pts = "도", 1, 1
    elif backs == 2:
        name, move, pts = "개", 2, 2
    elif backs == 3:
        name, move, pts = "걸", 3, 3
    else:
        name, move, pts = "윷", 4, 4
    # 윷/모 bonus: 한번 더 던질 수 있음
    bonus = name in ("윷", "모")
    if move >= 3:
        player.yut_wins += 1
    else:
        player.yut_losses += 1
    return {"result": name, "sticks": sticks, "move": move, "points": pts, "bonus_throw": bonus,
            "detail": {"sticks": sticks, "name": name, "move": move}}


def _play_math(player: ArenaPlayer, data: dict) -> dict:
    """수학배틀: 문제 출제 or 답 체크"""
    action = data.get("action", "new")
    if action == "new":
        difficulty = data.get("difficulty", 1)
        if difficulty <= 1:
            a, b = random.randint(1, 20), random.randint(1, 20)
            op = random.choice(["+", "-"])
        elif difficulty == 2:
            a, b = random.randint(2, 15), random.randint(2, 15)
            op = random.choice(["+", "-", "*"])
        else:
            a, b = random.randint(5, 50), random.randint(2, 20)
            op = random.choice(["+", "-", "*"])
        answer = eval(f"{a}{op}{b}")
        return {"result": "question", "question": f"{a} {op} {b} = ?", "points": 0,
                "detail": {"a": a, "b": b, "op": op, "answer": answer, "difficulty": difficulty}}
    else:
        # 답 체크
        user_answer = data.get("answer", None)
        correct_answer = data.get("correct_answer", None)
        time_ms = data.get("time_ms", 9999)
        if user_answer is not None and correct_answer is not None and int(user_answer) == int(correct_answer):
            pts = max(1, 10 - time_ms // 1000)
            player.math_games += 1
            if pts > player.math_best_score:
                player.math_best_score = pts
            return {"result": "correct", "points": pts, "time_ms": time_ms,
                    "detail": {"user_answer": user_answer, "correct_answer": correct_answer, "time_ms": time_ms}}
        else:
            player.math_games += 1
            return {"result": "wrong", "points": 0, "time_ms": time_ms,
                    "detail": {"user_answer": user_answer, "correct_answer": correct_answer, "time_ms": time_ms}}


def _play_quiz(player: ArenaPlayer, data: dict) -> dict:
    """상식퀴즈: 랜덤 문제 or 답 체크"""
    action = data.get("action", "new")
    lang = data.get("lang", "ko")
    if action == "new":
        pool = [q for q in QUIZ_QUESTIONS if q["lang"] == lang]
        if not pool:
            pool = QUIZ_QUESTIONS
        q = random.choice(pool)
        idx = QUIZ_QUESTIONS.index(q)
        return {"result": "question", "question_id": idx, "question": q["q"],
                "choices": q["choices"], "points": 0, "detail": {"question_id": idx}}
    else:
        qid = data.get("question_id", 0)
        user_answer = data.get("answer", -1)
        if 0 <= qid < len(QUIZ_QUESTIONS) and int(user_answer) == QUIZ_QUESTIONS[qid]["answer"]:
            pts = 5
            player.quiz_games += 1
            if pts > player.quiz_best_score:
                player.quiz_best_score = pts
            return {"result": "correct", "points": pts,
                    "detail": {"question_id": qid, "user_answer": user_answer, "correct": True}}
        else:
            player.quiz_games += 1
            correct = QUIZ_QUESTIONS[qid]["answer"] if 0 <= qid < len(QUIZ_QUESTIONS) else -1
            return {"result": "wrong", "points": 0,
                    "detail": {"question_id": qid, "user_answer": user_answer, "correct_answer": correct}}


def _play_reaction(player: ArenaPlayer, data: dict) -> dict:
    """반응속도: 클라이언트가 측정한 reaction_ms를 기록"""
    reaction_ms = data.get("reaction_ms", 9999)
    if reaction_ms < 100:
        reaction_ms = 100  # 치팅 방지
    pts = max(1, 10 - reaction_ms // 100)
    player.reaction_games += 1
    if player.reaction_best_ms == 0 or reaction_ms < player.reaction_best_ms:
        player.reaction_best_ms = reaction_ms
    return {"result": "recorded", "reaction_ms": reaction_ms, "points": pts,
            "detail": {"reaction_ms": reaction_ms}}


GAME_HANDLERS = {
    "rps": _play_rps,
    "mjb": _play_mjb,
    "yut": _play_yut,
    "math": _play_math,
    "quiz": _play_quiz,
    "reaction": _play_reaction,
}


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────

@router.post("/register")
async def arena_register(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """아레나 플레이어 등록/조회"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    player = _get_or_create_player(db, user)
    player.country = body.get("country", player.country or "KR")
    player.region = body.get("region", player.region)
    player.latitude = body.get("latitude", player.latitude)
    player.longitude = body.get("longitude", player.longitude)
    player.age_group = body.get("age_group", player.age_group)
    player.gender = body.get("gender", player.gender)
    db.commit()
    db.refresh(player)
    return {
        "id": player.id,
        "user_id": player.user_id,
        "nickname": player.nickname,
        "country": player.country,
        "region": player.region,
        "total_points": player.total_points,
        "arena_level": player.arena_level,
        "total_games": player.total_games,
        "daily_game_count": player.daily_game_count,
    }


@router.post("/play")
async def arena_play(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """통합 게임 플레이 API"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    game_type = body.get("game_type", "").lower()
    if game_type not in GAME_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid game_type. Must be one of: {', '.join(sorted(GAME_TYPES))}")

    player = _get_or_create_player(db, user)
    _check_daily_limit(player)

    handler = GAME_HANDLERS[game_type]
    game_data = body.get("data", {})
    result = handler(player, game_data)

    pts = result.get("points", 0)
    player.total_points += pts
    player.total_games += 1
    player.arena_level = _calc_level(player.total_games)

    # 게임 기록 저장
    game = ArenaGame(
        player_id=player.id,
        game_type=game_type,
        result=result.get("result", "unknown"),
        score=pts,
        detail=result.get("detail"),
        points_earned=pts,
        country=player.country,
        region=player.region,
        latitude=player.latitude,
        longitude=player.longitude,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    return {
        "game_id": game.id,
        "game_type": game_type,
        **result,
        "total_points": player.total_points,
        "arena_level": player.arena_level,
        "total_games": player.total_games,
        "daily_remaining": DAILY_LIMIT - player.daily_game_count,
    }


@router.get("/rankings")
def arena_rankings(
    game_type: str = Query("all", description="all, rps, mjb, yut, math, quiz, reaction"),
    country: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """랭킹 조회"""
    q = db.query(ArenaPlayer)

    if country:
        q = q.filter(ArenaPlayer.country == country)

    if game_type == "all":
        q = q.order_by(desc(ArenaPlayer.total_points))
    elif game_type == "rps":
        q = q.order_by(desc(ArenaPlayer.rps_wins))
    elif game_type == "mjb":
        q = q.order_by(desc(ArenaPlayer.mjb_wins))
    elif game_type == "yut":
        q = q.order_by(desc(ArenaPlayer.yut_wins))
    elif game_type == "math":
        q = q.order_by(desc(ArenaPlayer.math_best_score))
    elif game_type == "quiz":
        q = q.order_by(desc(ArenaPlayer.quiz_best_score))
    elif game_type == "reaction":
        # 반응속도: 낮을수록 좋음, 0 제외
        q = q.filter(ArenaPlayer.reaction_best_ms > 0).order_by(ArenaPlayer.reaction_best_ms)
    else:
        q = q.order_by(desc(ArenaPlayer.total_points))

    players = q.limit(limit).all()
    return {
        "game_type": game_type,
        "rankings": [
            {
                "rank": i + 1,
                "player_id": p.id,
                "nickname": p.nickname,
                "country": p.country,
                "arena_level": p.arena_level,
                "total_points": p.total_points,
                "total_games": p.total_games,
                "rps_wins": p.rps_wins,
                "mjb_wins": p.mjb_wins,
                "yut_wins": p.yut_wins,
                "math_best_score": p.math_best_score,
                "quiz_best_score": p.quiz_best_score,
                "reaction_best_ms": p.reaction_best_ms,
            }
            for i, p in enumerate(players)
        ],
    }


@router.get("/map")
def arena_map(
    db: Session = Depends(get_db),
):
    """배틀 맵 데이터 (최근 게임 위치 + 지역 통계)"""
    # 최근 100 게임
    recent = (
        db.query(ArenaGame)
        .filter(ArenaGame.latitude.isnot(None))
        .order_by(desc(ArenaGame.played_at))
        .limit(100)
        .all()
    )
    particles = [
        {
            "game_type": g.game_type,
            "lat": g.latitude,
            "lng": g.longitude,
            "country": g.country,
            "result": g.result,
            "played_at": g.played_at.isoformat() if g.played_at else None,
        }
        for g in recent
    ]

    # 지역 통계
    region_stats = db.query(ArenaRegionStats).order_by(desc(ArenaRegionStats.composite_score)).limit(50).all()
    regions = [
        {
            "level": r.level,
            "country": r.country,
            "region": r.region,
            "total_games": r.total_games,
            "total_players": r.total_players,
            "composite_score": r.composite_score,
        }
        for r in region_stats
    ]

    return {"particles": particles, "regions": regions}


@router.get("/live-feed")
def arena_live_feed(
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    """실시간 피드 (최근 게임 결과)"""
    recent = (
        db.query(ArenaGame)
        .order_by(desc(ArenaGame.played_at))
        .limit(limit)
        .all()
    )
    return {
        "feed": [
            {
                "game_id": g.id,
                "game_type": g.game_type,
                "result": g.result,
                "score": g.score,
                "country": g.country,
                "played_at": g.played_at.isoformat() if g.played_at else None,
            }
            for g in recent
        ]
    }


@router.get("/deal-banner")
def arena_deal_banner(
    db: Session = Depends(get_db),
):
    """역핑 딜 배너 (아레나에 노출할 인기 딜)"""
    from app.models import Deal
    try:
        deals = (
            db.query(Deal)
            .filter(Deal.status == "OPEN")
            .order_by(desc(Deal.created_at))
            .limit(3)
            .all()
        )
        return {
            "banners": [
                {
                    "deal_id": d.id,
                    "title": getattr(d, "title", "역핑 딜"),
                    "status": d.status,
                }
                for d in deals
            ]
        }
    except Exception:
        return {"banners": []}


@router.get("/quiz/questions")
def arena_quiz_questions(
    lang: str = Query("ko"),
    count: int = Query(5, le=20),
):
    """퀴즈 문제 목록 (답 제외)"""
    pool = [q for q in QUIZ_QUESTIONS if q["lang"] == lang]
    if not pool:
        pool = QUIZ_QUESTIONS
    selected = random.sample(pool, min(count, len(pool)))
    return {
        "questions": [
            {
                "question_id": QUIZ_QUESTIONS.index(q),
                "question": q["q"],
                "choices": q["choices"],
                "lang": q["lang"],
            }
            for q in selected
        ]
    }


@router.get("/me")
def arena_me(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """내 아레나 프로필"""
    player = db.query(ArenaPlayer).filter(ArenaPlayer.user_id == user.id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Arena player not found. Register first.")
    return {
        "id": player.id,
        "user_id": player.user_id,
        "nickname": player.nickname,
        "country": player.country,
        "region": player.region,
        "arena_level": player.arena_level,
        "total_points": player.total_points,
        "total_games": player.total_games,
        "daily_game_count": player.daily_game_count,
        "daily_remaining": DAILY_LIMIT - (player.daily_game_count or 0),
        "stats": {
            "rps": {"wins": player.rps_wins, "losses": player.rps_losses, "draws": player.rps_draws, "streak_best": player.rps_streak_best},
            "mjb": {"wins": player.mjb_wins, "losses": player.mjb_losses},
            "yut": {"wins": player.yut_wins, "losses": player.yut_losses},
            "math": {"best_score": player.math_best_score, "games": player.math_games},
            "quiz": {"best_score": player.quiz_best_score, "games": player.quiz_games},
            "reaction": {"best_ms": player.reaction_best_ms, "games": player.reaction_games},
        },
    }


@router.get("/history")
def arena_history(
    limit: int = Query(20, le=100),
    game_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """내 게임 히스토리"""
    player = db.query(ArenaPlayer).filter(ArenaPlayer.user_id == user.id).first()
    if not player:
        return {"games": []}
    q = db.query(ArenaGame).filter(ArenaGame.player_id == player.id)
    if game_type and game_type in GAME_TYPES:
        q = q.filter(ArenaGame.game_type == game_type)
    games = q.order_by(desc(ArenaGame.played_at)).limit(limit).all()
    return {
        "games": [
            {
                "game_id": g.id,
                "game_type": g.game_type,
                "result": g.result,
                "score": g.score,
                "points_earned": g.points_earned,
                "played_at": g.played_at.isoformat() if g.played_at else None,
            }
            for g in games
        ]
    }

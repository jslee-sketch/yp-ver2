# simulation_fullflow_v3_7.py
"""
v3.7 Fullflow Adapter
- 현재는 v3.6 fullflow를 내부에서 호출(delegate)하되,
  v3.5/v3.6에서 확정한 정책(판매자 철회/수락, 포인트 규칙 등)을 기본값으로 강제/주입.
- 추후 v3.7 고유 로직을 이 파일에 직접 구현하면 됨.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict

# v3.6 구현을 재사용 (shim이 있으면 우선, 없으면 reservations_v3_6로 폴백)
try:
    from simulation_fullflow_v3_6 import SimConfig as V36Config, run as v36_run  # shim 경로
except ImportError:
    from simulation_reservations_v3_6 import SimConfig as V36Config, run as v36_run  # 직접 폴백


@dataclass
class SimConfig:
    # ===== 공통 파라미터(여기 정의된 것만 노출하고 내부적으로 v3.6으로 변환) =====
    deal_id: int
    rounds: int = 1
    seed: int = 42

    # v3.5/v3.6 합의 정책(기본 고정값)
    buyer_point_on_paid: int = 20          # 결제 시 +20
    buyer_point_on_refund: int = -20       # 환불/취소 시 -20 (사유 무관, 해당 결제분 회수)
    # 판매자 의사결정: 부분판매(일부 PAID) = 철회 가능, 전량판매(전량 PAID) = 철회 불가(자동 확정)
    seller_withdraw_policy: str = "PARTIAL_ALLOWED_FULL_FORCED_ACCEPT"

    # 결제창/판매자 결정창 기본(DeadTime-aware는 내부 엔진이 다룸)
    payment_window_minutes: int = 120      # 총 2h (방장 15분 선점은 엔진이 관리)
    seller_decision_window_minutes: int = 30

    # 필요 시 v3.6의 세부 시뮬 파라미터(예: 행동비율 등)를 추가 가능
    # 현재는 v3.6 기본값 사용


def _to_v36(cfg: SimConfig) -> V36Config:
    """
    v3.7의 공개 설정을 v3.6 SimConfig로 변환.
    - v3.6에 없는 필드는 무시
    - 정책 플래그들은 v3.6 엔진이 인지하면 사용, 인지 못하면 no-op
    """
    base = {
        "deal_id": cfg.deal_id,
        "rounds": cfg.rounds,
        "seed": cfg.seed,
    }

    policy_overrides = {
        # v3.6에 qty당 포인트 로직이 있다면 끄기 위한 힌트(엔진이 지원하면 사용, 아니면 무시)
        "buyer_point_per_qty": None,
        "buyer_point_on_paid": cfg.buyer_point_on_paid,
        "buyer_point_on_refund": cfg.buyer_point_on_refund,
        "seller_withdraw_policy": cfg.seller_withdraw_policy,
        "payment_window_minutes": cfg.payment_window_minutes,
        "seller_decision_window_minutes": cfg.seller_decision_window_minutes,
    }

    # V36Config 시그니처에 맞게 안전 필터링
    v36_fields = getattr(V36Config, "__dataclass_fields__", {}).keys()  # type: ignore
    init_kwargs: Dict[str, Any] = {}
    init_kwargs.update({k: v for k, v in base.items() if k in v36_fields})
    init_kwargs.update({k: v for k, v in policy_overrides.items() if k in v36_fields})

    return V36Config(**init_kwargs)  # type: ignore


def run(cfg: SimConfig) -> dict:
    """
    v3.7 엔트리포인트.
    현재는 v3.6 엔진에 정책 오버라이드만 주입해서 실행.
    """
    v36cfg = _to_v36(cfg)
    result = v36_run(v36cfg)
    # TODO: v3.7 후처리(메타/통계/필드명 보강 등) 필요 시 여기서 수행
    return result


if __name__ == "__main__":
    # 간단 CLI
    import argparse, json, sys
    p = argparse.ArgumentParser(description="simulation fullflow v3.7 adapter")
    p.add_argument("--deal-id", type=int, required=True)
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    cfg = SimConfig(deal_id=args.deal_id, rounds=args.rounds, seed=args.seed)
    out = run(cfg)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
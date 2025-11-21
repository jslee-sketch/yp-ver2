"""v3.5 models update

Revision ID: 4d995dedbf80
Revises: 20251109_add_reservations_and_offer_counters
Create Date: 2025-11-12 14:42:30.055717
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "4d995dedbf80"
down_revision: Union[str, Sequence[str], None] = "20251109_add_reservations_and_offer_counters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------- helpers ----------
def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(name)

def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return any(ix.get("name") == name for ix in insp.get_indexes(table))
    except Exception:
        return False

def _ensure_index(name: str, table: str, cols, unique: bool = False):
    if not _has_index(table, name):
        op.create_index(name, table, cols, unique=unique)

def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return any(col["name"] == column for col in insp.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    # -----------------------------
    # event_logs
    # -----------------------------
    if not _has_table("event_logs"):
        op.create_table(
            "event_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "event_type",
                sa.Enum(
                    "DEAL_CREATED",
                    "DEAL_CLOSED",
                    "ROUND_OPENED",
                    "ROUND_CLOSED",
                    "OFFER_CREATED",
                    "OFFER_CONFIRMED",
                    "OFFER_WITHDRAWN",
                    "RESERVATION_CREATED",
                    "RESERVATION_PAID",
                    "RESERVATION_CANCELLED",
                    "RESERVATION_EXPIRED",
                    "POINT_CREDIT",
                    "POINT_DEBIT",
                    "REVIEW_CREATED",
                    "REVIEW_FLAGGED",
                    name="eventtype",
                ),
                nullable=False,
            ),
            sa.Column("actor_type", sa.String(), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("deal_id", sa.Integer(), nullable=True),
            sa.Column("round_id", sa.Integer(), nullable=True),
            sa.Column("offer_id", sa.Integer(), nullable=True),
            sa.Column("reservation_id", sa.Integer(), nullable=True),
            sa.Column("seller_id", sa.Integer(), nullable=True),
            sa.Column("buyer_id", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Float(), nullable=True),
            sa.Column("qty", sa.Integer(), nullable=True),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("idempotency_key", sa.String(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("ix_event_logs_buyer_id", "event_logs", ["buyer_id"])
    _ensure_index("ix_event_logs_created_at", "event_logs", ["created_at"])
    _ensure_index("ix_event_logs_deal_id", "event_logs", ["deal_id"])
    _ensure_index("ix_event_logs_id", "event_logs", ["id"])
    _ensure_index("ix_event_logs_idempotency_key", "event_logs", ["idempotency_key"])
    _ensure_index("ix_event_logs_offer_id", "event_logs", ["offer_id"])
    _ensure_index("ix_event_logs_reservation_id", "event_logs", ["reservation_id"])
    _ensure_index("ix_event_logs_round_id", "event_logs", ["round_id"])
    _ensure_index("ix_event_logs_seller_id", "event_logs", ["seller_id"])
    _ensure_index("ix_event_type_created", "event_logs", ["event_type", "created_at"])

    # -----------------------------
    # seller_rating_aggregates
    # -----------------------------
    if not _has_table("seller_rating_aggregates"):
        op.create_table(
            "seller_rating_aggregates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("seller_id", sa.Integer(), nullable=False),
            sa.Column("reviews_count", sa.Integer(), nullable=True),
            sa.Column("rating_raw_mean", sa.Float(), nullable=True),
            sa.Column("rating_adjusted", sa.Float(), nullable=True),
            sa.Column("last_computed_at", sa.DateTime(), nullable=True),
            sa.Column("price_fairness_avg", sa.Float(), nullable=True),
            sa.Column("quality_avg", sa.Float(), nullable=True),
            sa.Column("shipping_avg", sa.Float(), nullable=True),
            sa.Column("communication_avg", sa.Float(), nullable=True),
            sa.Column("accuracy_avg", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seller_id"),
        )
    _ensure_index("ix_seller_rating_aggregates_id", "seller_rating_aggregates", ["id"])

    # -----------------------------
    # seller_reviews
    # -----------------------------
    if not _has_table("seller_reviews"):
        op.create_table(
            "seller_reviews",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reservation_id", sa.Integer(), nullable=False),
            sa.Column("seller_id", sa.Integer(), nullable=False),
            sa.Column("buyer_id", sa.Integer(), nullable=False),
            sa.Column("price_fairness", sa.Integer(), nullable=False),
            sa.Column("quality", sa.Integer(), nullable=False),
            sa.Column("shipping", sa.Integer(), nullable=False),
            sa.Column("communication", sa.Integer(), nullable=False),
            sa.Column("accuracy", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("media_count", sa.Integer(), nullable=True),
            sa.Column("is_verified", sa.Boolean(), nullable=True),
            sa.Column("helpful_yes", sa.Integer(), nullable=True),
            sa.Column("helpful_no", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reservation_id", "buyer_id", name="uq_review_once_per_buyer_reservation"),
        )
    _ensure_index("ix_review_seller_created", "seller_reviews", ["seller_id", "created_at"])
    _ensure_index("ix_seller_reviews_buyer_id", "seller_reviews", ["buyer_id"])
    _ensure_index("ix_seller_reviews_id", "seller_reviews", ["id"])
    _ensure_index("ix_seller_reviews_reservation_id", "seller_reviews", ["reservation_id"])
    _ensure_index("ix_seller_reviews_seller_id", "seller_reviews", ["seller_id"])

    # -----------------------------
    # buyer_deposits
    # -----------------------------
    if not _has_column("buyer_deposits", "refund_reason"):
        op.add_column("buyer_deposits", sa.Column("refund_reason", sa.String(), nullable=True))
    # NULL -> 'held' 정리(있으면)
    op.execute(sa.text("UPDATE buyer_deposits SET status='held' WHERE status IS NULL"))
    # SQLite: NOT NULL은 배치모드로
    with op.batch_alter_table("buyer_deposits", recreate="always") as batch:
        batch.alter_column("status", existing_type=sa.String(), nullable=False)
    _ensure_index("ix_deposit_deal_buyer", "buyer_deposits", ["deal_id", "buyer_id"])

    # -----------------------------
    # buyers
    # -----------------------------
    if not _has_column("buyers", "trust_tier"):
        op.add_column("buyers", sa.Column("trust_tier", sa.String(), nullable=True))
    if not _has_column("buyers", "tier_computed_at"):
        op.add_column("buyers", sa.Column("tier_computed_at", sa.DateTime(), nullable=True))

    # -----------------------------
    # deal_participants  *** 핵심 오류 처리 구간 ***
    # -----------------------------
    # (1) 유니크 제약을 막는 중복 데이터 제거
    op.execute(
        sa.text(
            """
            DELETE FROM deal_participants
            WHERE id NOT IN (
                SELECT MIN(id) FROM deal_participants GROUP BY deal_id, buyer_id
            )
            """
        )
    )
    # (2) 배치모드 재생성하면서 유니크 제약 + 인덱스 동시 추가
    with op.batch_alter_table("deal_participants", recreate="always") as batch:
        # 이미 존재할 수 있으니 try/except로 감싸도 되지만, 재생성에서 안전하게 덮습니다.
        batch.create_unique_constraint("uq_participation_once_per_deal", ["deal_id", "buyer_id"])
        batch.create_index("ix_participation_deal", ["deal_id"])

    # -----------------------------
    # deals
    # -----------------------------
    if not _has_column("deals", "product_norm"):
        op.add_column("deals", sa.Column("product_norm", sa.String(), nullable=True))
    if not _has_column("deals", "options_norm"):
        op.add_column("deals", sa.Column("options_norm", sa.String(), nullable=True))
    if not _has_column("deals", "fingerprint_hash"):
        op.add_column("deals", sa.Column("fingerprint_hash", sa.String(), nullable=True))
    _ensure_index("ix_deal_fingerprint", "deals", ["fingerprint_hash"])
    _ensure_index("ix_deal_status_deadline", "deals", ["status", "deadline_at"])

    # -----------------------------
    # offers
    # -----------------------------
    if not _has_column("offers", "decision_state"):
        op.add_column(
            "offers",
            sa.Column(
                "decision_state",
                sa.Enum("PENDING", "CONFIRMED", "WITHDRAWN", "AUTO_WITHDRAWN", "AUTO_CONFIRMED", name="offerdecisionstate"),
                nullable=True,
            ),
        )
    if not _has_column("offers", "decision_deadline_at"):
        op.add_column("offers", sa.Column("decision_deadline_at", sa.DateTime(), nullable=True))
    if not _has_column("offers", "decision_made_at"):
        op.add_column("offers", sa.Column("decision_made_at", sa.DateTime(), nullable=True))
    if not _has_column("offers", "decision_reason"):
        op.add_column("offers", sa.Column("decision_reason", sa.String(), nullable=True))

    _ensure_index("ix_offer_deal_active_deadline", "offers", ["deal_id", "is_active", "deadline_at"])
    _ensure_index("ix_offer_deal_confirmed", "offers", ["deal_id", "is_confirmed"])
    _ensure_index("ix_offer_seller", "offers", ["seller_id"])

    # 기존 FK 재정의(있다면 무시되고, 없으면 생성)
    try:
        op.drop_constraint(None, "offers", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint(None, "offers", type_="foreignkey")
    except Exception:
        pass
    try:
        op.create_foreign_key(None, "offers", "sellers", ["seller_id"], ["id"], ondelete="CASCADE")
    except Exception:
        pass
    try:
        op.create_foreign_key(None, "offers", "deals", ["deal_id"], ["id"], ondelete="CASCADE")
    except Exception:
        pass

    # -----------------------------
    # point_transactions
    # -----------------------------
    if not _has_column("point_transactions", "idempotency_key"):
        op.add_column("point_transactions", sa.Column("idempotency_key", sa.String(), nullable=True))
    _ensure_index("ix_point_transactions_idempotency_key", "point_transactions", ["idempotency_key"], unique=True)
    _ensure_index("ix_point_user_created", "point_transactions", ["user_type", "user_id", "created_at"])

    # -----------------------------
    # reservations
    # -----------------------------
    _ensure_index("ix_resv_deal_status", "reservations", ["deal_id", "status"])

    # -----------------------------
    # sellers
    # -----------------------------
    if not _has_column("sellers", "level"):
        op.add_column("sellers", sa.Column("level", sa.Integer(), nullable=False, server_default="6"))
    # (원하면 server_default 제거 배치 재생성 가능)


def downgrade() -> None:
    # sellers
    if _has_column("sellers", "level"):
        op.drop_column("sellers", "level")

    # reservations
    if _has_index("reservations", "ix_resv_deal_status"):
        op.drop_index("ix_resv_deal_status", table_name="reservations")

    # point_transactions
    if _has_index("point_transactions", "ix_point_user_created"):
        op.drop_index("ix_point_user_created", table_name="point_transactions")
    if _has_index("point_transactions", "ix_point_transactions_idempotency_key"):
        op.drop_index("ix_point_transactions_idempotency_key", table_name="point_transactions")
    if _has_column("point_transactions", "idempotency_key"):
        op.drop_column("point_transactions", "idempotency_key")

    # offers
    if _has_index("offers", "ix_offer_seller"):
        op.drop_index("ix_offer_seller", table_name="offers")
    if _has_index("offers", "ix_offer_deal_confirmed"):
        op.drop_index("ix_offer_deal_confirmed", table_name="offers")
    if _has_index("offers", "ix_offer_deal_active_deadline"):
        op.drop_index("ix_offer_deal_active_deadline", table_name="offers")
    for col in ["decision_reason", "decision_made_at", "decision_deadline_at", "decision_state"]:
        if _has_column("offers", col):
            op.drop_column("offers", col)

    # deals
    if _has_index("deals", "ix_deal_status_deadline"):
        op.drop_index("ix_deal_status_deadline", table_name="deals")
    if _has_index("deals", "ix_deal_fingerprint"):
        op.drop_index("ix_deal_fingerprint", table_name="deals")
    for col in ["fingerprint_hash", "options_norm", "product_norm"]:
        if _has_column("deals", col):
            op.drop_column("deals", col)

    # deal_participants (배치모드로 제약/인덱스 제거)
    with op.batch_alter_table("deal_participants", recreate="always") as batch:
        try:
            batch.drop_constraint("uq_participation_once_per_deal", type_="unique")
        except Exception:
            pass
        try:
            batch.drop_index("ix_participation_deal")
        except Exception:
            pass

    # buyers
    for col in ["tier_computed_at", "trust_tier"]:
        if _has_column("buyers", col):
            op.drop_column("buyers", col)

    # buyer_deposits
    with op.batch_alter_table("buyer_deposits", recreate="always") as batch:
        batch.alter_column("status", existing_type=sa.String(), nullable=True)
    if _has_index("buyer_deposits", "ix_deposit_deal_buyer"):
        op.drop_index("ix_deposit_deal_buyer", table_name="buyer_deposits")
    if _has_column("buyer_deposits", "refund_reason"):
        op.drop_column("buyer_deposits", "refund_reason")

    # seller_reviews
    if _has_index("seller_reviews", "ix_seller_reviews_seller_id"):
        op.drop_index("ix_seller_reviews_seller_id", table_name="seller_reviews")
    if _has_index("seller_reviews", "ix_seller_reviews_reservation_id"):
        op.drop_index("ix_seller_reviews_reservation_id", table_name="seller_reviews")
    if _has_index("seller_reviews", "ix_seller_reviews_id"):
        op.drop_index("ix_seller_reviews_id", table_name="seller_reviews")
    if _has_index("seller_reviews", "ix_seller_reviews_buyer_id"):
        op.drop_index("ix_seller_reviews_buyer_id", table_name="seller_reviews")
    if _has_index("seller_reviews", "ix_review_seller_created"):
        op.drop_index("ix_review_seller_created", table_name="seller_reviews")
    if _has_table("seller_reviews"):
        op.drop_table("seller_reviews")

    # seller_rating_aggregates
    if _has_index("seller_rating_aggregates", "ix_seller_rating_aggregates_id"):
        op.drop_index("ix_seller_rating_aggregates_id", table_name="seller_rating_aggregates")
    if _has_table("seller_rating_aggregates"):
        op.drop_table("seller_rating_aggregates")

    # event_logs
    if _has_index("event_logs", "ix_event_type_created"):
        op.drop_index("ix_event_type_created", table_name="event_logs")
    for ix in [
        "ix_event_logs_seller_id",
        "ix_event_logs_round_id",
        "ix_event_logs_reservation_id",
        "ix_event_logs_offer_id",
        "ix_event_logs_idempotency_key",
        "ix_event_logs_id",
        "ix_event_logs_deal_id",
        "ix_event_logs_created_at",
        "ix_event_logs_buyer_id",
    ]:
        if _has_index("event_logs", ix):
            op.drop_index(ix, table_name="event_logs")
    if _has_table("event_logs"):
        op.drop_table("event_logs")
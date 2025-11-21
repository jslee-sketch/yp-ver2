# alembic/versions/20251109_add_reservations_and_offer_counters.py
from alembic import op
import sqlalchemy as sa

# --- revision identifiers ---
revision = "20251109_add_reservations_and_offer_counters"
down_revision = "0ccbaaa1c59d"  # 당신 프로젝트의 직전 리비전
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # 1) reservations 테이블 생성 (없을 때만)
    if not _has_table(bind, "reservations"):
        op.create_table(
            "reservations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("offer_id", sa.Integer(), sa.ForeignKey("offers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("paid_at", sa.DateTime()),
            sa.Column("cancelled_at", sa.DateTime()),
            sa.Column("expired_at", sa.DateTime()),
            sa.Column("idempotency_key", sa.String(length=64)),
        )

    # 2) offers에 sold_qty / reserved_qty 추가 (없을 때만) — SQLite 대응 위해 batch_alter 사용
    need_sold = not _has_column(bind, "offers", "sold_qty")
    need_reserved = not _has_column(bind, "offers", "reserved_qty")

    if need_sold or need_reserved:
        with op.batch_alter_table("offers") as batch:
            if need_sold:
                batch.add_column(sa.Column("sold_qty", sa.Integer(), nullable=False, server_default="0"))
            if need_reserved:
                batch.add_column(sa.Column("reserved_qty", sa.Integer(), nullable=False, server_default="0"))

        # server_default 제거(원하면)
        with op.batch_alter_table("offers") as batch:
            if need_sold:
                batch.alter_column("sold_qty", server_default=None)
            if need_reserved:
                batch.alter_column("reserved_qty", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()

    # offers 컬럼 되돌리기(있을 때만)
    has_sold = _has_column(bind, "offers", "sold_qty")
    has_reserved = _has_column(bind, "offers", "reserved_qty")

    if has_sold or has_reserved:
        with op.batch_alter_table("offers") as batch:
            if has_reserved:
                batch.drop_column("reserved_qty")
            if has_sold:
                batch.drop_column("sold_qty")

    # reservations 테이블 드롭(있을 때만)
    if _has_table(bind, "reservations"):
        op.drop_table("reservations")
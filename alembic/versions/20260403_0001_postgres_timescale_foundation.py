from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260403_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "samples_raw",
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=False),
        sa.Column("p_kw", sa.Float(), nullable=True),
        sa.Column("v_ac", sa.Float(), nullable=True),
        sa.Column("v_dc", sa.Float(), nullable=True),
        sa.Column("i_dc", sa.Float(), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("serial", sa.Text(), nullable=True),
        sa.Column("gateway_swver", sa.Text(), nullable=True),
        sa.Column("gateway_ip", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ts", "panel_id", name="pk_samples_raw"),
    )
    op.create_index("idx_samples_raw_ts", "samples_raw", ["ts"], unique=False)
    op.create_index("idx_samples_raw_panel_ts", "samples_raw", ["panel_id", "ts"], unique=False)

    op.create_table(
        "house_raw",
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("production_kw", sa.Float(), nullable=True),
        sa.Column("consumption_kw", sa.Float(), nullable=True),
        sa.Column("net_kw", sa.Float(), nullable=True),
        sa.Column("v_sys", sa.Float(), nullable=True),
        sa.Column("v_l1", sa.Float(), nullable=True),
        sa.Column("v_l2", sa.Float(), nullable=True),
        sa.Column("gateway_swver", sa.Text(), nullable=True),
        sa.Column("gateway_ip", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ts", name="pk_house_raw"),
    )


def downgrade() -> None:
    op.drop_table("house_raw")
    op.drop_index("idx_samples_raw_panel_ts", table_name="samples_raw")
    op.drop_index("idx_samples_raw_ts", table_name="samples_raw")
    op.drop_table("samples_raw")

# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0004"
down_revision: Union[str, None] = "20260404_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "charger_samples",
        sa.Column("site_id", sa.Text(), nullable=False, server_default="default"),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_connected", sa.Boolean(), nullable=True),
        sa.Column("contactor_closed", sa.Boolean(), nullable=True),
        sa.Column("evse_state", sa.Integer(), nullable=True),
        sa.Column("current_a", sa.Float(), nullable=True),
        sa.Column("voltage_v", sa.Float(), nullable=True),
        sa.Column("power_kw", sa.Float(), nullable=True),
        sa.Column("session_energy_wh", sa.Float(), nullable=True),
        sa.Column("lifetime_energy_wh", sa.Float(), nullable=True),
        sa.Column("pcba_temp_c", sa.Float(), nullable=True),
        sa.Column("handle_temp_c", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_charger_samples_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("site_id", "ts", name="pk_charger_samples"),
    )
    op.create_index("idx_charger_samples_ts", "charger_samples", ["ts"], unique=False)
    op.create_index("idx_charger_samples_site_ts", "charger_samples", ["site_id", "ts"], unique=False)

    if is_postgres:
        op.execute("SELECT create_hypertable('charger_samples', 'ts', if_not_exists => TRUE)")
        op.execute(
            "SELECT set_integer_now_func('charger_samples', 'unix_now_seconds', replace_if_exists => TRUE)"
        )
        op.execute(
            "SELECT add_retention_policy('charger_samples', 31536000::BIGINT, if_not_exists => TRUE)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("SELECT remove_retention_policy('charger_samples', if_exists => TRUE)")

    op.drop_index("idx_charger_samples_site_ts", table_name="charger_samples")
    op.drop_index("idx_charger_samples_ts", table_name="charger_samples")
    op.drop_table("charger_samples")

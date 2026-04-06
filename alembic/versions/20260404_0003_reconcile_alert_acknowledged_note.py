# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0003"
down_revision: Union[str, None] = "20260403_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    alert_columns = {column["name"] for column in inspector.get_columns("alerts")}

    if "acknowledged_note" not in alert_columns:
        op.add_column("alerts", sa.Column("acknowledged_note", sa.Text(), nullable=True))


def downgrade() -> None:
    return None

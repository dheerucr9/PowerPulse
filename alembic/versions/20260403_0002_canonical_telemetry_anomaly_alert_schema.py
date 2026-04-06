# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260403_0002"
down_revision: Union[str, None] = "20260403_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "sites",
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("site_name", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("site_id", name="pk_sites"),
    )

    op.create_table(
        "site_panels",
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=False),
        sa.Column("serial", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_state", sa.Text(), nullable=True),
        sa.Column("first_seen_ts", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_ts", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_site_panels_site_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_id", "panel_id", name="pk_site_panels"),
    )
    op.create_index("idx_site_panels_serial", "site_panels", ["serial"], unique=False)

    op.create_table(
        "site_power_samples",
        sa.Column("site_id", sa.Text(), nullable=False, server_default="default"),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("production_kw", sa.Float(), nullable=True),
        sa.Column("consumption_kw", sa.Float(), nullable=True),
        sa.Column("net_kw", sa.Float(), nullable=True),
        sa.Column("v_sys", sa.Float(), nullable=True),
        sa.Column("v_l1", sa.Float(), nullable=True),
        sa.Column("v_l2", sa.Float(), nullable=True),
        sa.Column("gateway_swver", sa.Text(), nullable=True),
        sa.Column("gateway_ip", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_site_power_samples_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("site_id", "ts", name="pk_site_power_samples"),
    )
    op.create_index("idx_site_power_samples_ts", "site_power_samples", ["ts"], unique=False)
    op.create_index("idx_site_power_samples_site_ts", "site_power_samples", ["site_id", "ts"], unique=False)

    op.create_table(
        "panel_power_samples",
        sa.Column("site_id", sa.Text(), nullable=False, server_default="default"),
        sa.Column("panel_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("p_kw", sa.Float(), nullable=True),
        sa.Column("v_ac", sa.Float(), nullable=True),
        sa.Column("v_dc", sa.Float(), nullable=True),
        sa.Column("i_dc", sa.Float(), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("serial", sa.Text(), nullable=True),
        sa.Column("gateway_swver", sa.Text(), nullable=True),
        sa.Column("gateway_ip", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_panel_power_samples_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("site_id", "panel_id", "ts", name="pk_panel_power_samples"),
    )
    op.create_index("idx_panel_power_samples_ts", "panel_power_samples", ["ts"], unique=False)
    op.create_index("idx_panel_power_samples_panel_ts", "panel_power_samples", ["panel_id", "ts"], unique=False)
    op.create_index("idx_panel_power_samples_site_panel_ts", "panel_power_samples", ["site_id", "panel_id", "ts"], unique=False)

    op.create_table(
        "site_power_baselines",
        sa.Column("baseline_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("bucket_start_ts", sa.BigInteger(), nullable=False),
        sa.Column("bucket_granularity_seconds", sa.Integer(), nullable=False),
        sa.Column("baseline_kw", sa.Float(), nullable=False),
        sa.Column("baseline_stddev_kw", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("metric IN ('production_kw','consumption_kw','net_kw')", name="ck_site_power_baselines_metric"),
        sa.CheckConstraint("bucket_granularity_seconds > 0", name="ck_site_power_baselines_granularity"),
        sa.CheckConstraint("sample_count >= 0", name="ck_site_power_baselines_sample_count"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_site_power_baselines_site_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("baseline_id", name="pk_site_power_baselines"),
        sa.UniqueConstraint(
            "site_id",
            "metric",
            "bucket_start_ts",
            "bucket_granularity_seconds",
            name="uq_site_power_baselines_bucket",
        ),
    )

    op.create_table(
        "panel_power_baselines",
        sa.Column("baseline_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("bucket_start_ts", sa.BigInteger(), nullable=False),
        sa.Column("bucket_granularity_seconds", sa.Integer(), nullable=False),
        sa.Column("baseline_kw", sa.Float(), nullable=False),
        sa.Column("baseline_stddev_kw", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("bucket_granularity_seconds > 0", name="ck_panel_power_baselines_granularity"),
        sa.CheckConstraint("sample_count >= 0", name="ck_panel_power_baselines_sample_count"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_panel_power_baselines_site_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("baseline_id", name="pk_panel_power_baselines"),
        sa.UniqueConstraint(
            "site_id",
            "panel_id",
            "metric",
            "bucket_start_ts",
            "bucket_granularity_seconds",
            name="uq_panel_power_baselines_bucket",
        ),
    )

    op.create_table(
        "anomalies",
        sa.Column("anomaly_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=True),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="open"),
        sa.Column("detected_at_ts", sa.BigInteger(), nullable=False),
        sa.Column("sample_ts", sa.BigInteger(), nullable=False),
        sa.Column("bucket_start_ts", sa.BigInteger(), nullable=True),
        sa.Column("bucket_end_ts", sa.BigInteger(), nullable=True),
        sa.Column("baseline_kw", sa.Float(), nullable=True),
        sa.Column("observed_kw", sa.Float(), nullable=True),
        sa.Column("deviation_kw", sa.Float(), nullable=True),
        sa.Column("deviation_pct", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("panel_state", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("source IN ('site','panel')", name="ck_anomalies_source"),
        sa.CheckConstraint("direction IN ('above','below')", name="ck_anomalies_direction"),
        sa.CheckConstraint("severity IN ('info','warning','critical')", name="ck_anomalies_severity"),
        sa.CheckConstraint("state IN ('open','acknowledged','resolved','dismissed')", name="ck_anomalies_state"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_anomalies_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("anomaly_id", name="pk_anomalies"),
        sa.UniqueConstraint("site_id", "panel_id", "metric", "sample_ts", "direction", name="uq_anomalies_dedupe"),
    )
    op.create_index("idx_anomalies_site_detected_ts", "anomalies", ["site_id", "detected_at_ts"], unique=False)
    op.create_index("idx_anomalies_open_severity", "anomalies", ["state", "severity"], unique=False)

    op.create_table(
        "anomaly_evidence",
        sa.Column("evidence_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anomaly_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("reference_ts", sa.BigInteger(), nullable=True),
        sa.Column("window_start_ts", sa.BigInteger(), nullable=True),
        sa.Column("window_end_ts", sa.BigInteger(), nullable=True),
        sa.Column("metric", sa.Text(), nullable=True),
        sa.Column("baseline_kw", sa.Float(), nullable=True),
        sa.Column("observed_kw", sa.Float(), nullable=True),
        sa.Column("deviation_kw", sa.Float(), nullable=True),
        sa.Column("deviation_pct", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("panel_state", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("sample_count IS NULL OR sample_count >= 0", name="ck_anomaly_evidence_sample_count"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["anomalies.anomaly_id"], name="fk_anomaly_evidence_anomaly_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_anomaly_evidence_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_anomaly_evidence"),
    )
    op.create_index("idx_anomaly_evidence_anomaly_id", "anomaly_evidence", ["anomaly_id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anomaly_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("panel_id", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("first_seen_ts", sa.BigInteger(), nullable=False),
        sa.Column("last_seen_ts", sa.BigInteger(), nullable=False),
        sa.Column("detected_at_ts", sa.BigInteger(), nullable=False),
        sa.Column("last_observed_ts", sa.BigInteger(), nullable=True),
        sa.Column("baseline_kw", sa.Float(), nullable=True),
        sa.Column("observed_kw", sa.Float(), nullable=True),
        sa.Column("deviation_kw", sa.Float(), nullable=True),
        sa.Column("deviation_pct", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("affected_panel_count", sa.Integer(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("explanation_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Text(), nullable=True),
        sa.Column("acknowledged_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('production','consumption')", name="ck_alerts_kind"),
        sa.CheckConstraint("severity IN ('info','warning','critical')", name="ck_alerts_severity"),
        sa.CheckConstraint("status IN ('open','acknowledged','resolved','suppressed')", name="ck_alerts_status"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["anomalies.anomaly_id"], name="fk_alerts_anomaly_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], name="fk_alerts_site_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("alert_id", name="pk_alerts"),
    )
    op.create_index("idx_alerts_status_severity", "alerts", ["status", "severity"], unique=False)
    op.create_index("idx_alerts_site_detected_ts", "alerts", ["site_id", "detected_at_ts"], unique=False)
    op.create_index("idx_alerts_dedupe_status", "alerts", ["dedupe_key", "status"], unique=False)

    op.create_table(
        "alert_acknowledgements",
        sa.Column("ack_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("acknowledged_by", sa.Text(), nullable=False),
        sa.Column("previous_status", sa.Text(), nullable=True),
        sa.Column("new_status", sa.Text(), nullable=False, server_default="acknowledged"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("new_status IN ('acknowledged','resolved','suppressed')", name="ck_alert_acknowledgements_new_status"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"], name="fk_alert_acknowledgements_alert_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ack_id", name="pk_alert_acknowledgements"),
    )
    op.create_index("idx_alert_acknowledgements_alert_id", "alert_acknowledgements", ["alert_id"], unique=False)

    op.execute("INSERT INTO sites (site_id, site_name, timezone) VALUES ('default', 'Default Site', 'UTC')")

    if is_postgres:
        op.execute("SELECT create_hypertable('site_power_samples', 'ts', if_not_exists => TRUE)")
        op.execute("SELECT create_hypertable('panel_power_samples', 'ts', if_not_exists => TRUE)")
        op.execute(
            """
            CREATE OR REPLACE FUNCTION unix_now_seconds()
            RETURNS BIGINT
            LANGUAGE SQL
            STABLE
            AS $$
                SELECT EXTRACT(EPOCH FROM NOW())::BIGINT
            $$
            """
        )
        op.execute(
            "SELECT set_integer_now_func('site_power_samples', 'unix_now_seconds', replace_if_exists => TRUE)"
        )
        op.execute(
            "SELECT set_integer_now_func('panel_power_samples', 'unix_now_seconds', replace_if_exists => TRUE)"
        )
        op.execute(
            "SELECT add_retention_policy('site_power_samples', 31536000::BIGINT, if_not_exists => TRUE)"
        )
        op.execute(
            "SELECT add_retention_policy('panel_power_samples', 31536000::BIGINT, if_not_exists => TRUE)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("SELECT remove_retention_policy('site_power_samples', if_exists => TRUE)")
        op.execute("SELECT remove_retention_policy('panel_power_samples', if_exists => TRUE)")
        op.execute("DROP FUNCTION IF EXISTS unix_now_seconds()")

    op.drop_index("idx_alert_acknowledgements_alert_id", table_name="alert_acknowledgements")
    op.drop_table("alert_acknowledgements")

    op.drop_index("idx_alerts_site_detected_ts", table_name="alerts")
    op.drop_index("idx_alerts_status_severity", table_name="alerts")
    op.drop_index("idx_alerts_dedupe_status", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("idx_anomaly_evidence_anomaly_id", table_name="anomaly_evidence")
    op.drop_table("anomaly_evidence")

    op.drop_index("idx_anomalies_open_severity", table_name="anomalies")
    op.drop_index("idx_anomalies_site_detected_ts", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_table("panel_power_baselines")
    op.drop_table("site_power_baselines")

    op.drop_index("idx_panel_power_samples_site_panel_ts", table_name="panel_power_samples")
    op.drop_index("idx_panel_power_samples_panel_ts", table_name="panel_power_samples")
    op.drop_index("idx_panel_power_samples_ts", table_name="panel_power_samples")
    op.drop_table("panel_power_samples")

    op.drop_index("idx_site_power_samples_site_ts", table_name="site_power_samples")
    op.drop_index("idx_site_power_samples_ts", table_name="site_power_samples")
    op.drop_table("site_power_samples")

    op.drop_index("idx_site_panels_serial", table_name="site_panels")
    op.drop_table("site_panels")
    op.drop_table("sites")

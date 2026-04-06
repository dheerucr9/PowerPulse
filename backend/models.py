# pyright: reportMissingImports=false

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (PrimaryKeyConstraint("site_id", name="pk_sites"),)

    site_id: Mapped[str] = mapped_column(Text, nullable=False)
    site_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UTC'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SitePanel(Base):
    __tablename__ = "site_panels"
    __table_args__ = (PrimaryKeyConstraint("site_id", "panel_id", name="pk_site_panels"),)

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id", name="fk_site_panels_site_id", ondelete="CASCADE"), nullable=False)
    panel_id: Mapped[str] = mapped_column(Text, nullable=False)
    serial: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_seen_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SitePowerSample(Base):
    __tablename__ = "site_power_samples"
    __table_args__ = (PrimaryKeyConstraint("site_id", "ts", name="pk_site_power_samples"),)

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", name="fk_site_power_samples_site_id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'default'"),
    )
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    production_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    consumption_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_sys: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_l1: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_l2: Mapped[float | None] = mapped_column(Float, nullable=True)
    gateway_swver: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PanelPowerSample(Base):
    __tablename__ = "panel_power_samples"
    __table_args__ = (PrimaryKeyConstraint("site_id", "panel_id", "ts", name="pk_panel_power_samples"),)

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", name="fk_panel_power_samples_site_id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'default'"),
    )
    panel_id: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    p_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_ac: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_dc: Mapped[float | None] = mapped_column(Float, nullable=True)
    i_dc: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    serial: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_swver: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ChargerSample(Base):
    __tablename__ = "charger_samples"
    __table_args__ = (PrimaryKeyConstraint("site_id", "ts", name="pk_charger_samples"),)

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", name="fk_charger_samples_site_id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'default'"),
    )
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vehicle_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    contactor_closed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evse_state: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_energy_wh: Mapped[float | None] = mapped_column(Float, nullable=True)
    lifetime_energy_wh: Mapped[float | None] = mapped_column(Float, nullable=True)
    pcba_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    handle_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)


class SitePowerBaseline(Base):
    __tablename__ = "site_power_baselines"
    __table_args__ = (
        CheckConstraint("metric IN ('production_kw','consumption_kw','net_kw')", name="ck_site_power_baselines_metric"),
        CheckConstraint("bucket_granularity_seconds > 0", name="ck_site_power_baselines_granularity"),
        CheckConstraint("sample_count >= 0", name="ck_site_power_baselines_sample_count"),
        PrimaryKeyConstraint("baseline_id", name="pk_site_power_baselines"),
        UniqueConstraint(
            "site_id",
            "metric",
            "bucket_start_ts",
            "bucket_granularity_seconds",
            name="uq_site_power_baselines_bucket",
        ),
    )

    baseline_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id", name="fk_site_power_baselines_site_id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_start_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bucket_granularity_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_kw: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_stddev_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PanelPowerBaseline(Base):
    __tablename__ = "panel_power_baselines"
    __table_args__ = (
        CheckConstraint("bucket_granularity_seconds > 0", name="ck_panel_power_baselines_granularity"),
        CheckConstraint("sample_count >= 0", name="ck_panel_power_baselines_sample_count"),
        PrimaryKeyConstraint("baseline_id", name="pk_panel_power_baselines"),
        UniqueConstraint(
            "site_id",
            "panel_id",
            "metric",
            "bucket_start_ts",
            "bucket_granularity_seconds",
            name="uq_panel_power_baselines_bucket",
        ),
    )

    baseline_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id", name="fk_panel_power_baselines_site_id", ondelete="CASCADE"), nullable=False)
    panel_id: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_start_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bucket_granularity_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_kw: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_stddev_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        CheckConstraint("source IN ('site','panel')", name="ck_anomalies_source"),
        CheckConstraint("direction IN ('above','below')", name="ck_anomalies_direction"),
        CheckConstraint("severity IN ('info','warning','critical')", name="ck_anomalies_severity"),
        CheckConstraint("state IN ('open','acknowledged','resolved','dismissed')", name="ck_anomalies_state"),
        PrimaryKeyConstraint("anomaly_id", name="pk_anomalies"),
        UniqueConstraint("site_id", "panel_id", "metric", "sample_ts", "direction", name="uq_anomalies_dedupe"),
    )

    anomaly_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id", name="fk_anomalies_site_id", ondelete="RESTRICT"), nullable=False)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    detected_at_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sample_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bucket_start_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bucket_end_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    baseline_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    panel_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class AnomalyEvidence(Base):
    __tablename__ = "anomaly_evidence"
    __table_args__ = (
        CheckConstraint("sample_count IS NULL OR sample_count >= 0", name="ck_anomaly_evidence_sample_count"),
        PrimaryKeyConstraint("evidence_id", name="pk_anomaly_evidence"),
    )

    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(
        ForeignKey("anomalies.anomaly_id", name="fk_anomaly_evidence_anomaly_id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", name="fk_anomaly_evidence_site_id", ondelete="RESTRICT"),
        nullable=False,
    )
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    window_start_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    window_end_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    metric: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    panel_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("kind IN ('production','consumption')", name="ck_alerts_kind"),
        CheckConstraint("severity IN ('info','warning','critical')", name="ck_alerts_severity"),
        CheckConstraint("status IN ('open','acknowledged','resolved','suppressed')", name="ck_alerts_status"),
        PrimaryKeyConstraint("alert_id", name="pk_alerts"),
    )

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int | None] = mapped_column(
        ForeignKey("anomalies.anomaly_id", name="fk_alerts_anomaly_id", ondelete="SET NULL"),
        nullable=True,
    )
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id", name="fk_alerts_site_id", ondelete="RESTRICT"), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_seen_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detected_at_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_observed_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    baseline_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_panel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    acknowledged_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertAcknowledgement(Base):
    __tablename__ = "alert_acknowledgements"
    __table_args__ = (
        CheckConstraint("new_status IN ('acknowledged','resolved','suppressed')", name="ck_alert_acknowledgements_new_status"),
        PrimaryKeyConstraint("ack_id", name="pk_alert_acknowledgements"),
    )

    ack_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.alert_id", name="fk_alert_acknowledgements_alert_id", ondelete="CASCADE"),
        nullable=False,
    )
    acknowledged_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    acknowledged_by: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'acknowledged'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

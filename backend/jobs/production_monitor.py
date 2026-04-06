"""
Production monitor — runs every 60 seconds.
Checks for:
  1. Per-panel zero production during daylight hours
  2. Panel offline (no data seen for OFFLINE_THRESHOLD_SECONDS during daylight)
  3. Gateway unreachable / auth failure

Sunrise/sunset uses the same algorithm as production_intelligence.py.
Alerts use the AlertLifecycleService deduplication so repeated occurrences
collapse into a single open alert.
"""

from __future__ import annotations

import math
import time
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta, timezone
from typing import TYPE_CHECKING, TypedDict, Any

from sqlalchemy import text

from .. import settings
from ..repositories.alerts import AlertsRepository
from ..repositories.telemetry import TelemetryRepository
from ..services.alerts import AlertLifecycleService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SessionClass

SITE_ID = "default"

ZERO_PROD_THRESHOLD_SECONDS = 600
OFFLINE_THRESHOLD_SECONDS = 600
CRITICAL_OFFLINE_SECONDS = 1800

MODEL_VERSION = "production-monitor-v1"


@dataclass
class DaylightStatus:
    is_daylight: bool
    sunrise_ts: int | None
    sunset_ts: int | None
    timezone: str
    method: str


def _get_tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(settings.TZ_NAME or "UTC")
    except Exception:
        return timezone.utc


def _solar_daylight_status(ts: int) -> DaylightStatus:
    tz = _get_tz()
    now_local = datetime.fromtimestamp(ts, tz=tz)
    latitude = _to_float(settings.LATITUDE)
    longitude = _to_float(settings.LONGITUDE)

    fallback_dawn = datetime.combine(now_local.date(), dtime(hour=6, minute=0), tzinfo=tz)
    fallback_dusk = datetime.combine(now_local.date(), dtime(hour=18, minute=30), tzinfo=tz)

    if latitude is None or longitude is None:
        return DaylightStatus(
            is_daylight=fallback_dawn <= now_local <= fallback_dusk,
            sunrise_ts=int(fallback_dawn.timestamp()),
            sunset_ts=int(fallback_dusk.timestamp()),
            timezone=getattr(tz, "key", "UTC"),
            method="fallback_fixed_window",
        )

    day_of_year = now_local.timetuple().tm_yday
    gamma = (2.0 * math.pi / 365.0) * (day_of_year - 1)
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.00148 * math.sin(2 * gamma)
    )

    lat_rad = math.radians(latitude)
    cos_zenith = math.cos(math.radians(90.833))
    denominator = math.cos(lat_rad) * math.cos(decl)
    if abs(denominator) < 1e-8:
        return DaylightStatus(
            is_daylight=fallback_dawn <= now_local <= fallback_dusk,
            sunrise_ts=int(fallback_dawn.timestamp()),
            sunset_ts=int(fallback_dusk.timestamp()),
            timezone=getattr(tz, "key", "UTC"),
            method="fallback_fixed_window",
        )

    hour_angle_input = (cos_zenith / denominator) - (math.tan(lat_rad) * math.tan(decl))
    if hour_angle_input <= -1.0 or hour_angle_input >= 1.0:
        return DaylightStatus(
            is_daylight=False,
            sunrise_ts=None,
            sunset_ts=None,
            timezone=getattr(tz, "key", "UTC"),
            method="solar_no_daylight",
        )

    hour_angle = math.degrees(math.acos(hour_angle_input))
    utc_offset = now_local.utcoffset()
    utc_offset_minutes = int(utc_offset.total_seconds() / 60) if utc_offset else 0

    sunrise_minutes = 720 - (4 * (longitude + hour_angle)) - eq_time + utc_offset_minutes
    sunset_minutes = 720 - (4 * (longitude - hour_angle)) - eq_time + utc_offset_minutes

    day_start = datetime.combine(now_local.date(), dtime(hour=0, minute=0), tzinfo=tz)
    sunrise_local = day_start + timedelta(minutes=sunrise_minutes)
    sunset_local = day_start + timedelta(minutes=sunset_minutes)

    return DaylightStatus(
        is_daylight=sunrise_local <= now_local <= sunset_local,
        sunrise_ts=int(sunrise_local.timestamp()),
        sunset_ts=int(sunset_local.timestamp()),
            timezone=getattr(tz, "key", "UTC"),
        method="solar_position",
    )


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass
class PanelStatus:
    panel_id: str
    p_kw: float
    ts: int
    state: str
    serial: str
    is_offline: bool = False
    offline_seconds: int = 0


def _check_zero_production(
    session: "SessionClass",
    now_ts: int,
    daylight: DaylightStatus,
) -> list[dict[str, Any]]:
    """Return list of zero-production panel dicts that qualify for alerting."""
    if not daylight.is_daylight:
        return []

    alert_window_start = now_ts - ZERO_PROD_THRESHOLD_SECONDS
    alert_window_end = now_ts

    repo = TelemetryRepository(session, dialect_name="postgresql")

    # Get all panels with latest reading
    latest_rows = repo.fetch_latest_panel_rows()
    if not latest_rows:
        return []

    # For each panel, check if ALL readings in the window are zero
    zero_panels = []
    for row in latest_rows:
        p_kw = _to_float(str(row.get("p_kw"))) if row.get("p_kw") is not None else None
        if p_kw is None:
            continue

        if p_kw == 0.0:
            # Panel is at zero right now — check if sustained
            count_row = session.execute(
                text(
                    """
                    SELECT COUNT(*) as total,
                           COUNT(CASE WHEN p_kw > 0 THEN 1 END) as nonzero_count
                    FROM panel_power_samples
                    WHERE panel_id = :panel_id
                      AND ts BETWEEN :window_start AND :window_end
                    """
                ),
                {"panel_id": row["panel_id"], "window_start": alert_window_start, "window_end": alert_window_end},
            ).mappings().first()

            total = int(count_row["total"]) if count_row else 0
            nonzero = int(count_row["nonzero_count"]) if count_row else 0

            # If we have samples but ALL are zero, flag it
            if total > 0 and nonzero == 0:
                zero_panels.append(
                    {
                        "panel_id": str(row["panel_id"]),
                        "serial": str(row.get("serial") or row["panel_id"]),
                        "state": str(row.get("state") or "Unknown"),
                        "p_kw": p_kw,
                        "ts": int(row["ts"]),
                        "sustained_samples": total,
                        "sustained_seconds": ZERO_PROD_THRESHOLD_SECONDS,
                    }
                )

    return zero_panels


def _check_offline_panels(
    session: "SessionClass",
    now_ts: int,
    daylight: DaylightStatus,
) -> list[PanelStatus]:
    """Return panels with no data seen for OFFLINE_THRESHOLD_SECONDS during daylight."""
    if not daylight.is_daylight:
        return []

    repo = TelemetryRepository(session, dialect_name="postgresql")
    latest_rows = repo.fetch_latest_panel_rows()

    offline_panels = []
    for row in latest_rows:
        last_ts = int(row["ts"]) if row.get("ts") else 0
        seconds_ago = now_ts - last_ts
        if last_ts > 0 and seconds_ago >= OFFLINE_THRESHOLD_SECONDS:
            p_kw = _to_float(str(row.get("p_kw"))) if row.get("p_kw") is not None else None
            offline_panels.append(
                PanelStatus(
                    panel_id=str(row["panel_id"]),
                    p_kw=p_kw or 0.0,
                    ts=last_ts,
                    state=str(row.get("state") or "Unknown"),
                    serial=str(row.get("serial") or row["panel_id"]),
                    is_offline=True,
                    offline_seconds=seconds_ago,
                )
            )

    return offline_panels


def _gateway_severity(seconds_ago: int) -> str:
    if seconds_ago >= 3600:
        return "critical"
    if seconds_ago >= 600:
        return "warning"
    return "info"


def run_production_monitor_cycle(
    session: "SessionClass",
    now_ts: int | None = None,
    gateway_failure_seconds_ago: int | None = None,
) -> dict[str, Any]:
    """
    main entry point for the production monitor job.

    gateway_failure_seconds_ago: if the poll cycle caught a gateway failure,
    pass how many seconds ago (e.g. 0 for immediate). None means no failure this cycle.
    """
    if now_ts is None:
        now_ts = int(time.time())

    daylight = _solar_daylight_status(now_ts)
    results: dict[str, Any] = {
        "checked_at_ts": now_ts,
        "is_daylight": daylight.is_daylight,
        "sunrise_ts": daylight.sunrise_ts,
        "sunset_ts": daylight.sunset_ts,
        "gateway_alert_triggered": False,
        "zero_production_panels": [],
        "offline_panels": [],
    }

    alert_service = AlertLifecycleService(AlertsRepository(session))

    # ── Gateway failure alert ────────────────────────────────────────────────
    # Only alert if gateway has been down for ≥60s; recent polls (≤30s) mean it came back
    if gateway_failure_seconds_ago is not None and gateway_failure_seconds_ago >= 60:
        severity = _gateway_severity(gateway_failure_seconds_ago)
        dedupe_key = f"{SITE_ID}|gateway|production|gateway-health|gateway_status|down"
        existing = alert_service._repository.fetch_active_alert_by_dedupe_key(dedupe_key)
        if existing is None:
            alert_service._repository.insert_alert(
                anomaly_id=None,
                site_id=SITE_ID,
                panel_id=None,
                dedupe_key=dedupe_key,
                kind="production",
                category="gateway",
                severity=severity,
                title="Gateway unreachable",
                message=(
                    f"Gateway at {settings.GATEWAY_IP} is not reachable "
                    f"({gateway_failure_seconds_ago}s since last successful poll). "
                    "Live data may be stale."
                ),
                first_seen_ts=now_ts,
                last_seen_ts=now_ts,
                baseline_kw=None,
                observed_kw=None,
                deviation_kw=None,
                deviation_pct=None,
                confidence_score=None,
                affected_panel_count=None,
                evidence_summary="Gateway connectivity failure",
                explanation_payload={
                    "kind": "production",
                    "source": "gateway-health",
                    "metric": "gateway_status",
                    "direction": "down",
                    "title": "Gateway unreachable",
                    "message": f"Gateway at {settings.GATEWAY_IP} unreachable",
                    "explanation": f"Gateway unreachable for {gateway_failure_seconds_ago}s",
                    "evidence": {
                        "gateway_ip": settings.GATEWAY_IP,
                        "failure_duration_seconds": gateway_failure_seconds_ago,
                        "last_successful_poll_ts": now_ts - gateway_failure_seconds_ago,
                    },
                    "sample_ts": now_ts,
                },
            )
            results["gateway_alert_triggered"] = True
        else:
            # Update existing alert's last_seen_ts
            alert_service._repository.update_existing_alert_observation(
                alert_id=int(existing["alert_id"]),
                anomaly_id=None,
                severity=severity,
                last_seen_ts=now_ts,
                baseline_kw=None,
                observed_kw=None,
                deviation_kw=None,
                deviation_pct=None,
                confidence_score=None,
                affected_panel_count=None,
                evidence_summary="Gateway connectivity failure",
                explanation_payload={
                    "kind": "production",
                    "source": "gateway-health",
                    "metric": "gateway_status",
                    "direction": "down",
                    "title": "Gateway unreachable",
                    "message": f"Gateway at {settings.GATEWAY_IP} unreachable",
                    "explanation": f"Gateway unreachable for {gateway_failure_seconds_ago}s",
                    "evidence": {
                        "gateway_ip": settings.GATEWAY_IP,
                        "failure_duration_seconds": gateway_failure_seconds_ago,
                        "last_successful_poll_ts": now_ts - gateway_failure_seconds_ago,
                    },
                    "sample_ts": now_ts,
                },
            )
            results["gateway_alert_triggered"] = True

    # ── Zero production during daylight ─────────────────────────────────────
    if daylight.is_daylight:
        zero_panels = _check_zero_production(session, now_ts, daylight)
        results["zero_production_panels"] = [
            {"panel_id": p["panel_id"], "serial": p["serial"]} for p in zero_panels
        ]

        for panel in zero_panels:
            panel_id = panel["panel_id"]
            dedupe_key = (
                f"{SITE_ID}|{panel_id}|production|production-monitor|p_kw|zero"
            )
            severity = "critical"
            title = f"Panel {panel_id} zero production during daylight"
            message = (
                f"Panel {panel_id} (serial: {panel['serial']}) has reported zero production "
                f"continuously for {panel['sustained_seconds']} seconds during daylight hours. "
                f"Last state: {panel['state']}."
            )
            evidence = {
                "panel_id": panel_id,
                "serial": panel["serial"],
                "state": panel["state"],
                "p_kw": panel["p_kw"],
                "sustained_seconds": panel["sustained_seconds"],
                "threshold_seconds": ZERO_PROD_THRESHOLD_SECONDS,
                "daylight": {
                    "is_daylight": daylight.is_daylight,
                    "sunrise_ts": daylight.sunrise_ts,
                    "sunset_ts": daylight.sunset_ts,
                    "timezone": daylight.timezone,
                    "method": daylight.method,
                },
            }

            existing = alert_service._repository.fetch_active_alert_by_dedupe_key(dedupe_key)
            if existing is None:
                alert_service._repository.insert_alert(
                    anomaly_id=None,
                    site_id=SITE_ID,
                    panel_id=panel_id,
                    dedupe_key=dedupe_key,
                    kind="production",
                    category="production",
                    severity=severity,
                    title=title,
                    message=message,
                    first_seen_ts=now_ts,
                    last_seen_ts=now_ts,
                    baseline_kw=None,
                    observed_kw=0.0,
                    deviation_kw=None,
                    deviation_pct=None,
                    confidence_score=1.0,
                    affected_panel_count=1,
                    evidence_summary=message[:200],
                    explanation_payload={
                        "kind": "production",
                        "source": "production-monitor",
                        "metric": "p_kw",
                        "direction": "zero",
                        "title": title,
                        "message": message,
                        "explanation": message,
                        "evidence": evidence,
                        "sample_ts": now_ts,
                    },
                )
            else:
                alert_service._repository.update_existing_alert_observation(
                    alert_id=int(existing["alert_id"]),
                    anomaly_id=None,
                    severity=severity,
                    last_seen_ts=now_ts,
                    baseline_kw=None,
                    observed_kw=0.0,
                    deviation_kw=None,
                    deviation_pct=None,
                    confidence_score=1.0,
                    affected_panel_count=1,
                    evidence_summary=message[:200],
                    explanation_payload={
                        "kind": "production",
                        "source": "production-monitor",
                        "metric": "p_kw",
                        "direction": "zero",
                        "title": title,
                        "message": message,
                        "explanation": message,
                        "evidence": evidence,
                        "sample_ts": now_ts,
                    },
                )

    # ── Offline panels during daylight ──────────────────────────────────────
    if daylight.is_daylight:
        offline_panels = _check_offline_panels(session, now_ts, daylight)
        results["offline_panels"] = [
            {"panel_id": p.panel_id, "offline_seconds": p.offline_seconds} for p in offline_panels
        ]

        for panel in offline_panels:
            severity = "critical" if panel.offline_seconds >= CRITICAL_OFFLINE_SECONDS else "warning"
            dedupe_key = (
                f"{SITE_ID}|{panel.panel_id}|production|production-monitor|panel_offline|offline"
            )
            title = f"Panel {panel.panel_id} offline"
            message = (
                f"Panel {panel.panel_id} (serial: {panel.serial}) has not reported data "
                f"for {panel.offline_seconds}s (threshold: {OFFLINE_THRESHOLD_SECONDS}s). "
                f"Last state: {panel.state}. "
                f"Last reading: {panel.p_kw:.3f}kW at ts={panel.ts}."
            )
            evidence = {
                "panel_id": panel.panel_id,
                "serial": panel.serial,
                "state": panel.state,
                "p_kw": panel.p_kw,
                "last_seen_ts": panel.ts,
                "offline_seconds": panel.offline_seconds,
                "offline_threshold_seconds": OFFLINE_THRESHOLD_SECONDS,
                "critical_threshold_seconds": CRITICAL_OFFLINE_SECONDS,
                "daylight": {
                    "is_daylight": daylight.is_daylight,
                    "sunrise_ts": daylight.sunrise_ts,
                    "sunset_ts": daylight.sunset_ts,
                    "timezone": daylight.timezone,
                    "method": daylight.method,
                },
            }

            existing = alert_service._repository.fetch_active_alert_by_dedupe_key(dedupe_key)
            if existing is None:
                alert_service._repository.insert_alert(
                    anomaly_id=None,
                    site_id=SITE_ID,
                    panel_id=panel.panel_id,
                    dedupe_key=dedupe_key,
                    kind="production",
                    category="production",
                    severity=severity,
                    title=title,
                    message=message,
                    first_seen_ts=now_ts,
                    last_seen_ts=now_ts,
                    baseline_kw=None,
                    observed_kw=panel.p_kw,
                    deviation_kw=None,
                    deviation_pct=None,
                    confidence_score=1.0,
                    affected_panel_count=1,
                    evidence_summary=message[:200],
                    explanation_payload={
                        "kind": "production",
                        "source": "production-monitor",
                        "metric": "panel_offline",
                        "direction": "offline",
                        "title": title,
                        "message": message,
                        "explanation": message,
                        "evidence": evidence,
                        "sample_ts": now_ts,
                    },
                )
            else:
                alert_service._repository.update_existing_alert_observation(
                    alert_id=int(existing["alert_id"]),
                    anomaly_id=None,
                    severity=severity,
                    last_seen_ts=now_ts,
                    baseline_kw=None,
                    observed_kw=panel.p_kw,
                    deviation_kw=None,
                    deviation_pct=None,
                    confidence_score=1.0,
                    affected_panel_count=1,
                    evidence_summary=message[:200],
                    explanation_payload={
                        "kind": "production",
                        "source": "production-monitor",
                        "metric": "panel_offline",
                        "direction": "offline",
                        "title": title,
                        "message": message,
                        "explanation": message,
                        "evidence": evidence,
                        "sample_ts": now_ts,
                    },
                )

    return results

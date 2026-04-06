import math
from dataclasses import dataclass
from datetime import datetime
from datetime import time
from datetime import timedelta
from statistics import fmean
from statistics import median
from statistics import pstdev
from zoneinfo import ZoneInfo

from .. import settings
from ..repositories.alerts import AlertsRepository
from ..repositories.production_intelligence import ProductionIntelligenceRepository
from ..services.alerts import AlertLifecycleService


SITE_ID = "default"
METRIC = "production_kw"
PANEL_METRIC = "p_kw"
BUCKET_SECONDS = 300
RECENT_WINDOW_SECONDS = 24 * 3600
LOOKBACK_SECONDS = 14 * 24 * 3600
MIN_BASELINE_SAMPLES = 5
MIN_BASELINE_FOR_ANOMALY_KW = 0.2
UNDERPRODUCTION_THRESHOLD_PCT = -30.0
PEER_UNDERPERFORMING_RATIO = 0.5
FAULT_KEYWORD = "fault"
MODEL_VERSION = "production-intelligence-v1"


@dataclass
class DaylightStatus:
    is_daylight: bool
    sunrise_ts: int | None
    sunset_ts: int | None
    timezone: str
    method: str


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _get_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TZ_NAME or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _solar_daylight_status(ts: int) -> DaylightStatus:
    tz = _get_tz()
    now_local = datetime.fromtimestamp(ts, tz=tz)
    latitude = _to_float(settings.LATITUDE)
    longitude = _to_float(settings.LONGITUDE)

    fallback_dawn = datetime.combine(now_local.date(), time(hour=6, minute=0), tzinfo=tz)
    fallback_dusk = datetime.combine(now_local.date(), time(hour=18, minute=30), tzinfo=tz)

    if latitude is None or longitude is None:
        return DaylightStatus(
            is_daylight=fallback_dawn <= now_local <= fallback_dusk,
            sunrise_ts=int(fallback_dawn.timestamp()),
            sunset_ts=int(fallback_dusk.timestamp()),
            timezone=tz.key,
            method="fallback_fixed_window",
        )

    day_of_year = now_local.timetuple().tm_yday
    gamma = (2.0 * math.pi / 365.0) * (day_of_year - 1)
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    lat_rad = math.radians(latitude)
    cos_zenith = math.cos(math.radians(90.833))
    denominator = math.cos(lat_rad) * math.cos(decl)
    if abs(denominator) < 1e-8:
        return DaylightStatus(
            is_daylight=fallback_dawn <= now_local <= fallback_dusk,
            sunrise_ts=int(fallback_dawn.timestamp()),
            sunset_ts=int(fallback_dusk.timestamp()),
            timezone=tz.key,
            method="fallback_fixed_window",
        )

    hour_angle_input = (cos_zenith / denominator) - (math.tan(lat_rad) * math.tan(decl))
    if hour_angle_input <= -1.0 or hour_angle_input >= 1.0:
        return DaylightStatus(
            is_daylight=False,
            sunrise_ts=None,
            sunset_ts=None,
            timezone=tz.key,
            method="solar_no_daylight",
        )

    hour_angle = math.degrees(math.acos(hour_angle_input))
    utc_offset = now_local.utcoffset()
    if utc_offset is None:
        utc_offset_minutes = 0
    else:
        utc_offset_minutes = int(utc_offset.total_seconds() / 60)

    sunrise_minutes = 720 - (4 * (longitude + hour_angle)) - eq_time + utc_offset_minutes
    sunset_minutes = 720 - (4 * (longitude - hour_angle)) - eq_time + utc_offset_minutes

    day_start = datetime.combine(now_local.date(), time(hour=0, minute=0), tzinfo=tz)
    sunrise_local = day_start + timedelta(minutes=sunrise_minutes)
    sunset_local = day_start + timedelta(minutes=sunset_minutes)

    return DaylightStatus(
        is_daylight=sunrise_local <= now_local <= sunset_local,
        sunrise_ts=int(sunrise_local.timestamp()),
        sunset_ts=int(sunset_local.timestamp()),
        timezone=tz.key,
        method="solar_position",
    )


def _severity_for_deviation(deviation_pct: float) -> str:
    if deviation_pct <= -60.0:
        return "critical"
    if deviation_pct <= -40.0:
        return "warning"
    return "info"


def _compute_stats(values: list[float]) -> tuple[float, float, int]:
    baseline = float(fmean(values))
    stddev = float(pstdev(values)) if len(values) > 1 else 0.0
    return baseline, stddev, len(values)


def _confidence(sample_count: int) -> float:
    return min(1.0, sample_count / float(MIN_BASELINE_SAMPLES * 2))


def _panel_state_text(fault_count: int) -> str | None:
    if fault_count < 1:
        return None
    return f"{fault_count} panel(s) reported fault state"


def _upsert_recent_daylight_baselines(
    repository: ProductionIntelligenceRepository,
    reference_ts: int,
) -> dict[int, dict[str, float | int]]:
    recent_rows = repository.fetch_site_samples_between(reference_ts - RECENT_WINDOW_SECONDS, reference_ts)
    recent_buckets = sorted({int(row["ts"]) // BUCKET_SECONDS * BUCKET_SECONDS for row in recent_rows})
    panel_ids = repository.fetch_panel_ids()

    computed_for_bucket: dict[int, dict[str, float | int]] = {}
    for bucket_start_ts in recent_buckets:
        daylight = _solar_daylight_status(bucket_start_ts)
        if not daylight.is_daylight:
            continue

        bucket_of_day = bucket_start_ts % 86400
        history = repository.fetch_site_bucket_history(
            bucket_of_day=bucket_of_day,
            start_ts=bucket_start_ts - LOOKBACK_SECONDS,
            end_ts=bucket_start_ts - BUCKET_SECONDS,
        )
        history_values = [
            float(row["production_kw"])
            for row in history
            if row["production_kw"] is not None and _solar_daylight_status(int(row["ts"])).is_daylight
        ]
        if len(history_values) < MIN_BASELINE_SAMPLES:
            continue

        baseline_kw, baseline_stddev_kw, sample_count = _compute_stats(history_values)
        confidence = _confidence(sample_count)
        repository.upsert_site_baseline(
            site_id=SITE_ID,
            metric=METRIC,
            bucket_start_ts=bucket_start_ts,
            bucket_granularity_seconds=BUCKET_SECONDS,
            baseline_kw=baseline_kw,
            baseline_stddev_kw=baseline_stddev_kw,
            sample_count=sample_count,
            confidence_score=confidence,
            model_version=MODEL_VERSION,
        )
        computed_for_bucket[bucket_start_ts] = {
            "baseline_kw": baseline_kw,
            "baseline_stddev_kw": baseline_stddev_kw,
            "sample_count": sample_count,
            "confidence_score": confidence,
        }

        for panel_id in panel_ids:
            panel_history = repository.fetch_panel_bucket_history(
                panel_id=panel_id,
                bucket_of_day=bucket_of_day,
                start_ts=bucket_start_ts - LOOKBACK_SECONDS,
                end_ts=bucket_start_ts - BUCKET_SECONDS,
            )
            panel_values = [
                float(row["p_kw"])
                for row in panel_history
                if row["p_kw"] is not None and _solar_daylight_status(int(row["ts"])).is_daylight
            ]
            if len(panel_values) < MIN_BASELINE_SAMPLES:
                continue
            panel_baseline_kw, panel_stddev_kw, panel_sample_count = _compute_stats(panel_values)
            repository.upsert_panel_baseline(
                site_id=SITE_ID,
                panel_id=panel_id,
                metric=PANEL_METRIC,
                bucket_start_ts=bucket_start_ts,
                bucket_granularity_seconds=BUCKET_SECONDS,
                baseline_kw=panel_baseline_kw,
                baseline_stddev_kw=panel_stddev_kw,
                sample_count=panel_sample_count,
                confidence_score=_confidence(panel_sample_count),
                model_version=MODEL_VERSION,
            )

    return computed_for_bucket


def run_production_intelligence_cycle(
    repository: ProductionIntelligenceRepository,
    now_ts: int | None = None,
) -> dict[str, int | bool]:
    latest = repository.fetch_latest_site_sample(site_id=SITE_ID)
    if latest is None or latest.get("production_kw") is None:
        return {
            "baseline_windows": 0,
            "anomaly_created": False,
        }

    latest_ts = int(latest["ts"])
    reference_ts = min(now_ts, latest_ts) if now_ts is not None else latest_ts
    baseline_by_bucket = _upsert_recent_daylight_baselines(repository=repository, reference_ts=reference_ts)

    daylight = _solar_daylight_status(latest_ts)
    if not daylight.is_daylight:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    bucket_start_ts = latest_ts // BUCKET_SECONDS * BUCKET_SECONDS
    baseline = baseline_by_bucket.get(bucket_start_ts) or repository.fetch_site_baseline(
        site_id=SITE_ID,
        metric=METRIC,
        bucket_start_ts=bucket_start_ts,
        bucket_granularity_seconds=BUCKET_SECONDS,
    )
    if baseline is None:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    baseline_kw = float(baseline["baseline_kw"])
    observed_kw = float(latest["production_kw"])
    if baseline_kw < MIN_BASELINE_FOR_ANOMALY_KW:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    deviation_kw = observed_kw - baseline_kw
    deviation_pct = (deviation_kw / baseline_kw) * 100.0
    if deviation_pct > UNDERPRODUCTION_THRESHOLD_PCT:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    existing = repository.fetch_existing_site_underproduction_anomaly(site_id=SITE_ID, sample_ts=latest_ts)
    if existing is not None:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    panel_rows = repository.fetch_panel_samples_at_ts(latest_ts)
    valid_powers = [float(row["p_kw"]) for row in panel_rows if row.get("p_kw") is not None]
    peer_median_kw = float(median(valid_powers)) if valid_powers else 0.0

    fault_panels = []
    peer_underperforming_panels = []
    for row in panel_rows:
        panel_id = str(row["panel_id"])
        panel_power = float(row["p_kw"]) if row.get("p_kw") is not None else 0.0
        panel_state = str(row.get("state") or "")
        panel_state_lower = panel_state.lower()
        if FAULT_KEYWORD in panel_state_lower:
            fault_panels.append({"panel_id": panel_id, "state": panel_state, "p_kw": panel_power})
        if peer_median_kw > 0 and panel_power < (peer_median_kw * PEER_UNDERPERFORMING_RATIO):
            peer_underperforming_panels.append(
                {
                    "panel_id": panel_id,
                    "p_kw": panel_power,
                    "peer_median_kw": peer_median_kw,
                    "ratio_to_peer_median": panel_power / peer_median_kw,
                    "state": panel_state,
                }
            )

    affected_panels = {item["panel_id"] for item in fault_panels}
    affected_panels.update(item["panel_id"] for item in peer_underperforming_panels)
    affected_panel_count = len(affected_panels)

    evidence = {
        "expected_baseline_kw": baseline_kw,
        "actual_production_kw": observed_kw,
        "percent_deviation": deviation_pct,
        "daylight": {
            "is_daylight": daylight.is_daylight,
            "sunrise_ts": daylight.sunrise_ts,
            "sunset_ts": daylight.sunset_ts,
            "timezone": daylight.timezone,
            "method": daylight.method,
        },
        "affected_panel_count": affected_panel_count,
        "panel_state_issues": fault_panels,
        "peer_underperforming_panels": peer_underperforming_panels,
        "baseline_sample_count": int(baseline["sample_count"]),
        "baseline_stddev_kw": float(baseline.get("baseline_stddev_kw") or 0.0),
    }
    explanation = (
        f"Daylight underproduction detected: observed {observed_kw:.3f}kW vs expected {baseline_kw:.3f}kW "
        f"({deviation_pct:.1f}% deviation) with {affected_panel_count} affected panel(s)."
    )

    baseline_stddev_kw = float(baseline.get("baseline_stddev_kw") or 0.0)
    z_score = (deviation_kw / baseline_stddev_kw) if baseline_stddev_kw > 0 else 0.0

    anomaly_id = repository.insert_anomaly(
        site_id=SITE_ID,
        panel_id=None,
        metric=METRIC,
        source="site",
        direction="below",
        severity=_severity_for_deviation(deviation_pct),
        detected_at_ts=reference_ts,
        sample_ts=latest_ts,
        bucket_start_ts=bucket_start_ts,
        bucket_end_ts=bucket_start_ts + BUCKET_SECONDS,
        baseline_kw=baseline_kw,
        observed_kw=observed_kw,
        deviation_kw=deviation_kw,
        deviation_pct=deviation_pct,
        z_score=z_score,
        confidence_score=float(baseline["confidence_score"]),
        sample_count=int(baseline["sample_count"]),
        panel_state=_panel_state_text(len(fault_panels)),
        explanation=explanation,
        evidence=evidence,
    )

    repository.insert_anomaly_evidence(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        evidence_type="site_underproduction_baseline",
        reference_ts=latest_ts,
        window_start_ts=bucket_start_ts,
        window_end_ts=bucket_start_ts + BUCKET_SECONDS,
        metric=METRIC,
        baseline_kw=baseline_kw,
        observed_kw=observed_kw,
        deviation_kw=deviation_kw,
        deviation_pct=deviation_pct,
        z_score=z_score,
        confidence_score=float(baseline["confidence_score"]),
        sample_count=int(baseline["sample_count"]),
        panel_state=_panel_state_text(len(fault_panels)),
        details="Observed site production is materially below daylight baseline.",
        context=evidence,
    )

    repository.insert_anomaly_evidence(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        evidence_type="daylight_status",
        reference_ts=latest_ts,
        window_start_ts=daylight.sunrise_ts,
        window_end_ts=daylight.sunset_ts,
        metric=METRIC,
        baseline_kw=None,
        observed_kw=observed_kw,
        deviation_kw=None,
        deviation_pct=None,
        z_score=None,
        confidence_score=None,
        sample_count=None,
        panel_state=None,
        details="Anomaly evaluated during daylight window.",
        context={
            "is_daylight": daylight.is_daylight,
            "sunrise_ts": daylight.sunrise_ts,
            "sunset_ts": daylight.sunset_ts,
            "timezone": daylight.timezone,
            "method": daylight.method,
        },
    )

    for issue in fault_panels:
        repository.insert_anomaly_evidence(
            anomaly_id=anomaly_id,
            site_id=SITE_ID,
            panel_id=str(issue["panel_id"]),
            evidence_type="panel_state_issue",
            reference_ts=latest_ts,
            window_start_ts=bucket_start_ts,
            window_end_ts=bucket_start_ts + BUCKET_SECONDS,
            metric=PANEL_METRIC,
            baseline_kw=None,
            observed_kw=float(issue["p_kw"]),
            deviation_kw=None,
            deviation_pct=None,
            z_score=None,
            confidence_score=None,
            sample_count=None,
            panel_state=str(issue["state"]),
            details="Panel reports fault state while site underproduction is active.",
            context=issue,
        )

    for peer in peer_underperforming_panels:
        repository.insert_anomaly_evidence(
            anomaly_id=anomaly_id,
            site_id=SITE_ID,
            panel_id=str(peer["panel_id"]),
            evidence_type="peer_underperforming_panel",
            reference_ts=latest_ts,
            window_start_ts=bucket_start_ts,
            window_end_ts=bucket_start_ts + BUCKET_SECONDS,
            metric=PANEL_METRIC,
            baseline_kw=float(peer["peer_median_kw"]),
            observed_kw=float(peer["p_kw"]),
            deviation_kw=float(peer["p_kw"] - peer["peer_median_kw"]),
            deviation_pct=float(((peer["p_kw"] - peer["peer_median_kw"]) / peer["peer_median_kw"]) * 100.0),
            z_score=None,
            confidence_score=None,
            sample_count=None,
            panel_state=str(peer["state"]),
            details="Panel output is materially below contemporaneous peer median.",
            context=peer,
        )

    alert_service = AlertLifecycleService(AlertsRepository(repository.executor))
    alert_service.record_anomaly_detection(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        source="site",
        metric=METRIC,
        direction="below",
        severity=_severity_for_deviation(deviation_pct),
        sample_ts=latest_ts,
        title="Production underperformance",
        message=explanation,
        baseline_kw=baseline_kw,
        observed_kw=observed_kw,
        deviation_kw=deviation_kw,
        deviation_pct=deviation_pct,
        confidence_score=float(baseline["confidence_score"]),
        affected_panel_count=affected_panel_count,
        explanation=explanation,
        evidence=evidence,
    )

    return {
        "baseline_windows": len(baseline_by_bucket),
        "anomaly_created": True,
    }

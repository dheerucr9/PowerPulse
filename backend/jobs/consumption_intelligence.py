from datetime import datetime
from statistics import fmean
from statistics import pstdev
from zoneinfo import ZoneInfo

from .. import settings
from ..repositories.alerts import AlertsRepository
from ..repositories.consumption_intelligence import ConsumptionIntelligenceRepository
from ..services.alerts import AlertLifecycleService


SITE_ID = "default"
METRIC = "consumption_kw"
BUCKET_SECONDS = 300
RECENT_WINDOW_SECONDS = 24 * 3600
LOOKBACK_SECONDS = 56 * 24 * 3600
MIN_BASELINE_SAMPLES = 5
SUSTAINED_MIN_BUCKETS = 4
SUSTAINED_MAX_WINDOW_SECONDS = 2 * 3600
BASELOAD_HOURS = set(range(0, 6))
MODEL_VERSION = "consumption-intelligence-v1"


def _get_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TZ_NAME or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _bucket_start(ts: int) -> int:
    return ts // BUCKET_SECONDS * BUCKET_SECONDS


def _compute_stats(values: list[float]) -> tuple[float, float, int]:
    baseline = float(fmean(values))
    stddev = float(pstdev(values)) if len(values) > 1 else 0.0
    return baseline, stddev, len(values)


def _confidence(sample_count: int) -> float:
    return min(1.0, sample_count / float(MIN_BASELINE_SAMPLES * 2))


def _expected_band(baseline_kw: float, stddev_kw: float) -> tuple[float, float]:
    spread_upper = max(stddev_kw * 2.5, baseline_kw * 0.40, 0.35)
    spread_lower = max(stddev_kw * 2.0, baseline_kw * 0.25, 0.20)
    lower = max(0.0, baseline_kw - spread_lower)
    upper = baseline_kw + spread_upper
    return lower, upper


def _severity(observed_kw: float, expected_upper_kw: float, sustained_buckets: int) -> str:
    ratio = observed_kw / expected_upper_kw if expected_upper_kw > 0 else 1.0
    if ratio >= 2.0 or sustained_buckets >= 12:
        return "critical"
    if ratio >= 1.5 or sustained_buckets >= 8:
        return "warning"
    return "info"


def _format_duration(seconds: int) -> str:
    if seconds >= 3600:
        hours = seconds / 3600.0
        return f"{hours:.1f} hour(s)"
    minutes = seconds / 60.0
    return f"{minutes:.0f} minute(s)"


def _as_float(value: object | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _upsert_recent_baselines(
    repository: ConsumptionIntelligenceRepository,
    reference_ts: int,
) -> dict[int, dict[str, float | int]]:
    tz = _get_tz()
    recent_rows = repository.fetch_site_samples_between(reference_ts - RECENT_WINDOW_SECONDS, reference_ts)
    recent_buckets = sorted({_bucket_start(int(row["ts"])) for row in recent_rows})

    computed_for_bucket: dict[int, dict[str, float | int]] = {}
    for bucket_start_ts in recent_buckets:
        bucket_of_day = bucket_start_ts % 86400
        target_dow = datetime.fromtimestamp(bucket_start_ts, tz=tz).weekday()
        history = repository.fetch_consumption_bucket_history(
            bucket_of_day=bucket_of_day,
            start_ts=bucket_start_ts - LOOKBACK_SECONDS,
            end_ts=bucket_start_ts - BUCKET_SECONDS,
        )
        comparable_values = [
            float(row["consumption_kw"])
            for row in history
            if row.get("consumption_kw") is not None
            and datetime.fromtimestamp(int(row["ts"]), tz=tz).weekday() == target_dow
        ]
        if len(comparable_values) < MIN_BASELINE_SAMPLES:
            continue

        baseline_kw, baseline_stddev_kw, sample_count = _compute_stats(comparable_values)
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
    return computed_for_bucket


def _resolve_baseline(
    repository: ConsumptionIntelligenceRepository,
    baseline_by_bucket: dict[int, dict[str, float | int]],
    bucket_start_ts: int,
) -> dict[str, float | int] | None:
    baseline = baseline_by_bucket.get(bucket_start_ts)
    if baseline is not None:
        return baseline
    stored = repository.fetch_site_baseline(
        site_id=SITE_ID,
        metric=METRIC,
        bucket_start_ts=bucket_start_ts,
        bucket_granularity_seconds=BUCKET_SECONDS,
    )
    if stored is None:
        return None
    return {
        "baseline_kw": float(stored["baseline_kw"]),
        "baseline_stddev_kw": float(stored.get("baseline_stddev_kw") or 0.0),
        "sample_count": int(stored["sample_count"]),
        "confidence_score": float(stored.get("confidence_score") or 0.0),
    }


def _compute_sustained_buckets(
    repository: ConsumptionIntelligenceRepository,
    baseline_by_bucket: dict[int, dict[str, float | int]],
    latest_ts: int,
) -> tuple[int, int | None, int | None]:
    window_start = latest_ts - SUSTAINED_MAX_WINDOW_SECONDS
    recent_rows = repository.fetch_site_samples_between(window_start, latest_ts)
    by_bucket: dict[int, dict[str, object]] = {}
    for row in recent_rows:
        by_bucket[_bucket_start(int(row["ts"]))] = row

    streak = 0
    start_ts: int | None = None
    end_ts: int | None = None
    cursor = _bucket_start(latest_ts)
    while cursor >= _bucket_start(window_start):
        row = by_bucket.get(cursor)
        if row is None:
            break
        observed_kw = _as_float(row.get("consumption_kw"))
        if observed_kw is None:
            break
        baseline = _resolve_baseline(repository, baseline_by_bucket, cursor)
        if baseline is None:
            break
        baseline_kw = float(baseline["baseline_kw"])
        stddev_kw = float(baseline.get("baseline_stddev_kw") or 0.0)
        _, expected_upper_kw = _expected_band(baseline_kw, stddev_kw)
        if observed_kw <= expected_upper_kw:
            break
        streak += 1
        start_ts = cursor
        end_ts = cursor + BUCKET_SECONDS
        cursor -= BUCKET_SECONDS

    return streak, start_ts, end_ts


def run_consumption_intelligence_cycle(
    repository: ConsumptionIntelligenceRepository,
    now_ts: int | None = None,
) -> dict[str, int | bool]:
    latest = repository.fetch_latest_site_sample(site_id=SITE_ID)
    if latest is None or latest.get("consumption_kw") is None:
        return {
            "baseline_windows": 0,
            "anomaly_created": False,
        }

    latest_ts = int(latest["ts"])
    reference_ts = min(now_ts, latest_ts) if now_ts is not None else latest_ts
    baseline_by_bucket = _upsert_recent_baselines(repository=repository, reference_ts=reference_ts)

    bucket_start_ts = _bucket_start(latest_ts)
    baseline = _resolve_baseline(repository, baseline_by_bucket, bucket_start_ts)
    if baseline is None:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    baseline_kw = float(baseline["baseline_kw"])
    baseline_stddev_kw = float(baseline.get("baseline_stddev_kw") or 0.0)
    observed_kw = float(latest["consumption_kw"])
    expected_low_kw, expected_high_kw = _expected_band(baseline_kw, baseline_stddev_kw)
    if observed_kw <= expected_high_kw:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    existing = repository.fetch_existing_site_anomaly(
        site_id=SITE_ID,
        metric=METRIC,
        sample_ts=latest_ts,
        direction="above",
    )
    if existing is not None:
        return {
            "baseline_windows": len(baseline_by_bucket),
            "anomaly_created": False,
        }

    sustained_buckets, sustained_start_ts, sustained_end_ts = _compute_sustained_buckets(
        repository=repository,
        baseline_by_bucket=baseline_by_bucket,
        latest_ts=latest_ts,
    )
    is_sustained = sustained_buckets >= SUSTAINED_MIN_BUCKETS
    local_hour = datetime.fromtimestamp(latest_ts, tz=_get_tz()).hour
    is_baseload_hour = local_hour in BASELOAD_HOURS

    if is_sustained and is_baseload_hour:
        pattern_type = "elevated_baseload"
    elif is_sustained:
        pattern_type = "sustained"
    else:
        pattern_type = "spike"

    duration_seconds = BUCKET_SECONDS if pattern_type == "spike" else sustained_buckets * BUCKET_SECONDS
    production_kw_raw = latest.get("production_kw")
    production_kw = float(production_kw_raw) if production_kw_raw is not None else None
    net_kw_raw = latest.get("net_kw")
    net_kw = float(net_kw_raw) if net_kw_raw is not None else None
    exceeds_solar = bool(production_kw is not None and observed_kw > production_kw)
    exceeds_solar_by_kw = (observed_kw - production_kw) if production_kw is not None else None

    deviation_kw = observed_kw - baseline_kw
    deviation_pct = ((deviation_kw / baseline_kw) * 100.0) if baseline_kw > 0 else None
    z_score = (deviation_kw / baseline_stddev_kw) if baseline_stddev_kw > 0 else None
    severity = _severity(observed_kw, expected_high_kw, sustained_buckets)

    solar_context: dict[str, object] = {
        "production_kw": production_kw,
        "net_kw": net_kw,
        "demand_exceeds_solar": exceeds_solar,
        "demand_exceeds_solar_by_kw": exceeds_solar_by_kw,
    }
    evidence: dict[str, object] = {
        "pattern_type": pattern_type,
        "is_spike_like": pattern_type == "spike",
        "duration_seconds": duration_seconds,
        "expected_range_kw": {
            "low": expected_low_kw,
            "high": expected_high_kw,
            "baseline": baseline_kw,
            "stddev": baseline_stddev_kw,
        },
        "actual_demand_kw": observed_kw,
        "deviation_kw": deviation_kw,
        "deviation_pct": deviation_pct,
        "sustained_window": {
            "start_ts": sustained_start_ts,
            "end_ts": sustained_end_ts,
            "bucket_count": sustained_buckets,
        },
        "comparison_context": {
            "bucket_granularity_seconds": BUCKET_SECONDS,
            "sample_count": int(baseline["sample_count"]),
            "confidence_score": float(baseline["confidence_score"]),
        },
        "solar_context": solar_context,
    }

    solar_phrase = (
        f"Demand exceeded contemporaneous solar production ({production_kw:.3f}kW) by {exceeds_solar_by_kw:.3f}kW."
        if production_kw is not None and exceeds_solar and exceeds_solar_by_kw is not None
        else (
            f"Demand did not exceed contemporaneous solar production ({production_kw:.3f}kW)."
            if production_kw is not None
            else "Contemporaneous solar production was unavailable."
        )
    )
    pattern_label = "spike-like" if pattern_type == "spike" else "sustained"
    explanation = (
        f"Consumption {pattern_type.replace('_', ' ')} anomaly ({pattern_label}): expected "
        f"{expected_low_kw:.3f}-{expected_high_kw:.3f}kW for this hour/day baseline, observed {observed_kw:.3f}kW "
        f"for { _format_duration(duration_seconds) }. {solar_phrase}"
    )

    anomaly_id = repository.insert_anomaly(
        site_id=SITE_ID,
        panel_id=None,
        metric=METRIC,
        source="site",
        direction="above",
        severity=severity,
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
        panel_state=None,
        explanation=explanation,
        evidence=evidence,
    )

    repository.insert_anomaly_evidence(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        evidence_type="consumption_baseline_comparison",
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
        panel_state=None,
        details="Observed site consumption is above conservative hour/day baseline range.",
        context=evidence,
    )

    repository.insert_anomaly_evidence(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        evidence_type=("consumption_spike_window" if pattern_type == "spike" else "consumption_sustained_window"),
        reference_ts=latest_ts,
        window_start_ts=sustained_start_ts if sustained_start_ts is not None else bucket_start_ts,
        window_end_ts=sustained_end_ts if sustained_end_ts is not None else bucket_start_ts + BUCKET_SECONDS,
        metric=METRIC,
        baseline_kw=baseline_kw,
        observed_kw=observed_kw,
        deviation_kw=deviation_kw,
        deviation_pct=deviation_pct,
        z_score=z_score,
        confidence_score=float(baseline["confidence_score"]),
        sample_count=int(baseline["sample_count"]),
        panel_state=None,
        details="Pattern classification and duration evidence for elevated site demand.",
        context={
            "pattern_type": pattern_type,
            "duration_seconds": duration_seconds,
            "sustained_bucket_count": sustained_buckets,
            "is_spike_like": pattern_type == "spike",
            "is_baseload_hour": is_baseload_hour,
        },
    )

    repository.insert_anomaly_evidence(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        evidence_type="consumption_solar_context",
        reference_ts=latest_ts,
        window_start_ts=bucket_start_ts,
        window_end_ts=bucket_start_ts + BUCKET_SECONDS,
        metric="production_kw",
        baseline_kw=None,
        observed_kw=production_kw,
        deviation_kw=exceeds_solar_by_kw,
        deviation_pct=None,
        z_score=None,
        confidence_score=None,
        sample_count=None,
        panel_state=None,
        details="Contemporaneous solar and net context for demand anomaly evaluation.",
        context=solar_context,
    )

    alert_service = AlertLifecycleService(AlertsRepository(repository.executor))
    alert_service.record_anomaly_detection(
        anomaly_id=anomaly_id,
        site_id=SITE_ID,
        panel_id=None,
        source="site",
        metric=METRIC,
        direction="above",
        severity=severity,
        sample_ts=latest_ts,
        title=f"Consumption {pattern_type.replace('_', ' ')} anomaly",
        message=explanation,
        baseline_kw=baseline_kw,
        observed_kw=observed_kw,
        deviation_kw=deviation_kw,
        deviation_pct=deviation_pct,
        confidence_score=float(baseline["confidence_score"]),
        affected_panel_count=None,
        explanation=explanation,
        evidence=evidence,
    )

    return {
        "baseline_windows": len(baseline_by_bucket),
        "anomaly_created": True,
    }

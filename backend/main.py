# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportImplicitRelativeImport=false

import os
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Literal

import requests
import urllib3
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # pyright: ignore[reportMissingImports]

from backend import db
from backend.observability import API_REQUEST_DURATION_SECONDS
from backend.observability import API_REQUEST_STATUS_TOTAL
from backend.observability import INGEST_LAST_SUCCESS_TIMESTAMP_SECONDS
from backend.observability import build_readiness_report
from backend.observability import configure_json_logging
from backend.repositories import InvalidCursorError
from backend.schemas import AlertAcknowledgeRequest
from backend.schemas import AlertDetailResponse
from backend.schemas import AlertListMeta
from backend.schemas import AlertListResponse
from backend.schemas import AlertResponse
from backend.schemas import AlertSummaryResponse
from backend.schemas import AnomalySummaryResponse
from backend.schemas import IntelligenceDomainSummaryResponse
from backend.schemas import IntelligenceOpenCountsResponse
from backend.schemas import IntelligenceSummaryResponse
from backend.services.alerts import AlertLifecycleService
from backend import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

configure_json_logging(service="api")
log = logging.getLogger("backend")


app = FastAPI(title="Solar API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built frontend assets
STATIC_ROOT = os.path.join(os.path.dirname(__file__), "..", "static")
DIST_DIR = os.path.join(STATIC_ROOT, "dist")
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.middleware("http")
async def record_request_metrics(request: Request, call_next):
    started = time.perf_counter()
    path_template = request.url.path
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        route = request.scope.get("route")
        if route is not None and getattr(route, "path", None):
            path_template = route.path
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - started
        API_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path_template).observe(duration)
        API_REQUEST_STATUS_TOTAL.labels(
            method=request.method,
            path=path_template,
            status_code=str(status_code),
        ).inc()


class Sample(BaseModel):
    ts: int
    panel_id: str
    p_kw: Optional[float] = None
    v_ac: Optional[float] = None
    v_dc: Optional[float] = None
    i_dc: Optional[float] = None
    temp_c: Optional[float] = None
    state: Optional[str] = None
    serial: Optional[str] = None


class HouseSample(BaseModel):
    ts: int
    production_kw: Optional[float] = None
    consumption_kw: Optional[float] = None
    net_kw: Optional[float] = None
    v_sys: Optional[float] = None
    v_l1: Optional[float] = None
    v_l2: Optional[float] = None


class HouseSeriesResponse(BaseModel):
    samples: List[HouseSample]


class SeriesResponse(BaseModel):
    house: List[HouseSample]
    panel: List[Sample]


class LatestResponse(BaseModel):
    as_of: int
    total_production_kw: float
    panels: List[Sample]


class ChargerLatestResponse(BaseModel):
    ts: int
    charging: bool
    charging_status: str
    vehicle_connected: Optional[bool] = None
    contactor_closed: Optional[bool] = None
    evse_state: Optional[int] = None
    current_a: Optional[float] = None
    voltage_v: Optional[float] = None
    power_kw: Optional[float] = None
    session_energy_wh: Optional[float] = None
    lifetime_energy_wh: Optional[float] = None
    pcba_temp_c: Optional[float] = None
    handle_temp_c: Optional[float] = None


class ChargerSample(BaseModel):
    ts: int
    power_kw: Optional[float] = None


class PageInfo(BaseModel):
    has_more: bool
    next_cursor: Optional[str] = None
    returned: int
    limit: int


GATEWAY_IP = settings.GATEWAY_IP
GATEWAY_USER = settings.GATEWAY_USER
GATEWAY_PASS = settings.GATEWAY_PASS
SUN_TIMEOUT = settings.GATEWAY_TIMEOUT
SESSIONS = {}
LATITUDE = settings.LATITUDE
LONGITUDE = settings.LONGITUDE
DEFAULT_PAGE_LIMIT = 500
MAX_PAGE_LIMIT = 5000


def _normalize_limit(limit: Optional[int]) -> int:
    if limit is None:
        return DEFAULT_PAGE_LIMIT
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return min(limit, MAX_PAGE_LIMIT)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(response: Response):
    report = build_readiness_report(
        get_connection=db.get_connection,
        max_ingest_age_seconds=settings.INGEST_FRESHNESS_MAX_AGE_SECONDS,
    )
    if report.last_ingest_ts is not None:
        INGEST_LAST_SUCCESS_TIMESTAMP_SECONDS.set(report.last_ingest_ts)
    if not report.ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if report.ok else "not_ready",
        "checks": report.checks,
        "last_successful_ingest_ts": report.last_ingest_ts,
        "max_ingest_age_seconds": settings.INGEST_FRESHNESS_MAX_AGE_SECONDS,
    }


@app.get("/metrics")
def metrics():
    from backend import worker_metrics  # noqa: WPS433

    _ = worker_metrics
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


def _dashboard_path():
    return os.path.join(DIST_DIR, "index.html")


@app.get("/", include_in_schema=False)
@app.get("/solar_dashboard.html", include_in_schema=False)
def dashboard():
    return FileResponse(_dashboard_path())


@app.get("/config")
def config():
    return {
        "lat": float(LATITUDE) if LATITUDE else None,
        "lon": float(LONGITUDE) if LONGITUDE else None,
        "tz": settings.TZ_NAME,
        "frontend_api_origin": settings.FRONTEND_API_ORIGIN,
    }


@app.get("/devices")
def devices(ip: Optional[str] = None, user: Optional[str] = None, pass_: Optional[str] = Query(None, alias="pass")):
    ip = ip or GATEWAY_IP
    user = user or GATEWAY_USER
    passwd = pass_ or GATEWAY_PASS
    if not ip or not user or not passwd:
        raise HTTPException(status_code=400, detail="Missing gateway credentials or IP")

    sess = SESSIONS.get(ip) or requests.Session()
    try:
        r = sess.get(f"https://{ip}/auth?login", auth=(user, passwd), timeout=SUN_TIMEOUT, verify=False)
        if r.status_code != 200 or not sess.cookies:
            raise HTTPException(status_code=403, detail="Gateway authentication failed")
        r2 = sess.get(f"https://{ip}/cgi-bin/dl_cgi/devices/list", timeout=SUN_TIMEOUT, verify=False)
        r2.raise_for_status()
        SESSIONS[ip] = sess
        return r2.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/latest", response_model=LatestResponse)
def latest():
    with db.get_connection() as conn:
        repo = db.get_telemetry_repository(conn)
        rows = repo.fetch_latest_panel_rows()
    if not rows:
        raise HTTPException(status_code=404, detail="No samples yet")
    total_kw = sum(r["p_kw"] or 0 for r in rows)
    as_of = max(r["ts"] for r in rows)
    panels = [Sample(**dict(r)) for r in rows]
    return LatestResponse(as_of=as_of, total_production_kw=total_kw, panels=panels)


@app.get("/charger/latest", response_model=ChargerLatestResponse)
def charger_latest():
    with db.get_connection() as conn:
        repo = db.get_charger_repository(conn)
        row = repo.fetch_latest()

    if not row:
        raise HTTPException(status_code=404, detail="No charger samples yet")

    evse_state = row.get("evse_state")
    charging = bool(row.get("contactor_closed") is True or evse_state == 11)
    if evse_state == 11:
        charging_status = "charging"
    elif evse_state == 4:
        charging_status = "finished"
    elif evse_state == 1:
        charging_status = "not_connected"
    else:
        charging_status = "idle"

    return ChargerLatestResponse(
        ts=int(row["ts"]),
        charging=charging,
        charging_status=charging_status,
        vehicle_connected=row.get("vehicle_connected"),
        contactor_closed=row.get("contactor_closed"),
        evse_state=evse_state,
        current_a=row.get("current_a"),
        voltage_v=row.get("voltage_v"),
        power_kw=row.get("power_kw"),
        session_energy_wh=row.get("session_energy_wh"),
        lifetime_energy_wh=row.get("lifetime_energy_wh"),
        pcba_temp_c=row.get("pcba_temp_c"),
        handle_temp_c=row.get("handle_temp_c"),
    )


@app.get("/charger/history")
def charger_history(
    start: Optional[int] = Query(None, alias="from"),
    end: Optional[int] = Query(None, alias="to"),
    interval: str = Query("raw", pattern="^(raw|5m|1h)$"),
    limit: Optional[int] = Query(None),
    cursor: Optional[str] = Query(None),
):
    now = int(datetime.now(tz=timezone.utc).timestamp())
    start = start or (now - 24 * 3600)
    end = end or now
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be < end")

    page_limit = _normalize_limit(limit)
    try:
        with db.get_connection() as conn:
            repo = db.get_charger_repository(conn)
            rows, page_info = repo.fetch_power_page(
                start=start,
                end=end,
                interval=interval,
                limit=page_limit,
                cursor=cursor,
            )
            samples = [ChargerSample(**row) for row in rows]
            return {"samples": [s.model_dump() for s in samples], "page_info": page_info}
    except InvalidCursorError:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/series")
def series(
    panel_id: Optional[str] = Query(None, description="Panel serial/id", alias="panel_id"),
    start: Optional[int] = Query(None, description="Unix epoch seconds", alias="from"),
    end: Optional[int] = Query(None, description="Unix epoch seconds", alias="to"),
    interval: str = Query("raw", pattern="^(raw|5m|1h)$"),
    limit: Optional[int] = Query(None),
    cursor: Optional[str] = Query(None),
):
    now = int(datetime.now(tz=timezone.utc).timestamp())
    start = start or (now - 24 * 3600)
    end = end or now

    if start >= end:
        raise HTTPException(status_code=400, detail="start must be < end")

    page_limit = _normalize_limit(limit)
    try:
        with db.get_connection() as conn:
            repo = db.get_telemetry_repository(conn)
            if panel_id:
                panel_rows, page_info = repo.fetch_panel_page(
                    panel_id=panel_id,
                    start=start,
                    end=end,
                    interval=interval,
                    limit=page_limit,
                    cursor=cursor,
                )
                panel_samples = [Sample(**row) for row in panel_rows]
                return {
                    "samples": [s.model_dump() for s in panel_samples],
                    "page_info": page_info,
                    "panel": [s.model_dump() for s in panel_samples],
                    "house": [],
                }

            house_rows, page_info = repo.fetch_house_page(
                start=start,
                end=end,
                interval=interval,
                limit=page_limit,
                cursor=cursor,
            )
            house_samples = [HouseSample(**row) for row in house_rows]
            return {
                "samples": [s.model_dump() for s in house_samples],
                "page_info": page_info,
                "house": [s.model_dump() for s in house_samples],
                "panel": [],
            }
    except InvalidCursorError:
        raise HTTPException(status_code=400, detail="Invalid cursor")


# Legacy endpoint kept for compatibility; now paginated with samples/page_info
@app.get("/house_series")
def house_series(
    start: Optional[int] = Query(None, alias="from"),
    end: Optional[int] = Query(None, alias="to"),
    interval: str = Query("raw", pattern="^(raw|5m|1h)$"),
    limit: Optional[int] = Query(None),
    cursor: Optional[str] = Query(None),
):
    now = int(datetime.now(tz=timezone.utc).timestamp())
    start = start or (now - 24 * 3600)
    end = end or now
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be < end")
    page_limit = _normalize_limit(limit)
    try:
        with db.get_connection() as conn:
            repo = db.get_telemetry_repository(conn)
            rows, page_info = repo.fetch_house_page(
                start=start,
                end=end,
                interval=interval,
                limit=page_limit,
                cursor=cursor,
            )
            samples = [HouseSample(**row) for row in rows]
            return {"samples": [s.model_dump() for s in samples], "page_info": page_info}
    except InvalidCursorError:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/api/alerts", response_model=AlertListResponse)
def list_alerts(
    status: Optional[Literal["open", "acknowledged", "resolved", "suppressed"]] = Query(None),
    kind: Optional[Literal["production", "consumption"]] = Query(None),
    severity: Optional[Literal["info", "warning", "critical"]] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    with db.get_connection() as conn:
        repo = db.get_alerts_repository(conn)
        items = repo.list_alerts(status=status, kind=kind, severity=severity, limit=limit)
        filtered_total = repo.count_alerts(status=status, kind=kind, severity=severity)
        open_badge_count = repo.count_alerts(status="open", kind=None, severity=None)
        open_by_kind = repo.count_open_alerts_grouped(field="kind")
        open_by_severity = repo.count_open_alerts_grouped(field="severity")

    return AlertListResponse(
        items=[AlertResponse(**row) for row in items],
        meta=AlertListMeta(
            filtered_total=filtered_total,
            returned=len(items),
            open_badge_count=open_badge_count,
            open_by_kind={
                "production": int(open_by_kind.get("production", 0)),
                "consumption": int(open_by_kind.get("consumption", 0)),
            },
            open_by_severity={
                "info": int(open_by_severity.get("info", 0)),
                "warning": int(open_by_severity.get("warning", 0)),
                "critical": int(open_by_severity.get("critical", 0)),
            },
        ),
    )


@app.get("/api/alerts/{alert_id}", response_model=AlertDetailResponse)
def alert_detail(alert_id: int):
    with db.get_connection() as conn:
        repo = db.get_alerts_repository(conn)
        alert = repo.fetch_alert_by_id(alert_id=alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")

        anomaly = None
        anomaly_evidence = []
        anomaly_id = alert.get("anomaly_id")
        if anomaly_id is not None:
            anomaly = repo.fetch_anomaly_by_id(anomaly_id=int(anomaly_id))
            anomaly_evidence = repo.fetch_anomaly_evidence(anomaly_id=int(anomaly_id))

    return {
        "alert": alert,
        "anomaly": anomaly,
        "anomaly_evidence": anomaly_evidence,
    }


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, request: AlertAcknowledgeRequest):
    try:
        with db.get_session() as session:
            repo = db.get_alerts_repository(session)
            service = AlertLifecycleService(repo)
            updated = service.acknowledge_alert(
                alert_id=alert_id,
                new_status=request.new_status,
                acknowledged_by=request.acknowledged_by,
                note=request.note,
            )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)

    return AlertResponse(**updated)


@app.get("/api/intelligence/summary", response_model=IntelligenceSummaryResponse)
def intelligence_summary():
    with db.get_connection() as conn:
        repo = db.get_alerts_repository(conn)
        open_by_kind = repo.count_open_alerts_grouped(field="kind")
        open_by_severity = repo.count_open_alerts_grouped(field="severity")
        production_latest_alert = repo.fetch_latest_alert_for_kind(kind="production")
        consumption_latest_alert = repo.fetch_latest_alert_for_kind(kind="consumption")
        production_latest_anomaly = repo.fetch_latest_anomaly_for_kind(kind="production")
        consumption_latest_anomaly = repo.fetch_latest_anomaly_for_kind(kind="consumption")

    open_total = int(open_by_kind.get("production", 0)) + int(open_by_kind.get("consumption", 0))
    return IntelligenceSummaryResponse(
        generated_at_ts=int(datetime.now(tz=timezone.utc).timestamp()),
        open_counts=IntelligenceOpenCountsResponse(
            total=open_total,
            by_kind={
                "production": int(open_by_kind.get("production", 0)),
                "consumption": int(open_by_kind.get("consumption", 0)),
            },
            by_severity={
                "info": int(open_by_severity.get("info", 0)),
                "warning": int(open_by_severity.get("warning", 0)),
                "critical": int(open_by_severity.get("critical", 0)),
            },
        ),
        production=IntelligenceDomainSummaryResponse(
            latest_alert=AlertSummaryResponse(**production_latest_alert) if production_latest_alert else None,
            latest_anomaly=AnomalySummaryResponse(**production_latest_anomaly) if production_latest_anomaly else None,
        ),
        consumption=IntelligenceDomainSummaryResponse(
            latest_alert=AlertSummaryResponse(**consumption_latest_alert) if consumption_latest_alert else None,
            latest_anomaly=AnomalySummaryResponse(**consumption_latest_anomaly) if consumption_latest_anomaly else None,
        ),
    )

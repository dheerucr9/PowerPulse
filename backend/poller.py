import time
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests  # pyright: ignore[reportMissingModuleSource]
from requests.exceptions import RequestException  # pyright: ignore[reportMissingModuleSource]
import urllib3  # pyright: ignore[reportMissingImports]
from urllib3.util.retry import Retry  # pyright: ignore[reportMissingImports]
from requests.adapters import HTTPAdapter  # pyright: ignore[reportMissingModuleSource]

from . import db
from .jobs.consumption_intelligence import run_consumption_intelligence_cycle
from .jobs.production_intelligence import run_production_intelligence_cycle
from .observability import INGEST_LAST_SUCCESS_TIMESTAMP_SECONDS
from .observability import POLL_INGEST_FAILURE_TOTAL
from .observability import POLL_INGEST_SUCCESS_TOTAL
from .observability import configure_json_logging
from . import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

configure_json_logging(service="worker")
log = logging.getLogger("worker")

# Written by ingest() after each successful poll; read by production_monitor.
_last_successful_poll_ts: int | None = None


def get_last_successful_poll_ts() -> int | None:
    return _last_successful_poll_ts


def require(name: str, val: str | None) -> str:
    if not val:
        raise SystemExit(f"Missing required environment variable {name}")
    return val


GATEWAY_IP = require("GATEWAY_IP", settings.GATEWAY_IP)
GATEWAY_USER = require("GATEWAY_USER", settings.GATEWAY_USER)
GATEWAY_PASS = require("GATEWAY_PASS", settings.GATEWAY_PASS)
POLL_SECONDS = settings.POLL_SECONDS
TZ_NAME = require("TZ", settings.TZ_NAME)
GATEWAY_TIMEOUT = settings.GATEWAY_TIMEOUT


def get_tz():
    try:
        return ZoneInfo(TZ_NAME)
    except Exception:
        return timezone.utc


TZ = get_tz()


def _safe_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        lowered = val.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def fetch_wall_connector_json(ip: str, path: str):
    url = f"http://{ip}{path}"
    sess = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=1.5,
        status_forcelist=(502, 503, 504),
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)

    try:
        response = sess.get(url, timeout=GATEWAY_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (RequestException, ValueError) as e:
        log.warning("Wall Connector request failed for %s: %s", path, e)
        return None


def fetch_devices():
    url_auth = f"https://{GATEWAY_IP}/auth?login"
    url_list = f"https://{GATEWAY_IP}/cgi-bin/dl_cgi/devices/list"
    sess = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=1.5,
        status_forcelist=(502, 503, 504),
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)

    try:
        r = sess.get(url_auth, auth=(GATEWAY_USER, GATEWAY_PASS), timeout=GATEWAY_TIMEOUT, verify=False)
        r.raise_for_status()
        r2 = sess.get(url_list, timeout=GATEWAY_TIMEOUT, verify=False)
        r2.raise_for_status()
        return r2.json()
    except RequestException as e:
        log.warning("Gateway request failed after retries: %s", e)
        return None


def ingest():
    try:
        data = fetch_devices()
        if not data:
            POLL_INGEST_FAILURE_TOTAL.labels(reason="no_data").inc()
            log.warning("No data fetched this cycle.")
            return False
        devices = data.get("devices", [])
        gateway = next((d for d in devices if d.get("DEVICE_TYPE") == "PVS"), {})
        swver = gateway.get("SWVER")

        def pick_meter(devs, role):
            # role: "prod" or "cons"
            for d in devs:
                t = (d.get("TYPE") or "").upper()
                subtype = (d.get("subtype") or "").lower()
                mloc = (d.get("METER_LOCATION") or "").lower()
                if role == "prod" and ("-P" in t or "prod" in subtype or "solar" in subtype):
                    return d
                if role == "cons" and ("-C" in t or "cons" in subtype or "load" in mloc or "house" in mloc):
                    return d
            # fallback: first meter-like
            for d in devs:
                if "METER" in (d.get("TYPE") or "").upper():
                    return d
            return {}

        meterP = pick_meter(devices, "prod")
        meterC = pick_meter(devices, "cons")

        now = int(datetime.now(tz=TZ).timestamp())
        rows = []
        for inv in devices:
            if inv.get("TYPE") != "SOLARBRIDGE":
                continue
            panel_id = inv.get("SERIAL") or inv.get("SN") or f"panel-{len(rows)+1}"
            p_kw = safe_float(inv.get("p_3phsum_kw"))
            v_ac = safe_float(inv.get("vln_3phavg_v"))
            v_dc = safe_float(inv.get("v_mppt1_v"))
            i_dc = safe_float(inv.get("i_mppt1_a"))
            temp_c = safe_float(inv.get("t_htsnk_degc"))
            state = inv.get("STATEDESCR") or inv.get("STATE")
            serial = inv.get("SERIAL")
            rows.append(
                (
                    now,
                    panel_id,
                    p_kw,
                    v_ac,
                    v_dc,
                    i_dc,
                    temp_c,
                    state,
                    serial,
                    swver,
                    GATEWAY_IP,
                )
            )

        if not rows:
            log.info("No inverter rows found; skipping inverter inserts.")

        with db.get_session() as session:
            repo = db.get_telemetry_repository(session)
            if rows:
                repo.insert_panel_rows(
                    [
                        {
                            "ts": row[0],
                            "panel_id": row[1],
                            "p_kw": row[2],
                            "v_ac": row[3],
                            "v_dc": row[4],
                            "i_dc": row[5],
                            "temp_c": row[6],
                            "state": row[7],
                            "serial": row[8],
                            "gateway_swver": row[9],
                            "gateway_ip": row[10],
                        }
                        for row in rows
                    ]
                )

            prod_kw = safe_float(meterP.get("p_3phsum_kw"))
            raw_cons_kw = safe_float(meterC.get("p_3phsum_kw"))
            cons_kw = derive_consumption(raw_cons_kw, prod_kw)
            net_kw = (prod_kw - cons_kw) if (prod_kw is not None and cons_kw is not None) else None
            v_sys = safe_float(meterC.get("v12_v"))
            v_l1 = safe_float(meterC.get("v1n_v"))
            v_l2 = safe_float(meterC.get("v2n_v"))

            repo.insert_house_row(
                {
                    "ts": now,
                    "production_kw": prod_kw,
                    "consumption_kw": cons_kw,
                    "net_kw": net_kw,
                    "v_sys": v_sys,
                    "v_l1": v_l1,
                    "v_l2": v_l2,
                    "gateway_swver": swver,
                    "gateway_ip": GATEWAY_IP,
                },
            )
        POLL_INGEST_SUCCESS_TOTAL.inc()
        INGEST_LAST_SUCCESS_TIMESTAMP_SECONDS.set(now)
        global _last_successful_poll_ts
        _last_successful_poll_ts = now
        log.info("Inserted %d inverter rows and house sample", len(rows))
        return True
    except Exception:
        POLL_INGEST_FAILURE_TOTAL.labels(reason="exception").inc()
        raise


def run_periodic_intelligence_cycle():
    with db.get_session() as session:
        production_repo = db.get_production_intelligence_repository(session)
        consumption_repo = db.get_consumption_intelligence_repository(session)
        production_summary = run_production_intelligence_cycle(repository=production_repo)
        consumption_summary = run_consumption_intelligence_cycle(repository=consumption_repo)
        summary = {
            "production": production_summary,
            "consumption": consumption_summary,
        }
    log.info("Periodic intelligence cycle completed: %s", summary)


def derive_consumption(cons_kw, prod_kw):
    if cons_kw is None:
        return None
    if prod_kw is None:
        return cons_kw
    if cons_kw < 0:
        val = prod_kw + cons_kw  # cons_kw is net import/export
        return max(val, 0)
    return cons_kw


def safe_float(val):
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except Exception:
        return None


def ingest_charger():
    wall_connector_ip = settings.WALL_CONNECTOR_IP
    if not wall_connector_ip:
        log.info("WALL_CONNECTOR_IP not configured; skipping charger ingest")
        return False

    try:
        vitals = fetch_wall_connector_json(wall_connector_ip, "/api/1/vitals")
        if not vitals:
            log.warning("No wall connector vitals fetched this cycle.")
            return False

        lifetime = fetch_wall_connector_json(wall_connector_ip, "/api/1/lifetime") or {}

        now = int(datetime.now(tz=TZ).timestamp())
        current_a = safe_float(vitals.get("vehicle_current_a"))
        voltage_v = safe_float(vitals.get("grid_v"))
        power_kw = (current_a * voltage_v / 1000.0) if (current_a is not None and voltage_v is not None) else None
        evse_state_raw = safe_float(vitals.get("evse_state"))
        evse_state = int(evse_state_raw) if evse_state_raw is not None else None

        with db.get_session() as session:
            repo = db.get_charger_repository(session)
            repo.insert_sample(
                {
                    "ts": now,
                    "vehicle_connected": _safe_bool(vitals.get("vehicle_connected")),
                    "contactor_closed": _safe_bool(vitals.get("contactor_closed")),
                    "evse_state": evse_state,
                    "current_a": current_a,
                    "voltage_v": voltage_v,
                    "power_kw": power_kw,
                    "session_energy_wh": safe_float(vitals.get("session_energy_wh")),
                    "lifetime_energy_wh": safe_float(lifetime.get("lifetime_energy_wh")),
                    "pcba_temp_c": safe_float(vitals.get("pcba_temp_c")),
                    "handle_temp_c": safe_float(vitals.get("handle_temp_c")),
                }
            )

        log.info("Inserted wall connector sample")
        return True
    except Exception:
        raise


def main():
    log.info("Worker started; polling every %ss", POLL_SECONDS)
    while True:
        try:
            ingest()
        except Exception as e:
            log.exception("Poll failed: %s", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

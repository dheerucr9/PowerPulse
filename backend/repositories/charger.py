# pyright: reportMissingImports=false

import base64
import hashlib
import json
from typing import Any, Optional

from sqlalchemy import text

from .telemetry import InvalidCursorError


class ChargerRepository:
    def __init__(self, executor: Any, dialect_name: str):
        self._executor = executor
        self._dialect_name = dialect_name

    def insert_sample(self, row: dict[str, Any]) -> None:
        self._executor.execute(
            text(
                """
                INSERT INTO charger_samples
                (
                    site_id,
                    ts,
                    vehicle_connected,
                    contactor_closed,
                    evse_state,
                    current_a,
                    voltage_v,
                    power_kw,
                    session_energy_wh,
                    lifetime_energy_wh,
                    pcba_temp_c,
                    handle_temp_c
                )
                VALUES
                (
                    'default',
                    :ts,
                    :vehicle_connected,
                    :contactor_closed,
                    :evse_state,
                    :current_a,
                    :voltage_v,
                    :power_kw,
                    :session_energy_wh,
                    :lifetime_energy_wh,
                    :pcba_temp_c,
                    :handle_temp_c
                )
                ON CONFLICT (site_id, ts) DO NOTHING
                """
            ),
            row,
        )

    def fetch_latest(self) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT
                    ts,
                    vehicle_connected,
                    contactor_closed,
                    evse_state,
                    current_a,
                    voltage_v,
                    power_kw,
                    session_energy_wh,
                    lifetime_energy_wh,
                    pcba_temp_c,
                    handle_temp_c
                FROM charger_samples
                WHERE site_id = 'default'
                ORDER BY ts DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None

    def fetch_power_page(
        self,
        start: int,
        end: int,
        interval: str,
        limit: int,
        cursor: Optional[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        signature = self._cursor_signature("charger", start, end, interval)
        decoded = self._decode_cursor(cursor, signature)

        bucket_expr, interval_param = self._bucket_expr(interval)
        params: dict[str, Any] = {
            "start": start,
            "end": end,
            "limit_plus": limit + 1,
        }
        if interval_param is not None:
            params["bucket_interval"] = interval_param

        if decoded:
            params["c_ts"], params["c_id"] = decoded
            raw_cursor = "AND (ts > :c_ts OR (ts = :c_ts AND ts > :c_id))"
            bucketed_cursor = "AND (ts > :c_ts OR (ts = :c_ts AND _cursor_id > :c_id))"
        else:
            raw_cursor = ""
            bucketed_cursor = ""

        if bucket_expr is None:
            sql = f"""
            SELECT ts AS _cursor_id, ts, power_kw
            FROM charger_samples
            WHERE site_id = 'default'
              AND ts BETWEEN :start AND :end
            {raw_cursor}
            ORDER BY ts ASC, _cursor_id ASC
            LIMIT :limit_plus
            """
        else:
            sql = f"""
            SELECT *
            FROM (
                SELECT
                    {bucket_expr} AS ts,
                    AVG(power_kw) AS power_kw,
                    {bucket_expr} AS _cursor_id
                FROM charger_samples
                WHERE site_id = 'default'
                  AND ts BETWEEN :start AND :end
                GROUP BY {bucket_expr}
            ) q
            WHERE 1 = 1
            {bucketed_cursor}
            ORDER BY ts ASC, _cursor_id ASC
            LIMIT :limit_plus
            """

        rows = self._executor.execute(text(sql), params).mappings().all()
        page_rows, page_info = self._build_page_info(rows, limit, signature)
        samples = [{"ts": int(row["ts"]), "power_kw": row["power_kw"]} for row in page_rows]
        return samples, page_info

    def _bucket_expr(self, interval: str) -> tuple[Optional[str], Optional[str]]:
        if interval == "raw":
            return None, None
        if interval == "5m":
            group_secs = 300
            interval_text = "5 minutes"
        elif interval == "1h":
            group_secs = 3600
            interval_text = "1 hour"
        else:
            raise ValueError(f"Unsupported interval: {interval}")

        if self._dialect_name == "postgresql":
            return "EXTRACT(EPOCH FROM time_bucket(CAST(:bucket_interval AS INTERVAL), to_timestamp(ts)))::BIGINT", interval_text
        return f"(ts / {group_secs}) * {group_secs}", None

    @staticmethod
    def _cursor_signature(kind: str, start: int, end: int, interval: str) -> str:
        payload = {"kind": kind, "start": start, "end": end, "interval": interval}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @staticmethod
    def _encode_cursor(ts: int, row_id: int, signature: str) -> str:
        raw = json.dumps({"ts": ts, "id": row_id, "sig": signature}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @classmethod
    def _decode_cursor(cls, cursor: Optional[str], signature: str) -> Optional[tuple[int, int]]:
        if cursor is None:
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
            if payload.get("sig") != signature:
                raise ValueError("cursor signature mismatch")
            ts = int(payload["ts"])
            row_id = int(payload["id"])
            return ts, row_id
        except Exception as exc:
            raise InvalidCursorError("Invalid cursor") from exc

    @classmethod
    def _build_page_info(
        cls,
        rows: list[dict[str, Any]],
        limit: int,
        signature: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        has_more = len(rows) > limit
        rows_page = rows[:limit]
        next_cursor = None
        if has_more and rows_page:
            last = rows_page[-1]
            next_cursor = cls._encode_cursor(int(last["ts"]), int(last["_cursor_id"]), signature)
        return rows_page, {
            "has_more": has_more,
            "next_cursor": next_cursor,
            "returned": len(rows_page),
            "limit": limit,
        }

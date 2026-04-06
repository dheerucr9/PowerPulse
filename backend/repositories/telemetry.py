import base64
import hashlib
import json
from typing import Any, Optional

from sqlalchemy import text


class InvalidCursorError(ValueError):
    pass


class TelemetryRepository:
    def __init__(self, executor: Any, dialect_name: str):
        self._executor = executor
        self._dialect_name = dialect_name

    def fetch_latest_panel_rows(self) -> list[dict[str, Any]]:
        rows = self._executor.execute(
            text(
                """
                SELECT s.*
                FROM panel_power_samples s
                JOIN (
                    SELECT panel_id, MAX(ts) AS max_ts
                    FROM panel_power_samples
                    GROUP BY panel_id
                ) latest
                ON latest.panel_id = s.panel_id AND latest.max_ts = s.ts
                """
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    def fetch_house_page(
        self,
        start: int,
        end: int,
        interval: str,
        limit: int,
        cursor: Optional[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        signature = self._cursor_signature("house", start, end, interval, None)
        decoded = self._decode_cursor(cursor, signature)

        bucket_expr, interval_param = self._bucket_expr(interval)
        params: dict[str, Any] = {"start": start, "end": end, "limit_plus": limit + 1}
        if interval_param is not None:
            params["bucket_interval"] = interval_param

        if decoded:
            params["c_ts"], params["c_id"] = decoded
            # For raw interval, _cursor_id IS ts, so compare ts directly.
            # For bucketed interval, _cursor_id is the bucket value.
            raw_cursor = "AND (ts > :c_ts OR (ts = :c_ts AND ts > :c_id))"
            bucketed_cursor = "AND (ts > :c_ts OR (ts = :c_ts AND _cursor_id > :c_id))"
        else:
            raw_cursor = ""
            bucketed_cursor = ""

        if bucket_expr is None:
            sql = f"""
            SELECT ts AS _cursor_id, ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2
            FROM site_power_samples
            WHERE ts BETWEEN :start AND :end
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
                    AVG(production_kw) AS production_kw,
                    AVG(consumption_kw) AS consumption_kw,
                    AVG(net_kw) AS net_kw,
                    AVG(v_sys) AS v_sys,
                    AVG(v_l1) AS v_l1,
                    AVG(v_l2) AS v_l2,
                    {bucket_expr} AS _cursor_id
                FROM site_power_samples
                WHERE ts BETWEEN :start AND :end
                GROUP BY {bucket_expr}
            ) q
            WHERE 1 = 1
            {bucketed_cursor}
            ORDER BY ts ASC, _cursor_id ASC
            LIMIT :limit_plus
            """

        rows = self._executor.execute(text(sql), params).mappings().all()
        page_rows, page_info = self._build_page_info(rows, limit, signature)
        samples = [
            {
                "ts": int(row["ts"]),
                "production_kw": row["production_kw"],
                "consumption_kw": row["consumption_kw"],
                "net_kw": row["net_kw"],
                "v_sys": row["v_sys"],
                "v_l1": row["v_l1"],
                "v_l2": row["v_l2"],
            }
            for row in page_rows
        ]
        return samples, page_info

    def fetch_panel_page(
        self,
        panel_id: str,
        start: int,
        end: int,
        interval: str,
        limit: int,
        cursor: Optional[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        signature = self._cursor_signature("panel", start, end, interval, panel_id)
        decoded = self._decode_cursor(cursor, signature)

        bucket_expr, interval_param = self._bucket_expr(interval)
        params: dict[str, Any] = {
            "start": start,
            "end": end,
            "panel_id": panel_id,
            "limit_plus": limit + 1,
        }
        if interval_param is not None:
            params["bucket_interval"] = interval_param

        raw_cursor_where = ""
        bucketed_cursor_where = ""
        if decoded:
            params["c_ts"], params["c_id"] = decoded
            raw_cursor_where = "AND (ts > :c_ts OR (ts = :c_ts AND ts > :c_id))"
            bucketed_cursor_where = "AND (ts > :c_ts OR (ts = :c_ts AND _cursor_id > :c_id))"
        if bucket_expr is None:
            sql = f"""
            SELECT ts AS _cursor_id, ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial
            FROM panel_power_samples
            WHERE ts BETWEEN :start AND :end
              AND panel_id = :panel_id
            {raw_cursor_where}
            ORDER BY ts ASC, _cursor_id ASC
            LIMIT :limit_plus
            """
        else:
            sql = f"""
            SELECT *
            FROM (
                SELECT
                    {bucket_expr} AS ts,
                    panel_id,
                    AVG(p_kw) AS p_kw,
                    AVG(v_ac) AS v_ac,
                    AVG(v_dc) AS v_dc,
                    AVG(i_dc) AS i_dc,
                    AVG(temp_c) AS temp_c,
                    MIN(state) AS state,
                    MIN(serial) AS serial,
                    {bucket_expr} AS _cursor_id
                FROM panel_power_samples
                WHERE ts BETWEEN :start AND :end
                  AND panel_id = :panel_id
                GROUP BY panel_id, {bucket_expr}
            ) q
            WHERE 1 = 1
            {bucketed_cursor_where}
            ORDER BY ts ASC, _cursor_id ASC
            LIMIT :limit_plus
            """

        rows = self._executor.execute(text(sql), params).mappings().all()
        page_rows, page_info = self._build_page_info(rows, limit, signature)
        samples = [
            {
                "ts": int(row["ts"]),
                "panel_id": row["panel_id"],
                "p_kw": row["p_kw"],
                "v_ac": row["v_ac"],
                "v_dc": row["v_dc"],
                "i_dc": row["i_dc"],
                "temp_c": row["temp_c"],
                "state": row["state"],
                "serial": row["serial"],
            }
            for row in page_rows
        ]
        return samples, page_info

    def insert_panel_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._executor.execute(
            text(
                """
                INSERT INTO panel_power_samples
                (site_id, ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
                VALUES
                ('default', :ts, :panel_id, :p_kw, :v_ac, :v_dc, :i_dc, :temp_c, :state, :serial, :gateway_swver, :gateway_ip)
                ON CONFLICT (site_id, panel_id, ts) DO NOTHING
                """
            ),
            rows,
        )

    def insert_house_row(self, row: dict[str, Any]) -> None:
        self._executor.execute(
            text(
                """
                INSERT INTO site_power_samples
                (site_id, ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                VALUES
                ('default', :ts, :production_kw, :consumption_kw, :net_kw, :v_sys, :v_l1, :v_l2, :gateway_swver, :gateway_ip)
                ON CONFLICT (site_id, ts) DO NOTHING
                """
            ),
            row,
        )

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
    def _cursor_signature(kind: str, start: int, end: int, interval: str, panel_id: Optional[str]) -> str:
        payload = {"kind": kind, "start": start, "end": end, "interval": interval, "panel_id": panel_id}
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

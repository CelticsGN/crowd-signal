"""Neon/Postgres persistence for simulation memory."""

from __future__ import annotations

import logging
import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _get_connection() -> psycopg2.extensions.connection | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_db_connect_failed: %s", exc)
        return None


def save_simulation_run(
    ticker: str,
    catalyst: str,
    catalyst_bias: float,
    event_type: str,
    direction: str,
    magnitude: str,
    aggregate_stance: float,
    probability_up: float,
    probability_down: float,
    final_bias: float,
    rules_fired: list[str],
) -> None:
    """Save simulation results to NeonDB.

    The call is intentionally fail-open: DB failures are logged and ignored.
    """
    conn = _get_connection()
    if conn is None:
        return

    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO simulation_runs (
                        ticker,
                        catalyst,
                        catalyst_bias,
                        event_type,
                        direction,
                        magnitude,
                        aggregate_stance,
                        probability_up,
                        probability_down,
                        final_bias,
                        rules_fired
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ticker,
                        catalyst,
                        float(catalyst_bias),
                        event_type,
                        direction,
                        magnitude,
                        float(aggregate_stance),
                        float(probability_up),
                        float(probability_down),
                        float(final_bias),
                        rules_fired or [],
                    ),
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_save_failed ticker=%s error=%s", ticker, exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def _normalize_recent_row(row: dict[str, Any]) -> dict[str, Any]:
    created_at = row.get("created_at")
    created_iso = created_at.isoformat() if created_at is not None else ""
    return {
        "catalyst": str(row.get("catalyst") or ""),
        "catalyst_bias": float(row.get("catalyst_bias") or 0.0),
        "aggregate_stance": float(row.get("aggregate_stance") or 0.0),
        "probability_up": float(row.get("probability_up") or 0.0),
        "probability_down": float(row.get("probability_down") or 0.0),
        "direction": str(row.get("direction") or "neutral"),
        "created_at": created_iso,
    }


def get_recent_runs(ticker: str, limit: int = 3) -> list[dict[str, Any]]:
    """Fetch recent simulation memory rows for a ticker.

    Returns an empty list if DB is unavailable.
    """
    conn = _get_connection()
    if conn is None:
        return []

    safe_limit = max(1, min(int(limit), 50))

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    catalyst,
                    catalyst_bias,
                    aggregate_stance,
                    probability_up,
                    probability_down,
                    direction,
                    created_at
                FROM simulation_runs
                WHERE ticker = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (ticker.upper(), safe_limit),
            )
            rows = cursor.fetchall()
            return [_normalize_recent_row(dict(row)) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_fetch_failed ticker=%s error=%s", ticker, exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

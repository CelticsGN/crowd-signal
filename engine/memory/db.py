"""Neon/Postgres persistence for simulation memory."""

from __future__ import annotations

import logging
import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
import yfinance as yf

logger = logging.getLogger(__name__)


def _fetch_price_at_simulation(ticker: str) -> float | None:
    """Fetch current market price for *ticker*.

    Returns None when unavailable so persistence remains fail-open.
    """
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            return None
        last_close = data["Close"].iloc[-1]
        return float(last_close)
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_at_simulation_fetch_failed ticker=%s error=%s", ticker, exc)
        return None


def _get_connection() -> psycopg2.extensions.connection | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_db_connect_failed: %s", exc)
        return None


def get_db_connection() -> psycopg2.extensions.connection | None:
    """Public DB connection helper for other engine modules.

    Returns:
        A psycopg2 connection or None when DB is unavailable.
    """
    return _get_connection()


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
    *,
    verdict_action: str | None = None,
    verdict_confidence: int | None = None,
    verdict_entry_price: float | None = None,
    verdict_target_price: float | None = None,
    verdict_stop_price: float | None = None,
) -> None:
    """Save simulation results to NeonDB.

    The call is intentionally fail-open: DB failures are logged and ignored.
    """
    conn = _get_connection()
    if conn is None:
        return

    price_at_simulation = _fetch_price_at_simulation(ticker)

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
                        rules_fired,
                        price_at_simulation,
                        verdict_action,
                        verdict_confidence,
                        verdict_entry_price,
                        verdict_target_price,
                        verdict_stop_price
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        float(price_at_simulation) if price_at_simulation is not None else None,
                        verdict_action,
                        verdict_confidence,
                        float(verdict_entry_price) if verdict_entry_price is not None else None,
                        float(verdict_target_price) if verdict_target_price is not None else None,
                        float(verdict_stop_price) if verdict_stop_price is not None else None,
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


def get_latest_simulation_run_id(ticker: str, catalyst: str) -> str | None:
    """Return the most recent simulation run id for ticker+catalyst.

    This is used by batch scanner workflows that need to link derived rows
    to a simulation run created by the existing save path.
    """
    conn = _get_connection()
    if conn is None:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id
                FROM simulation_runs
                WHERE ticker = %s
                  AND catalyst = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ticker.upper(), catalyst),
            )
            row = cursor.fetchone() or {}
            value = row.get("id")
            return str(value) if value is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("latest_simulation_run_fetch_failed ticker=%s error=%s", ticker, exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def update_verdict_on_latest_run(
    ticker: str,
    catalyst: str,
    *,
    verdict_action: str,
    verdict_confidence: int,
    verdict_entry_price: float | None,
    verdict_target_price: float | None,
    verdict_stop_price: float | None,
    verdict_range_low: float | None = None,
    verdict_range_high: float | None = None,
) -> None:
    """Patch verdict fields onto the most recent simulation_runs row for ticker+catalyst.

    Called by the route layer after blended probabilities have been computed,
    so the persisted verdict matches what the user actually sees.
    Fail-open: DB errors are logged and swallowed.
    """
    conn = _get_connection()
    if conn is None:
        return

    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE simulation_runs
                    SET verdict_action       = %s,
                        verdict_confidence   = %s,
                        verdict_entry_price  = %s,
                        verdict_target_price = %s,
                        verdict_stop_price   = %s,
                        verdict_range_low    = %s,
                        verdict_range_high   = %s
                    WHERE id = (
                        SELECT id FROM simulation_runs
                        WHERE ticker = %s AND catalyst = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                    """,
                    (
                        verdict_action,
                        verdict_confidence,
                        float(verdict_entry_price) if verdict_entry_price is not None else None,
                        float(verdict_target_price) if verdict_target_price is not None else None,
                        float(verdict_stop_price) if verdict_stop_price is not None else None,
                        float(verdict_range_low) if verdict_range_low is not None else None,
                        float(verdict_range_high) if verdict_range_high is not None else None,
                        ticker.upper(),
                        catalyst,
                    ),
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("verdict_update_failed ticker=%s error=%s", ticker, exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


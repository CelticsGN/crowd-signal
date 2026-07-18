"""Backtesting scorer for 24h directional prediction accuracy."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
import yfinance as yf

logger = logging.getLogger(__name__)


def _get_connection() -> psycopg2.extensions.connection | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, connect_timeout=5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("backtesting_db_connect_failed error=%s", exc)
        return None


def _fetch_current_price(ticker: str) -> float | None:
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.warning("backtesting_price_fetch_failed ticker=%s error=%s", ticker, exc)
        return None


def _derive_actual_direction(price_at_simulation: float, actual_price: float) -> str:
    # Deprecated: The rigorous ATR-based logic is now used inline in score_pending_predictions.
    if price_at_simulation <= 0:
        return "neutral"
    move_pct = ((actual_price - price_at_simulation) / price_at_simulation) * 100.0
    if move_pct > 0.5:
        return "up"
    if move_pct < -0.5:
        return "down"
    return "neutral"


def _derive_predicted_direction(probability_up: float, probability_down: float) -> str:
    # Deprecated: Replaced by verdict_action check inline.
    if probability_up > 0.55:
        return "up"
    if probability_down > 0.55:
        return "down"
    return "neutral"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _refresh_accuracy_summary(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH agg AS (
                SELECT
                    ticker,
                    COUNT(CASE WHEN verdict_action IN ('BUY', 'SELL') THEN 1 END)::int AS directional_total,
                    COALESCE(SUM(CASE WHEN verdict_action IN ('BUY', 'SELL') AND prediction_correct THEN 1 ELSE 0 END), 0)::int AS directional_correct,
                    COUNT(CASE WHEN verdict_action = 'HOLD' THEN 1 END)::int AS hold_total,
                    COALESCE(SUM(CASE WHEN verdict_action = 'HOLD' AND prediction_correct THEN 1 ELSE 0 END), 0)::int AS hold_correct
                FROM simulation_runs
                WHERE prediction_correct IS NOT NULL
                GROUP BY ticker
            )
            INSERT INTO accuracy_summary (
                ticker,
                directional_total,
                directional_correct,
                directional_accuracy_pct,
                hold_total,
                hold_correct,
                hold_accuracy_pct,
                last_updated
            )
            SELECT
                agg.ticker,
                agg.directional_total,
                agg.directional_correct,
                CASE WHEN agg.directional_total > 0 THEN (agg.directional_correct::float / agg.directional_total::float) * 100.0 ELSE 0.0 END,
                agg.hold_total,
                agg.hold_correct,
                CASE WHEN agg.hold_total > 0 THEN (agg.hold_correct::float / agg.hold_total::float) * 100.0 ELSE 0.0 END,
                NOW()
            FROM agg
            ON CONFLICT (ticker)
            DO UPDATE SET
                directional_total = EXCLUDED.directional_total,
                directional_correct = EXCLUDED.directional_correct,
                directional_accuracy_pct = EXCLUDED.directional_accuracy_pct,
                hold_total = EXCLUDED.hold_total,
                hold_correct = EXCLUDED.hold_correct,
                hold_accuracy_pct = EXCLUDED.hold_accuracy_pct,
                last_updated = NOW()
            """
        )

        cursor.execute(
            """
            SELECT
                COUNT(CASE WHEN verdict_action IN ('BUY', 'SELL') THEN 1 END)::int AS directional_total,
                COALESCE(SUM(CASE WHEN verdict_action IN ('BUY', 'SELL') AND prediction_correct THEN 1 ELSE 0 END), 0)::int AS directional_correct,
                COUNT(CASE WHEN verdict_action = 'HOLD' THEN 1 END)::int AS hold_total,
                COALESCE(SUM(CASE WHEN verdict_action = 'HOLD' AND prediction_correct THEN 1 ELSE 0 END), 0)::int AS hold_correct
            FROM simulation_runs
            WHERE prediction_correct IS NOT NULL
            """
        )
        global_row = cursor.fetchone() or (0, 0, 0, 0)
        dir_total = _safe_int(global_row[0])
        dir_correct = _safe_int(global_row[1])
        hold_total = _safe_int(global_row[2])
        hold_correct = _safe_int(global_row[3])
        
        dir_acc = (dir_correct / dir_total * 100.0) if dir_total > 0 else 0.0
        hold_acc = (hold_correct / hold_total * 100.0) if hold_total > 0 else 0.0

        cursor.execute("SELECT id FROM accuracy_summary_global ORDER BY last_updated DESC LIMIT 1")
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE accuracy_summary_global
                SET
                    directional_total = %s,
                    directional_correct = %s,
                    directional_accuracy_pct = %s,
                    hold_total = %s,
                    hold_correct = %s,
                    hold_accuracy_pct = %s,
                    last_updated = NOW()
                WHERE id = %s
                """,
                (dir_total, dir_correct, dir_acc, hold_total, hold_correct, hold_acc, existing[0]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO accuracy_summary_global (
                    directional_total,
                    directional_correct,
                    directional_accuracy_pct,
                    hold_total,
                    hold_correct,
                    hold_accuracy_pct,
                    last_updated
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (dir_total, dir_correct, dir_acc, hold_total, hold_correct, hold_acc),
            )


def score_pending_predictions() -> dict[str, float | int]:
    """Score unscored runs from 24-48h ago and refresh summaries."""
    conn = _get_connection()
    if conn is None:
        return {"scored_count": 0, "correct_count": 0, "accuracy_pct": 0.0}

    now = datetime.now(timezone.utc)
    window_end = now - timedelta(hours=24)
    window_start = now - timedelta(hours=48)

    scored_count = 0
    correct_count = 0

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        ticker,
                        probability_up,
                        probability_down,
                        price_at_simulation,
                        verdict_action,
                        verdict_entry_price,
                        verdict_target_price,
                        verdict_stop_price,
                        verdict_range_low,
                        verdict_range_high
                    FROM simulation_runs
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND actual_direction IS NULL
                      AND price_at_simulation IS NOT NULL
                    ORDER BY created_at ASC
                    """,
                    (window_start, window_end),
                )
                rows = cursor.fetchall() or []

                for row in rows:
                    try:
                        ticker = str(row.get("ticker", "")).upper()
                        if not ticker:
                            continue

                        price_at_simulation = _safe_float(row.get("price_at_simulation"))
                        if price_at_simulation <= 0:
                            continue

                        actual_price = _fetch_current_price(ticker)
                        if actual_price is None:
                            continue

                        verdict_action = str(row.get("verdict_action", "") or "HOLD").upper()
                        v_entry = _safe_float(row.get("verdict_entry_price") or price_at_simulation)
                        v_target = _safe_float(row.get("verdict_target_price"))
                        v_stop = _safe_float(row.get("verdict_stop_price"))
                        v_low = _safe_float(row.get("verdict_range_low"))
                        v_high = _safe_float(row.get("verdict_range_high"))

                        prediction_correct = False
                        
                        if verdict_action == "BUY":
                            if v_target > v_entry:
                                # 1 ATR is roughly (target - entry) / 3 based on engine logic
                                # 0.5 ATR threshold:
                                threshold = v_entry + ((v_target - v_entry) / 6.0)
                                prediction_correct = actual_price >= threshold
                            else:
                                # Fallback: 0.5% move
                                prediction_correct = actual_price >= v_entry * 1.005
                        elif verdict_action == "SELL":
                            if v_target > 0 and v_target < v_entry:
                                threshold = v_entry - ((v_entry - v_target) / 6.0)
                                prediction_correct = actual_price <= threshold
                            else:
                                # Fallback: 0.5% move down
                                prediction_correct = actual_price <= v_entry * 0.995
                        else:  # HOLD
                            if v_low > 0 and v_high > 0:
                                prediction_correct = v_low <= actual_price <= v_high
                            else:
                                # Fallback: stayed within 1% band
                                prediction_correct = (v_entry * 0.99) <= actual_price <= (v_entry * 1.01)

                        cursor.execute(
                            """
                            UPDATE simulation_runs
                            SET
                                actual_price_24h = %s,
                                actual_direction = %s,
                                prediction_correct = %s
                            WHERE id = %s
                            """,
                            (actual_price, "scored", prediction_correct, row.get("id")),
                        )

                        scored_count += 1
                        if prediction_correct:
                            correct_count += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("score_run_failed run_id=%s error=%s", row.get("id"), exc)
                        continue

            _refresh_accuracy_summary(conn)

        accuracy_pct = (correct_count / scored_count * 100.0) if scored_count > 0 else 0.0
        return {
            "scored_count": scored_count,
            "correct_count": correct_count,
            "overall_accuracy_pct": accuracy_pct,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("score_pending_predictions_failed error=%s", exc)
        return {"scored_count": 0, "correct_count": 0, "accuracy_pct": 0.0}
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def get_ticker_accuracy(ticker: str) -> dict[str, float | int]:
    """Fetch directional accuracy for one ticker with zero-safe fallback."""
    conn = _get_connection()
    if conn is None:
        return {"total": 0, "correct": 0, "accuracy_pct": 0.0}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT directional_total, directional_correct, directional_accuracy_pct,
                       hold_total, hold_correct, hold_accuracy_pct
                FROM accuracy_summary
                WHERE ticker = %s
                LIMIT 1
                """,
                (ticker.upper(),),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "directional_total": 0, "directional_correct": 0, "directional_accuracy_pct": 0.0,
                    "hold_total": 0, "hold_correct": 0, "hold_accuracy_pct": 0.0
                }
            return {
                "directional_total": _safe_int(row.get("directional_total")),
                "directional_correct": _safe_int(row.get("directional_correct")),
                "directional_accuracy_pct": _safe_float(row.get("directional_accuracy_pct")),
                "hold_total": _safe_int(row.get("hold_total")),
                "hold_correct": _safe_int(row.get("hold_correct")),
                "hold_accuracy_pct": _safe_float(row.get("hold_accuracy_pct")),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_ticker_accuracy_failed ticker=%s error=%s", ticker, exc)
        return {"total": 0, "correct": 0, "accuracy_pct": 0.0}
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def get_accuracy_stats() -> dict[str, Any]:
    """Fetch global and per-ticker directional accuracy summaries."""
    conn = _get_connection()
    if conn is None:
        return {
            "global_accuracy": {"total": 0, "correct": 0, "accuracy_pct": 0.0},
            "by_ticker": {},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT directional_total, directional_correct, directional_accuracy_pct,
                       hold_total, hold_correct, hold_accuracy_pct, last_updated
                FROM accuracy_summary_global
                ORDER BY last_updated DESC
                LIMIT 1
                """
            )
            global_row = cursor.fetchone()

            cursor.execute(
                """
                SELECT ticker, directional_total, directional_correct, directional_accuracy_pct,
                       hold_total, hold_correct, hold_accuracy_pct, last_updated
                FROM accuracy_summary
                ORDER BY directional_total DESC, ticker ASC
                """
            )
            ticker_rows = cursor.fetchall() or []

        by_ticker: dict[str, dict[str, float | int]] = {}
        last_updated_dt: datetime | None = None

        for row in ticker_rows:
            ticker = str(row.get("ticker", "")).upper()
            if not ticker:
                continue
            by_ticker[ticker] = {
                "directional_total": _safe_int(row.get("directional_total")),
                "directional_correct": _safe_int(row.get("directional_correct")),
                "directional_accuracy_pct": _safe_float(row.get("directional_accuracy_pct")),
                "hold_total": _safe_int(row.get("hold_total")),
                "hold_correct": _safe_int(row.get("hold_correct")),
                "hold_accuracy_pct": _safe_float(row.get("hold_accuracy_pct")),
            }
            row_updated = row.get("last_updated")
            if isinstance(row_updated, datetime):
                if last_updated_dt is None or row_updated > last_updated_dt:
                    last_updated_dt = row_updated

        if global_row:
            global_accuracy = {
                "directional_total": _safe_int(global_row.get("directional_total")),
                "directional_correct": _safe_int(global_row.get("directional_correct")),
                "directional_accuracy_pct": _safe_float(global_row.get("directional_accuracy_pct")),
                "hold_total": _safe_int(global_row.get("hold_total")),
                "hold_correct": _safe_int(global_row.get("hold_correct")),
                "hold_accuracy_pct": _safe_float(global_row.get("hold_accuracy_pct")),
            }
            global_updated = global_row.get("last_updated")
            if isinstance(global_updated, datetime):
                if last_updated_dt is None or global_updated > last_updated_dt:
                    last_updated_dt = global_updated
        else:
            global_accuracy = {
                "directional_total": 0, "directional_correct": 0, "directional_accuracy_pct": 0.0,
                "hold_total": 0, "hold_correct": 0, "hold_accuracy_pct": 0.0
            }

        last_updated = (last_updated_dt or datetime.now(timezone.utc)).isoformat()
        return {
            "global_accuracy": global_accuracy,
            "by_ticker": by_ticker,
            "last_updated": last_updated,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_accuracy_stats_failed error=%s", exc)
        return {
            "global_accuracy": {"total": 0, "correct": 0, "accuracy_pct": 0.0},
            "by_ticker": {},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

def get_recent_scored_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = _get_connection()
    if conn is None:
        return []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT ticker, verdict_action as action, verdict_confidence as confidence,
                       verdict_entry_price as entry_price, verdict_target_price as target_price,
                       verdict_stop_price as stop_price, verdict_range_low as range_low,
                       verdict_range_high as range_high, prediction_correct,
                       actual_price_24h, created_at
                FROM simulation_runs
                WHERE prediction_correct IS NOT NULL
                  AND verdict_action IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                result.append({
                    'ticker': row.get('ticker'),
                    'action': row.get('action'),
                    'confidence': row.get('confidence'),
                    'entry_price': row.get('entry_price'),
                    'target_price': row.get('target_price'),
                    'stop_price': row.get('stop_price'),
                    'range_low': row.get('range_low'),
                    'range_high': row.get('range_high'),
                    'prediction_correct': row.get('prediction_correct'),
                    'actual_price_24h': row.get('actual_price_24h'),
                    'created_at': row.get('created_at').isoformat() if row.get('created_at') else ''
                })
            return result
    except Exception as exc:
        logger.warning("get_recent_scored_runs_failed error=%s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

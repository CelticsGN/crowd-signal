from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from api.ticker_catalog import TICKERS
from engine.data.news_connector import NewsConnector
from engine.memory.db import get_db_connection
from engine.sim.llm_parser import analyze_catalyst
from engine.sim.runner import run_simulation

logger = logging.getLogger(__name__)

_HIGH_KEYWORDS = [
    "earnings", "profit", "revenue", "quarterly", "beat", "miss", "guidance", "results",
    "ceo", "insider", "buyback", "merger", "acquisition", "fda", "approval", "lawsuit",
    "fraud", "bankruptcy", "rbi", "sebi",
]
_MEDIUM_KEYWORDS = [
    "upgrade", "downgrade", "target", "analyst", "partnership", "contract", "expansion", "layoffs", "dividend",
]
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def score_headline_priority(headline: str) -> str:
    text = (headline or "").lower()
    if any(word in text for word in _HIGH_KEYWORDS):
        return "high"
    if any(word in text for word in _MEDIUM_KEYWORDS):
        return "medium"
    return "low"


async def scan_catalysts_for_ticker(ticker: str) -> dict[str, Any] | None:
    try:
        records = await NewsConnector().fetch(ticker)

        ranked: list[dict[str, Any]] = []
        for item in records:
            headline = str(item.get("headline", "")).strip()
            if not headline:
                continue
            ranked.append(
                {
                    "ticker": ticker,
                    "catalyst": headline,
                    "headline": headline,
                    "source": str(item.get("source", "news")),
                    "priority": score_headline_priority(headline),
                }
            )

        logger.info("[SCANNER] %s: headlines found: %s", ticker, len(ranked))

        if ranked:
            ranked.sort(key=lambda row: _PRIORITY_RANK.get(str(row.get("priority", "low")), 99))
            ranked[0]["_headline_count"] = len(ranked)
            return ranked[0]

        logger.warning("[SCANNER] %s: no catalyst found - skipping", ticker)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("[SCANNER] %s: FAILED - %s: %s", ticker, type(exc).__name__, str(exc))
        return None


def _crowd_verdict(probability_up: float, probability_down: float) -> str:
    if probability_up > 0.6:
        return "BULLISH"
    if probability_down > 0.6:
        return "BEARISH"
    return "NEUTRAL"


def _verdict_strength(probability_up: float, probability_down: float) -> str:
    strongest = max(probability_up, probability_down)
    if strongest > 0.75:
        return "STRONG"
    if strongest > 0.60:
        return "MODERATE"
    return "WEAK"


def _currency_for_ticker(ticker: str) -> str:
    return "INR" if str(ticker).upper().endswith(".NS") else "USD"


def _market_tickers(market: str) -> list[str]:
    market_upper = (market or "ALL").upper()
    if market_upper == "IN":
        return [row["symbol"] for row in TICKERS.get("IN", [])]
    if market_upper == "US":
        return [row["symbol"] for row in TICKERS.get("US", [])]

    combined: list[str] = []
    for region in ("US", "IN"):
        combined.extend([row["symbol"] for row in TICKERS.get(region, [])])
    return combined


async def run_daily_scan(market: str = "ALL") -> dict[str, Any]:
    summary = {
        "tickers_scanned": 0,
        "catalysts_found": 0,
        "simulations_run": 0,
        "report_date": str(date.today()),
        "errors": [],
        "skipped_tickers": [],
    }

    conn = get_db_connection()
    if conn is None:
        logger.warning("run_daily_scan_db_unavailable")
        return summary

    us_entries: list[dict[str, Any]] = []
    in_entries: list[dict[str, Any]] = []

    try:
        for ticker in _market_tickers(market):
            logger.info("[SCANNER] Starting scan for %s", ticker)
            summary["tickers_scanned"] += 1
            try:
                logger.info("[SCANNER] %s: fetching headlines...", ticker)
                scanned = await scan_catalysts_for_ticker(ticker)
                if scanned is None:
                    logger.warning("[SCANNER] %s: 0 headlines returned from NewsConnector", ticker)
                    summary["skipped_tickers"].append(ticker)
                    await asyncio.sleep(2 + random.uniform(0, 1))
                    continue

                summary["catalysts_found"] += 1
                logger.info("[SCANNER] %s: headlines found: %s", ticker, int(scanned.get("_headline_count", 1)))
                catalyst = str(scanned["catalyst"])
                logger.info("[SCANNER] %s: top catalyst: %s", ticker, catalyst)

                analysis = analyze_catalyst(catalyst)
                event_type = str(getattr(getattr(analysis, "extraction", None), "event_type", ""))
                catalyst_bias = float(getattr(analysis, "final_bias", 0.0))

                logger.info("[SCANNER] %s: running simulation...", ticker)
                sim_result = run_simulation(ticker, catalyst, 120)
                summary["simulations_run"] += 1

                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO daily_catalysts (
                            ticker,
                            catalyst,
                            headline,
                            source,
                            priority,
                            catalyst_bias,
                            event_type,
                            market_date
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
                        """,
                        (
                            ticker,
                            catalyst,
                            str(scanned.get("headline", catalyst)),
                            str(scanned.get("source", "news")),
                            str(scanned.get("priority", "low")),
                            catalyst_bias,
                            event_type,
                        ),
                    )
                conn.commit()

                probability_up = float(sim_result.get("probability_up", 0.0))
                probability_down = float(sim_result.get("probability_down", 0.0))
                logger.info(
                    "[SCANNER] %s: simulation complete - up:%s down:%s",
                    ticker,
                    probability_up,
                    probability_down,
                )

                entry = {
                    "ticker": ticker,
                    "catalyst": catalyst,
                    "headline": str(scanned.get("headline", catalyst)),
                    "priority": str(scanned.get("priority", "low")).upper(),
                    "aggregate_stance": float(sim_result.get("mean_stance", 0.0)),
                    "probability_up": probability_up,
                    "probability_down": probability_down,
                    "crowd_verdict": _crowd_verdict(probability_up, probability_down),
                    "verdict_strength": _verdict_strength(probability_up, probability_down),
                    "currency": _currency_for_ticker(ticker),
                }

                if entry["currency"] == "INR":
                    in_entries.append(entry)
                else:
                    us_entries.append(entry)

                await asyncio.sleep(2 + random.uniform(0, 1))
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                logger.error("[SCANNER] %s: FAILED - %s: %s", ticker, type(exc).__name__, str(exc))
                summary["errors"].append(f"{ticker}: {type(exc).__name__}: {str(exc)}")
                await asyncio.sleep(2 + random.uniform(0, 1))
                continue

        accuracy_this_week = 0.0
        correct_this_week = 0
        total_this_week = 0
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT total_predictions, correct_predictions, accuracy_pct
                FROM accuracy_summary_global
                ORDER BY last_updated DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone() or {}
            total_this_week = int(row.get("total_predictions") or 0)
            correct_this_week = int(row.get("correct_predictions") or 0)
            accuracy_this_week = float(row.get("accuracy_pct") or 0.0)

        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO daily_report (
                    report_date,
                    us_entries,
                    in_entries,
                    accuracy_this_week,
                    correct_this_week,
                    total_this_week
                )
                VALUES (CURRENT_DATE, %s::jsonb, %s::jsonb, %s, %s, %s)
                ON CONFLICT (report_date)
                DO UPDATE SET
                    us_entries = EXCLUDED.us_entries,
                    in_entries = EXCLUDED.in_entries,
                    generated_at = NOW()
                """,
                (
                    Json(us_entries),
                    Json(in_entries),
                    accuracy_this_week,
                    correct_this_week,
                    total_this_week,
                ),
            )
        conn.commit()
        logger.info(
            "[SCANNER] Scan complete: %s scanned, %s catalysts, %s simulations",
            summary["tickers_scanned"],
            summary["catalysts_found"],
            summary["simulations_run"],
        )
        return summary
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        logger.error("[SCANNER] GLOBAL FAILED - %s: %s", type(exc).__name__, str(exc))
        summary["errors"].append(f"global: {type(exc).__name__}: {str(exc)}")
        return summary
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def get_todays_report() -> dict[str, Any] | None:
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM daily_report
                WHERE report_date = CURRENT_DATE
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None

            us_entries = row.get("us_entries") or []
            in_entries = row.get("in_entries") or []

            if isinstance(us_entries, str):
                us_entries = json.loads(us_entries)
            if isinstance(in_entries, str):
                in_entries = json.loads(in_entries)

            return {
                "report_date": str(row.get("report_date")),
                "generated_at": row.get("generated_at").isoformat() if row.get("generated_at") else "",
                "us_entries": list(us_entries),
                "in_entries": list(in_entries),
                "accuracy_this_week": float(row.get("accuracy_this_week") or 0.0),
                "correct_this_week": int(row.get("correct_this_week") or 0),
                "total_this_week": int(row.get("total_this_week") or 0),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_todays_report_failed error=%s", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

"""Run a batch of live simulations using real data from catalyst_scanner.py"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.scanner.catalyst_scanner import scan_catalysts_for_ticker
from engine.sim.runner import run_simulation
from engine.memory.db import get_db_connection, save_simulation_run, update_verdict_on_latest_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mixed batch of 15 tickers
BATCH_TICKERS = [
    # Large-cap tech
    "AAPL", "MSFT", "NVDA", "TSLA",
    # Large-cap non-tech (financials, energy, healthcare)
    "JPM", "XOM", "UNH", "DIS", "BA",
    # Mid-cap
    "PLTR", "SOFI", "ROKU",
    # India tickers
    "RELIANCE.NS", "TCS.NS", "INFY.NS"
]

async def main() -> None:
    conn = get_db_connection()
    if not conn:
        logger.error("DATABASE_URL not set or connection failed. Cannot run batch.")
        return
        
    logger.info(f"Starting live batch for {len(BATCH_TICKERS)} tickers...")

    for ticker in BATCH_TICKERS:
        try:
            logger.info(f"--- Fetching real catalyst for {ticker} ---")
            
            scanned = await scan_catalysts_for_ticker(ticker)
            if not scanned:
                logger.warning(f"Skipping {ticker}: No catalyst found.")
                continue
                
            catalyst_text = scanned["catalyst"]
            logger.info(f"Found catalyst for {ticker}: {catalyst_text}")
            
            # Fetch actual live current price
            import yfinance as yf
            current_price = 100.0
            try:
                data = yf.Ticker(ticker).history(period="1d", interval="1m")
                if not data.empty:
                    current_price = float(data["Close"].iloc[-1])
                else:
                    logger.warning(f"Could not fetch live price for {ticker}. Using fallback 100.0.")
            except Exception as e:
                logger.warning(f"Error fetching live price for {ticker}: {e}")
                
            from engine.data.aggregator import MarketContext
            
            logger.info(f"Running simulation for {ticker} at price {current_price:.2f}...")
            result = run_simulation(
                ticker=ticker,
                catalyst=catalyst_text,
                horizon_minutes=120,
                market_context=MarketContext(current_price=current_price, volume_vs_avg=1.0)
            )
            
            # Extract fields for save_simulation_run
            cat_analysis = result.get("catalyst_analysis", {})
            extraction = cat_analysis.get("extraction", {})
            rules_fired = [
                str(entry.get("rule", ""))
                for entry in cat_analysis.get("reasoning", [])
                if str(entry.get("rule", ""))
            ]
            
            save_simulation_run(
                ticker=ticker,
                catalyst=catalyst_text,
                catalyst_bias=cat_analysis.get("final_bias", 0.0),
                event_type=extraction.get("event_type", "macro"),
                direction=extraction.get("direction", "neutral"),
                magnitude=extraction.get("magnitude", "weak"),
                aggregate_stance=result.get("mean_stance", 0.0),
                probability_up=result.get("probability_up", 0.0),
                probability_down=result.get("probability_down", 0.0),
                final_bias=cat_analysis.get("final_bias", 0.0),
                rules_fired=rules_fired
            )
            
            verdict = result.get("verdict")
            if verdict:
                update_verdict_on_latest_run(
                    ticker,
                    catalyst_text,
                    verdict_action=verdict.get("action"),
                    verdict_confidence=verdict.get("confidence"),
                    verdict_entry_price=verdict.get("entry_price"),
                    verdict_target_price=verdict.get("target_price"),
                    verdict_stop_price=verdict.get("stop_price"),
                    verdict_range_low=verdict.get("range_low"),
                    verdict_range_high=verdict.get("range_high")
                )
                logger.info(f"Successfully simulated and saved run for {ticker} (Verdict: {verdict.get('action')})")
            else:
                logger.warning(f"No verdict generated for {ticker}")
                
        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")

    conn.close()
    logger.info("Live batch complete! Runs have been saved and will be scored automatically in 24-48h.")

if __name__ == "__main__":
    asyncio.run(main())

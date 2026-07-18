"""Seed test simulations backdated by 25 hours to test the scorer."""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.sim.runner import run_simulation
from engine.memory.db import get_db_connection, save_simulation_run, update_verdict_on_latest_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEST_CATALYSTS = {
    "AAPL": "Blowout Q3 earnings report, iPhone 16 supercycle confirmed with 20% year-over-year revenue growth.",
    "MSFT": "Major cloud outage affecting Azure globally, enterprise customers threatening to churn.",
    "NVDA": "Unveils next-gen AI chip with 5x efficiency, securing massive pre-orders from Meta and Google.",
    "AMZN": "AWS growth slowing down significantly, missing analyst estimates for the second consecutive quarter.",
    "GOOGL": "DOJ antitrust ruling forces potential breakup of the ad business, causing massive uncertainty.",
    "META": "User engagement hits all-time high with new AI features, ad revenue up 35%.",
    "TSLA": "Unexpected vehicle recall affecting 2 million cars due to critical autopilot safety flaw.",
    "BRK-B": "Warren Buffett announces massive new stake in energy sector, market reacts positively.",
    "LLY": "FDA approves new breakthrough weight-loss drug, expected to double revenue next year.",
    "V": "Consumer spending data shows sharp decline, signaling potential recession and lower transaction volumes.",
    "JPM": "Federal reserve hikes rates unexpectedly, boosting net interest income projections.",
    "UNH": "Medicare reimbursement rates slashed by 5%, significantly hurting forward guidance.",
    "XOM": "Oil prices surge above $95/barrel on geopolitical tensions, margins expected to hit record highs.",
    "MA": "Major regulatory fine in the EU for antitrust violations, impacting European margins.",
    "PG": "Strong defensive rotation as market panics, raising dividend by 10% on solid cash flow."
}

def main() -> None:
    conn = get_db_connection()
    if not conn:
        logger.error("DATABASE_URL not set or connection failed. Cannot seed DB.")
        return
        
    logger.info(f"Starting seed script for {len(TEST_CATALYSTS)} tickers...")

    for ticker, catalyst_text in TEST_CATALYSTS.items():
        try:
            logger.info(f"Running simulation for {ticker}...")
            
            # Fetch price from 2 days ago so that today's close represents 24 hours of real movement
            import yfinance as yf
            current_price = 100.0
            try:
                data = yf.Ticker(ticker).history(period="5d", interval="1d")
                if len(data) >= 2:
                    current_price = float(data["Close"].iloc[-2])
            except Exception:
                pass
                
            result = run_simulation(
                ticker=ticker,
                catalyst=catalyst_text,
                horizon_minutes=120,
                market_context=MarketContext(current_price=current_price, volume_vs_avg=1.0)
            )
            
            # Extract fields for save_simulation_run
            cat_analysis = result.get("catalyst_analysis", {})
            save_simulation_run(
                ticker=ticker,
                catalyst=catalyst_text,
                catalyst_bias=cat_analysis.get("final_bias", 0.0),
                event_type=cat_analysis.get("event_type", "macro"),
                direction=cat_analysis.get("direction", "neutral"),
                magnitude=cat_analysis.get("magnitude", "low"),
                aggregate_stance=result.get("mean_stance", 0.0),
                probability_up=result.get("probability_up", 0.0),
                probability_down=result.get("probability_down", 0.0),
                final_bias=cat_analysis.get("final_bias", 0.0),
                rules_fired=[]
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
                
                # Now backdate the row to 25 hours ago so the scorer will pick it up immediately
                with conn:
                    with conn.cursor() as cursor:
                        # Find the ID of the most recent run for this ticker
                        cursor.execute(
                            "SELECT id FROM simulation_runs WHERE ticker = %s ORDER BY created_at DESC LIMIT 1",
                            (ticker,)
                        )
                        row = cursor.fetchone()
                        if row:
                            run_id = row[0]
                            backdated_time = datetime.now(timezone.utc) - timedelta(hours=25)
                            cursor.execute(
                                "UPDATE simulation_runs SET created_at = %s WHERE id = %s",
                                (backdated_time, run_id)
                            )
                            logger.info(f"Successfully seeded and backdated run for {ticker} (Verdict: {verdict.get('action')})")
                        else:
                            logger.warning(f"Could not find inserted row for {ticker} to backdate.")
            else:
                logger.warning(f"No verdict generated for {ticker}")
                
        except Exception as e:
            logger.error(f"Failed to seed {ticker}: {e}")

    conn.close()
    logger.info("Seed script complete! You can now trigger score_pending_predictions().")

if __name__ == "__main__":
    main()

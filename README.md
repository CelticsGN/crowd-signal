# Crowd Signal

Crowd Signal is an AI-assisted market crowd simulation system for intraday sentiment mapping.

Instead of generating a single deterministic prediction, the system models how multiple trading personas react to a catalyst (earnings, headlines, social momentum) over a short time horizon and returns a probabilistic crowd-state summary.

It now supports both US equities and Indian NSE equities, plus explainable vocal-agent reactions and live accuracy tracking.

## What It Does

- Simulates trader personas such as retail, whales, and algos.
- Applies weighted peer influence over iterative ticks.
- Adds catalyst gravity to represent persistent narrative pressure.
- Produces aggregate stance, probability-up/down, persona-level confidence, and catalyst reasoning.
- Generates optional vocal crowd narrative reactions via Groq (US and India market variants).
- Persists simulation memory and applies lightweight memory bias.
- Scores historical predictions against later market movement and tracks directional accuracy.
- Exposes FastAPI endpoints consumed by a Next.js frontend.

## Core Idea

Markets often move because of crowd behavior before fundamentals fully settle.

Crowd Signal is designed as a decision-support layer:
- Assistive, not automated.
- Probabilistic, not certain.
- Explainable by design.

## Architecture

- Backend API: FastAPI in `api/`
- Simulation engine: persona dynamics in `engine/sim/`
- Data connectors: market/news/social connectors in `engine/data/`
- Memory and persistence: Neon/Postgres helpers in `engine/memory/`
- Backtesting and accuracy scoring: `engine/backtesting/`
- Frontend: Next.js app in `web/`

## API Quick Start

Main endpoints:
- `POST /api/v1/simulate`
- `GET /api/v1/tickers`
- `GET /api/v1/accuracy`
- `GET /api/v1/accuracy/{ticker}`

Example payload:

```json
{
  "ticker": "RELIANCE.NS",
  "catalyst": "Earnings beat by 20%",
  "horizon_minutes": 120
}
```

Example response shape:

```json
{
  "ticker": "RELIANCE.NS",
  "catalyst": "Earnings beat by 20%",
  "horizon_minutes": 120,
  "aggregate_stance": 0.63,
  "probability_up": 0.74,
  "probability_down": 0.21,
  "personas": [
    { "persona": "retail_bull", "stance": 0.78, "confidence": 0.71, "weight": 0.35 },
    { "persona": "retail_bear", "stance": 0.22, "confidence": 0.67, "weight": 0.35 },
    { "persona": "whale", "stance": 0.58, "confidence": 0.65, "weight": 0.10 },
    { "persona": "algo", "stance": 0.55, "confidence": 0.69, "weight": 0.20 }
  ],
  "catalyst_analysis": { "final_bias": 0.57, "reasoning": [] },
  "memory_context": [],
  "crowd_narrative": [
    { "agent_id": "indian_retail_047", "persona": "retail_bull", "message": "...", "stance": 0.81 }
  ],
  "current_price": 1394.8,
  "volume_vs_avg": 0.96,
  "reddit_mentions": 0,
  "reddit_sentiment": 0.0
}
```

`GET /api/v1/tickers` returns grouped market catalogs:

```json
{
  "US": [
    { "symbol": "NVDA", "name": "NVIDIA", "exchange": "NASDAQ", "currency": "USD" }
  ],
  "IN": [
    { "symbol": "RELIANCE.NS", "name": "Reliance Industries", "exchange": "NSE", "currency": "INR" }
  ]
}
```

`GET /api/v1/accuracy` returns global and per-ticker directional accuracy:

```json
{
  "global_accuracy": { "total": 127, "correct": 87, "accuracy_pct": 68.5 },
  "by_ticker": {
    "NVDA": { "total": 43, "correct": 31, "accuracy_pct": 72.1 },
    "RELIANCE.NS": { "total": 18, "correct": 11, "accuracy_pct": 61.1 }
  },
  "last_updated": "2026-03-17T12:34:56.000000+00:00"
}
```

## Local Development

### Backend

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Optional environment variables:

- `DATABASE_URL`: enable memory persistence and backtesting accuracy summaries.
- `GROQ_API_KEY`: enable vocal crowd narrative generation.

### Frontend

```bash
cd web
corepack pnpm install
corepack pnpm run dev
```

Optional frontend environment variable:

- `BACKEND_URL` (defaults to `http://localhost:8000`)

## License and Usage Rights

This project is intentionally **not open source**.

- Copyright (c) 2026 Crowd Signal Team.
- All rights reserved.
- No permission is granted to use, copy, modify, distribute, sublicense, or sell this software without prior written authorization.

See [LICENSE](LICENSE) for full terms.

## Important Disclaimer

Crowd Signal provides probabilistic analysis for research and decision support only.
It is not financial advice, not investment solicitation, and not an execution system.

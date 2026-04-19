# Crowd Signal

![Crowd Signal Hero](docs/images/readme-hero.svg)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-000000?logo=next.js&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Live%20Stream-4CC9F0)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-critical)

Crowd Signal is an AI-powered market crowd simulator for intraday catalysts.

Instead of producing a single deterministic call, it models how different trading personas react over time, streams those reactions live, and returns probabilistic outcomes with explainable reasoning.

## Why This Exists

Markets move on narrative, positioning, and crowd behavior long before consensus catches up.

Crowd Signal focuses on that behavior layer:

- Simulate crowd dynamics, not point forecasts.
- Keep outputs probabilistic and explainable.
- Show the full chain: catalyst -> bias -> agent evolution -> outcome.

## What You Get

- Tick-by-tick simulation over a configurable horizon.
- Persona-level modeling (`retail_bull`, `retail_bear`, `whale`, `algo`).
- Live WebSocket stream with ordered, turn-by-turn agent conversation.
- Catalyst intelligence (LLM extraction + graph-based bias adjustments).
- Market context enrichment (news, reddit, yfinance) when available.
- Memory-aware biasing from recent runs.
- Accuracy scoring and daily market report generation.
- US + India (`.NS`) support.

## Visual Overview

![Crowd Signal Flow](docs/images/readme-flow.svg)

## Live Stream Experience

The stream now emits conversation turns in sequence so the feed feels like an actual dialogue, not a bulk dump.

Example live event lines:

```text
[TICK] Tick 7/24 | mean=0.481
[AGENT THOUGHT] Turn 7 | Retail Bear 023 (retail_bear): Replying to Retail Bull 047: I am staying defensive on NVDA; catalyst risk still points to downside.
[TICK] Tick 8/24 | mean=0.502
[AGENT THOUGHT] Turn 8 | Whale 003 (whale): Replying to Retail Bear 023: I still like the upside in NVDA; catalyst momentum remains bullish.
```

## Repository Layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI app, REST routes, and WebSocket route |
| `engine/sim/` | Core simulation, streaming runner, narrator, catalyst parser |
| `engine/data/` | Market/news/reddit/yfinance connectors + context aggregation |
| `engine/memory/` | Postgres-backed simulation memory and retrieval |
| `engine/backtesting/` | Accuracy scoring + scheduler jobs |
| `engine/scanner/` | Daily catalyst scanning and report population |
| `web/` | Next.js frontend (simulate page, live feed, analysis UI) |
| `render.yaml` | Render backend deployment config |

## Quick Start (Local)

### 1) Prerequisites

- Python 3.11+
- Node.js 20+
- pnpm (recommended via `corepack`)

### 2) Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Start API:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) Frontend Setup

```bash
cd web
corepack pnpm install
copy .env.local.example .env.local
corepack pnpm dev
```

Frontend runs at `http://localhost:3000`.

## Environment Variables

### Backend (`.env`)

Required for full behavior:

| Variable | Why It Matters |
|---|---|
| `DATABASE_URL` | Stores simulation memory + report rows + scoring data |
| `ADMIN_KEY` | Protects `POST /api/v1/daily-report/trigger` |
| `GROQ_API_KEY` | Enables catalyst extraction + narrator generation |

Recommended / feature-enabling:

| Variable | Purpose |
|---|---|
| `REDDIT_CLIENT_ID` | Reddit ingestion |
| `REDDIT_CLIENT_SECRET` | Reddit ingestion |
| `REDDIT_USER_AGENT` | Reddit API compliance |
| `FINNHUB_API_KEY` | News enrichment |
| `ALPHA_VANTAGE_API_KEY` | News enrichment |
| `GNEWS_API_KEY` | News enrichment |
| `GROQ_BASE_URL` | Optional override (defaults to Groq OpenAI-compatible URL) |

### Frontend (`web/.env.local`)

| Variable | Example |
|---|---|
| `BACKEND_URL` | `https://your-render-url.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://your-render-url.onrender.com` |

## API and WebSocket Reference

### REST Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `POST` | `/api/v1/simulate` | Run one simulation request |
| `GET` | `/api/v1/tickers` | Supported US/IN ticker catalogs |
| `GET` | `/api/v1/accuracy` | Global + per-ticker directional accuracy |
| `GET` | `/api/v1/accuracy/{ticker}` | Ticker-specific accuracy detail |
| `GET` | `/api/v1/daily-report` | Daily catalyst report (`ready` or `generating`) |
| `POST` | `/api/v1/daily-report/trigger` | Manual report scan trigger (requires `X-Admin-Key`) |

### WebSocket Endpoint

| Route | Purpose |
|---|---|
| `/ws/simulate` | Stream simulation lifecycle and conversation turns live |

Common stream event types:

- `init`
- `catalyst_parsed`
- `agents_spawned`
- `tick`
- `agent_thought`
- `herd_detected`
- `narrator` or `narrator_error`
- `complete`

## Example Simulation Request

```bash
curl -X POST http://localhost:8000/api/v1/simulate \
  -H "Content-Type: application/json" \
  -d "{\"ticker\":\"NVDA\",\"catalyst\":\"Earnings beat and guidance raise\",\"horizon_minutes\":120}"
```

## Scheduling and Daily Reports

On backend startup, APScheduler jobs are registered for:

- Hourly backtesting scorer job.
- Weekday India daily scan job.
- Weekday US daily scan job.

Manual trigger endpoint is also available:

```bash
curl -X POST https://your-api-host/api/v1/daily-report/trigger \
  -H "X-Admin-Key: your-admin-key"
```

## Deploy Notes

### Backend (Render)

- `render.yaml` is configured for `uvicorn api.main:app`.
- Set all runtime env vars in Render dashboard.

### Frontend (Vercel)

- Uses `pnpm` lockfile (`web/pnpm-lock.yaml`).
- Set `BACKEND_URL` and `NEXT_PUBLIC_WS_URL`.
- Vercel Analytics is integrated in app layout.

## Troubleshooting

### `ws_disconnected` after `Progress 24/24`

Expected behavior. The stream closes after `complete` is emitted.

### `status: generating` on `/api/v1/daily-report`

Report has not been generated yet for the day. Trigger manually or wait for scheduler window.

### `[REDDIT] credentials not configured - skipping`

Reddit credentials are missing. Simulation still runs, but without reddit enrichment.

### YFinance `Too Many Requests`

Connector retries once, then enters cooldown to reduce repeated rate-limit hammering.

## License and Usage Rights

This project is intentionally **not open source**.

- Copyright (c) 2026 Crowd Signal Team.
- All rights reserved.
- No permission is granted to use, copy, modify, distribute, sublicense, or sell this software without prior written authorization.

See [LICENSE](LICENSE) for full terms.

## Important Disclaimer

Crowd Signal provides probabilistic analysis for research and decision support only.
It is not financial advice, not investment solicitation, and not an execution system.

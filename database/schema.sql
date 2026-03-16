CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS simulation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker VARCHAR(10) NOT NULL,
  catalyst TEXT NOT NULL,
  catalyst_bias FLOAT NOT NULL,
  event_type VARCHAR(50),
  direction VARCHAR(20),
  magnitude VARCHAR(20),
  aggregate_stance FLOAT NOT NULL,
  probability_up FLOAT NOT NULL,
  probability_down FLOAT NOT NULL,
  final_bias FLOAT NOT NULL,
  rules_fired TEXT[],
  agent_count INTEGER DEFAULT 100,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_ticker
ON simulation_runs(ticker);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_created
ON simulation_runs(created_at DESC);

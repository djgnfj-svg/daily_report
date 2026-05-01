-- supabase/migrations/0002_daily_metrics_scores.sql
-- 가공 결과(결정적)와 분석 결과(LLM)를 별도 테이블로 적재.
-- 재현 검증·하네스 평가에 쓰이도록 model 필드 포함.

CREATE TABLE daily_metrics (
  ticker TEXT NOT NULL,
  date DATE NOT NULL,
  ma20 NUMERIC,
  ma60 NUMERIC,
  ma200 NUMERIC,
  rsi14 NUMERIC,
  pos_52w_pct NUMERIC,
  volume_ratio_20d NUMERIC,
  volatility_pct NUMERIC,
  max_drawdown_pct NUMERIC,
  sharpe_naive NUMERIC,
  PRIMARY KEY (ticker, date)
);

CREATE TABLE daily_scores (
  ticker TEXT NOT NULL,
  date DATE NOT NULL,
  fundamental_score INT,
  fundamental_summary TEXT,
  fundamental_key_metrics JSONB,
  risk_score INT,
  risk_summary TEXT,
  combined_score NUMERIC,
  is_top_pick BOOLEAN DEFAULT FALSE,
  model TEXT,
  PRIMARY KEY (ticker, date)
);
CREATE INDEX ON daily_scores(date);
CREATE INDEX ON daily_scores(ticker, date DESC);

ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_scores  ENABLE ROW LEVEL SECURITY;

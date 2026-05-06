-- 0003_outcomes_30d.sql
-- 주간 전환에 따라 1d/7d → 7d/30d 검증으로 변경. 1d/7d 컬럼은 호환성 위해 nullable 유지.
ALTER TABLE outcomes
  ADD COLUMN IF NOT EXISTS price_30d NUMERIC,
  ADD COLUMN IF NOT EXISTS return_30d NUMERIC,
  ADD COLUMN IF NOT EXISTS spy_return_30d NUMERIC;

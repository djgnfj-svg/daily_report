-- supabase/migrations/0001_init.sql
-- MorningBrief initial schema

CREATE TABLE prices (
  ticker TEXT NOT NULL,
  date DATE NOT NULL,
  open NUMERIC,
  high NUMERIC,
  low NUMERIC,
  close NUMERIC,
  volume BIGINT,
  PRIMARY KEY (ticker, date)
);

CREATE TABLE financials (
  ticker TEXT NOT NULL,
  period TEXT NOT NULL,
  revenue NUMERIC,
  net_income NUMERIC,
  eps NUMERIC,
  fcf NUMERIC,
  total_debt NUMERIC,
  total_equity NUMERIC,
  source TEXT,
  filed_at DATE,
  PRIMARY KEY (ticker, period)
);

CREATE TABLE filings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  form_type TEXT,
  filed_at TIMESTAMPTZ,
  url TEXT,
  summary TEXT
);
CREATE INDEX ON filings(ticker, filed_at DESC);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  body_md TEXT,
  trace_url TEXT,
  cost_usd NUMERIC(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  signal TEXT CHECK(signal IN ('BUY','HOLD','SELL')),
  confidence INT,
  thesis TEXT,
  is_top_pick BOOLEAN DEFAULT FALSE
);
CREATE INDEX ON signals(report_id);
CREATE INDEX ON signals(ticker);

CREATE TABLE outcomes (
  signal_id UUID PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
  price_at_report NUMERIC,
  price_1d NUMERIC,
  price_7d NUMERIC,
  return_1d NUMERIC,
  return_7d NUMERIC
);

CREATE TABLE subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','confirmed','unsubscribed')),
  confirm_token TEXT UNIQUE,
  unsub_token TEXT UNIQUE NOT NULL,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON subscribers(status);

-- RLS: lock everything; service_role bypasses RLS automatically.
ALTER TABLE prices       ENABLE ROW LEVEL SECURITY;
ALTER TABLE financials   ENABLE ROW LEVEL SECURITY;
ALTER TABLE filings      ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports      ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE outcomes     ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers  ENABLE ROW LEVEL SECURITY;

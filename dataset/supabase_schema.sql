-- supabase_schema.sql — ConfMind PostgreSQL schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- or via psql: psql $DATABASE_URL -f dataset/supabase_schema.sql

-- ─────────────────────────────────────────────
-- events table — one row per conference/event
-- Populated by P3 (scraping pipeline / ETL)
-- Read by agents during planning
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS events (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name           TEXT NOT NULL,
    date                 TEXT,                       -- ISO 8601 "YYYY-MM-DD"
    city                 TEXT,
    country              TEXT,                       -- ISO 3166-1 alpha-2
    category             TEXT,                       -- AI / Web3 / ClimateTech …
    theme                TEXT,
    sponsors             JSONB DEFAULT '[]',         -- list of sponsor name strings
    speakers             JSONB DEFAULT '[]',         -- list of speaker name strings
    exhibitors           JSONB DEFAULT '[]',         -- list of exhibitor name strings
    ticket_price_early   NUMERIC(10,2) DEFAULT 0,
    ticket_price_general NUMERIC(10,2) DEFAULT 0,
    ticket_price_vip     NUMERIC(10,2) DEFAULT 0,
    estimated_attendance INTEGER DEFAULT 0,
    venue_name           TEXT,
    venue_capacity       INTEGER,
    source_url           TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (event_name, city)                        -- prevent duplicate scrape rows
);

CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_events_country  ON events (country);
CREATE INDEX IF NOT EXISTS idx_events_date     ON events (date);

-- ─────────────────────────────────────────────
-- plans table — one row per completed conference plan
-- Written by FastAPI after each successful /api/run-plan call
-- Read by /api/output/{plan_id}
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS plans (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payload    JSONB NOT NULL,                       -- full AgentState as JSON
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Row Level Security (RLS)
-- Enable if using Supabase Auth — disable for internal service-role access
-- ─────────────────────────────────────────────

-- ALTER TABLE events ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE plans  ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "service role only" ON events USING (true) WITH CHECK (true);
-- CREATE POLICY "service role only" ON plans  USING (true) WITH CHECK (true);

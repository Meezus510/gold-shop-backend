-- ============================================================
-- Migration: Add metals table and update items table
-- Run once against your database (local and Render).
-- Safe to run on an empty database — existing columns are
-- altered with ADD COLUMN IF NOT EXISTS / ALTER COLUMN.
-- ============================================================

BEGIN;

-- 1. Create metals table
CREATE TABLE IF NOT EXISTS metals (
    id                    SERIAL PRIMARY KEY,
    name                  VARCHAR NOT NULL UNIQUE,
    symbol                VARCHAR NOT NULL UNIQUE,
    spot_price_api_symbol VARCHAR NOT NULL,
    purity_denominator    INTEGER NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Seed default metals
INSERT INTO metals (name, symbol, spot_price_api_symbol, purity_denominator)
VALUES
    ('Gold',     'XAU', 'gold',     24),
    ('Silver',   'XAG', 'silver',   1000),
    ('Platinum', 'XPT', 'platinum', 1000)
ON CONFLICT (symbol) DO NOTHING;

-- 3. Add new columns to items
ALTER TABLE items
    ADD COLUMN IF NOT EXISTS metal_id      INTEGER REFERENCES metals(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS purity_karat  FLOAT,
    ADD COLUMN IF NOT EXISTS cost          FLOAT,
    ADD COLUMN IF NOT EXISTS sell_price    FLOAT;

-- 4. Make weight_grams and price_multiplier nullable
--    (they're now optional for non-metal items)
ALTER TABLE items
    ALTER COLUMN weight_grams    DROP NOT NULL,
    ALTER COLUMN price_multiplier DROP NOT NULL;

-- 5. (Optional) Back-fill existing items as gold 22k
--    Uncomment and adjust if you want to tag existing items:
-- UPDATE items
-- SET metal_id     = (SELECT id FROM metals WHERE symbol = 'XAU'),
--     purity_karat = 22
-- WHERE metal_id IS NULL;

COMMIT;

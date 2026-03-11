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
-- spot_price_api_symbol uses gold-api.com symbols (same as ISO: XAU, XAG, XPT)
INSERT INTO metals (name, symbol, spot_price_api_symbol, purity_denominator)
VALUES
    ('Gold',     'XAU', 'XAU', 24),
    ('Silver',   'XAG', 'XAG', 1000),
    ('Platinum', 'XPT', 'XPT', 1000)
ON CONFLICT (symbol) DO NOTHING;

-- 3. Create purchase_locations table and add new columns to items
CREATE TABLE IF NOT EXISTS purchase_locations (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS metal_id              INTEGER REFERENCES metals(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS purity_karat          FLOAT,
    ADD COLUMN IF NOT EXISTS cost                  FLOAT,
    ADD COLUMN IF NOT EXISTS sell_price            FLOAT,
    ADD COLUMN IF NOT EXISTS flat_markup           FLOAT,
    ADD COLUMN IF NOT EXISTS quantity              INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS purchase_location_id  INTEGER REFERENCES purchase_locations(id) ON DELETE SET NULL;

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

-- 6. Create item_images table (replaces single image_url on items)
CREATE TABLE IF NOT EXISTS item_images (
    id       SERIAL PRIMARY KEY,
    item_id  INTEGER NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    url      TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_item_images_item_id ON item_images(item_id);

-- Migrate any existing image_url values from items → item_images
INSERT INTO item_images (item_id, url, position)
SELECT item_id, image_url, 0
FROM items
WHERE image_url IS NOT NULL AND image_url <> '';

ALTER TABLE items DROP COLUMN IF EXISTS image_url;

COMMIT;

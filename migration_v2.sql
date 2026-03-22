-- =============================================================================
-- Migration v2: New pricing model + visibility
-- =============================================================================
-- Run Phase 1 immediately. Run Phase 2 only after all code is deployed and
-- you have verified nothing references the deprecated columns.
-- =============================================================================

BEGIN;

-- ── Phase 1 ──────────────────────────────────────────────────────────────────

-- New columns
ALTER TABLE items
    ADD COLUMN purchase_date      DATE,
    ADD COLUMN markup_flat        NUMERIC(10, 2),
    ADD COLUMN markup_loan        NUMERIC(10, 2),
    ADD COLUMN listed_price_flat  NUMERIC(10, 2),
    ADD COLUMN listed_price_loan  NUMERIC(10, 2),
    ADD COLUMN is_visible         BOOLEAN NOT NULL DEFAULT TRUE;

-- Rename sell_price for semantic clarity (Python attr keeps the old name via column mapping)
ALTER TABLE items RENAME COLUMN sell_price TO actual_sell_price;

-- Seed listed_price_flat from existing price so current items are not left blank
UPDATE items SET listed_price_flat = price WHERE price IS NOT NULL;

-- Deprecate old pricing columns — rename so they are invisible to the new ORM
-- but data is preserved until Phase 2 confirms everything is working.
ALTER TABLE items RENAME COLUMN price            TO _deprecated_price;
ALTER TABLE items RENAME COLUMN price_multiplier TO _deprecated_price_multiplier;
ALTER TABLE items RENAME COLUMN flat_markup      TO _deprecated_flat_markup;

COMMIT;


-- =============================================================================
-- Phase 2 — run only after full deployment is verified
-- =============================================================================
-- ALTER TABLE items
--     DROP COLUMN _deprecated_price,
--     DROP COLUMN _deprecated_price_multiplier,
--     DROP COLUMN _deprecated_flat_markup;

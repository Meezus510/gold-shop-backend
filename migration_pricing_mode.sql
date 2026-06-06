-- =============================================================================
-- Migration: Add item pricing mode for mixed/manual metal items
-- =============================================================================
-- METAL_DYNAMIC keeps current full-metal behavior.
-- MANUAL lets mixed-material items keep metal/purity metadata while using direct
-- flat prices and skipping market-value recalculation.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pricingmode') THEN
        CREATE TYPE pricingmode AS ENUM ('METAL_DYNAMIC', 'MANUAL');
    END IF;
END
$$;

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS pricing_mode pricingmode NOT NULL DEFAULT 'METAL_DYNAMIC';

COMMIT;

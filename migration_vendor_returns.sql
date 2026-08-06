-- Add vendor returns as an inventory outcome distinct from customer returns.

ALTER TYPE itemstatus ADD VALUE IF NOT EXISTS 'RETURNED_TO_VENDOR';

BEGIN;

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS quantity_returned_to_vendor INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS vendor_refund_amount NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS returned_to_vendor_at TIMESTAMPTZ;

COMMIT;

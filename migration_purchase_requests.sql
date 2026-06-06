-- =============================================================================
-- Migration: Customer purchase requests with encrypted PII
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchaserequeststatus') THEN
        CREATE TYPE purchaserequeststatus AS ENUM ('PENDING', 'ACCEPTED', 'DECLINED');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS customers (
    id              SERIAL PRIMARY KEY,
    name_encrypted  TEXT NOT NULL,
    phone_encrypted TEXT NOT NULL,
    phone_hash      VARCHAR(64) NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_customers_phone_hash ON customers(phone_hash);

CREATE TABLE IF NOT EXISTS purchase_requests (
    id                    SERIAL PRIMARY KEY,
    customer_id            INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    item_id                INTEGER NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    status                 purchaserequeststatus NOT NULL DEFAULT 'PENDING',
    item_number_snapshot   INTEGER,
    item_name_snapshot     VARCHAR NOT NULL,
    listed_price_snapshot  NUMERIC(10, 2),
    decided_by_admin_id    INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    decided_at             TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_purchase_requests_customer_id ON purchase_requests(customer_id);
CREATE INDEX IF NOT EXISTS ix_purchase_requests_item_id ON purchase_requests(item_id);
CREATE INDEX IF NOT EXISTS ix_purchase_requests_status ON purchase_requests(status);
CREATE INDEX IF NOT EXISTS ix_purchase_requests_created_at ON purchase_requests(created_at);

COMMIT;

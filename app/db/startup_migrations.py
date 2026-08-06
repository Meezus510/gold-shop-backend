import logging

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


def run_startup_migrations(engine: Engine) -> None:
    """Apply small, idempotent migrations required before serving requests."""
    if engine.dialect.name != "postgresql":
        return

    # PostgreSQL enum values must be committed before they can be used. Run the
    # enum alteration in autocommit mode, then add the related table columns.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            text("ALTER TYPE itemstatus ADD VALUE IF NOT EXISTS 'RETURNED_TO_VENDOR'")
        )

    with engine.begin() as connection:
        connection.execute(text("""
            ALTER TABLE items
                ADD COLUMN IF NOT EXISTS quantity_returned_to_vendor
                    INTEGER NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS vendor_refund_amount NUMERIC(10, 2),
                ADD COLUMN IF NOT EXISTS returned_to_vendor_at TIMESTAMPTZ
        """))

    logger.info("Startup database migrations are up to date")

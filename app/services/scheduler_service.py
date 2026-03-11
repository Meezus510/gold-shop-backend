"""
APScheduler integration for weekly price sync.
The scheduler is started in app/main.py via the lifespan context manager.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.services.price_sync_service import (
    SYNC_INTERVAL_DAYS,
    get_or_create_config,
    recalculate_all,
    record_sync,
)

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")
_JOB_ID = "weekly_price_sync"


# ── Background job ──────────────────────────────────────────────────────────────

async def _price_sync_job() -> None:
    """Runs weekly: recalculates all metal item prices and records the result."""
    logger.info("Weekly price sync: starting")
    from app.db.database import SessionLocal  # imported here to avoid circular imports

    db: Session = SessionLocal()
    try:
        next_sync = datetime.now(timezone.utc) + timedelta(days=SYNC_INTERVAL_DAYS)
        result = recalculate_all(db, force_fresh_prices=True)
        record_sync(db, result["updated"], next_sync)
        _reschedule(next_sync)
        logger.info(
            "Weekly price sync complete: %d updated, %d skipped",
            result["updated"], result["skipped"],
        )
    except Exception as exc:
        logger.error("Weekly price sync failed: %s", exc)
    finally:
        db.close()


# ── Public API ──────────────────────────────────────────────────────────────────

def start(db: Session) -> None:
    """Called once at app startup. Schedules the next sync based on persisted config."""
    config = get_or_create_config(db)
    now = datetime.now(timezone.utc)

    if config.next_sync_at and config.next_sync_at > now:
        next_run = config.next_sync_at
    else:
        # First run ever, or missed — schedule 7 days from now
        next_run = now + timedelta(days=SYNC_INTERVAL_DAYS)

    _scheduler.add_job(
        _price_sync_job,
        trigger="date",
        run_date=next_run,
        id=_JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Price sync scheduler started. Next run: %s", next_run.isoformat())


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def get_next_run_time() -> datetime | None:
    job = _scheduler.get_job(_JOB_ID)
    return job.next_run_time if job else None


def reset_schedule(db: Session, next_sync: datetime) -> None:
    """Called after a manual full sync to push the next auto-sync 7 days out."""
    _reschedule(next_sync)
    # Persist the new next_sync_at so it survives a restart
    config = get_or_create_config(db)
    config.next_sync_at = next_sync
    db.commit()


def _reschedule(next_run: datetime) -> None:
    """Replace the one-shot 'date' job with a fresh one for the new run time."""
    _scheduler.add_job(
        _price_sync_job,
        trigger="date",
        run_date=next_run,
        id=_JOB_ID,
        replace_existing=True,
    )
    logger.info("Price sync rescheduled. Next run: %s", next_run.isoformat())

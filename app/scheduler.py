import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.models import UpdateLog
from app.fcc_loader import fcc_loader

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def check_and_update():
    """Check if an update is needed and run it if so."""
    logger.info("Checking if database update is needed...")

    if fcc_loader.is_loading:
        logger.info("Update already in progress, skipping")
        return

    db = SessionLocal()
    try:
        # Get last successful update
        latest = (
            db.query(UpdateLog)
            .filter(UpdateLog.status == "success")
            .order_by(UpdateLog.update_time.desc())
            .first()
        )

        needs_update = False

        if not latest:
            logger.info("No previous update found, running initial update")
            needs_update = True
        else:
            days_since_update = (
                datetime.now(timezone.utc) - latest.update_time.replace(tzinfo=timezone.utc)
            ).days
            logger.info("Days since last update: %d", days_since_update)

            if days_since_update >= settings.auto_update_days:
                logger.info("Update threshold reached, running update")
                needs_update = True

        if needs_update:
            result = fcc_loader.run_full_update()
            logger.info("Update result: %s", result)
        else:
            logger.info("No update needed")

    except Exception as e:
        logger.error("Error checking for updates: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler for automatic updates."""
    # Check daily if update is needed
    scheduler.add_job(
        check_and_update,
        trigger=IntervalTrigger(hours=24),
        id="fcc_auto_update",
        name="FCC Database Auto Update",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started - checking for updates every 24 hours")

    # Run initial check on startup (after a short delay to let the app start)
    scheduler.add_job(
        check_and_update,
        trigger="date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=30),
        id="fcc_initial_check",
        name="FCC Initial Update Check",
    )


def stop_scheduler():
    """Stop the background scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler stopped")

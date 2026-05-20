"""
APScheduler — Weekly ECHA data sync + startup check.
Usage: import and call start_scheduler() from main.py
"""
import logging
import traceback
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from echa_scraper import run_scraper, ECHA_DOWNLOADS
except ImportError:
    from backend.echa_scraper import run_scraper, ECHA_DOWNLOADS

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


# ======================================================================
# Job Functions
# ======================================================================

def weekly_echa_sync():
    """Run all available ECHA dataset downloads."""
    logger.info(f"[SCHEDULER] Weekly ECHA sync started at {datetime.now().isoformat()}")
    try:
        results = run_scraper()
        for key, res in results.items():
            if "error" in res:
                logger.error(f"[SCHEDULER] {key}: {res['error']}")
            else:
                logger.info(f"[SCHEDULER] {key}: imported={res.get('imported',0)}, updated={res.get('updated',0)}, skipped={res.get('skipped',0)}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Weekly sync failed: {e}")
        logger.error(traceback.format_exc())


# ======================================================================
# Public API
# ======================================================================

def start_scheduler():
    """Start APScheduler with weekly ECHA sync."""
    if scheduler.running:
        logger.info("[SCHEDULER] Already running")
        return

    # Weekly sync: every Sunday at 02:00 UTC
    scheduler.add_job(
        weekly_echa_sync,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_echa_sync",
        name="ECHA Weekly Data Sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("[SCHEDULER] Background scheduler started — next weekly sync on Sunday 02:00 UTC")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[SCHEDULER] Shutdown complete")


def trigger_echa_sync_now():
    """Manual trigger for admin use."""
    weekly_echa_sync()

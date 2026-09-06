import logging
import os
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from importrr import metrics
from importrr.config import Config
from importrr.sort import Sort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main_process():
    """Run one full pass over every configuration section.

    Returns the number of sections that raised. A per-section failure is logged
    and skipped so the remaining sections still run; only an error outside the
    section loop (e.g. an unreadable config) propagates.
    """
    try:
        logger.info("Starting importrr application")
        config = Config()

        total_sections = len(config.get_data())
        logger.info(f"Processing {total_sections} configuration sections")

        failed = 0
        for i, d in enumerate(config.get_data(), 1):
            try:
                logger.info(
                    f"Processing section {i}/{total_sections}: {d.get('album')}"
                )
                sort = Sort(d.get("album"), d.get("archive"), d.get("section"))
                for import_dir in d.get("import"):
                    sort.launch(import_dir)
            except Exception as e:  # noqa: BLE001
                failed += 1
                metrics.SECTION_FAILURES_TOTAL.labels(
                    section=d.get("section") or "unknown"
                ).inc()
                logger.error(f"Failed to process section {i}: {e}")
                logger.debug(f"Section details: {d}")
                # Continue with next section instead of crashing
                continue

        if failed:
            logger.warning(
                f"Importrr application completed with {failed} failed section(s)"
            )
        else:
            logger.info("Importrr application completed successfully")
        return failed

    except Exception as e:
        logger.error(f"Fatal error in importrr application: {e}")
        logger.debug("Full traceback:", exc_info=True)
        raise  # Re-raise for scheduler to handle


class ImportrrScheduler:
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.scheduler.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run_import_job(self):
        """Wrapper function to run the import process with proper logging"""
        job_start = datetime.now()  # noqa: DTZ005
        logger.info("=" * 60)
        logger.info(f"Starting scheduled import job at {job_start}")
        logger.info("=" * 60)

        try:
            # Run the main import process
            with metrics.JOB_DURATION_SECONDS.time():
                failed = main_process()

            job_end = datetime.now()  # noqa: DTZ005
            duration = job_end - job_start
            if failed:
                metrics.JOB_RUNS_TOTAL.labels(outcome="partial").inc()
                logger.warning("=" * 60)
                logger.warning(
                    f"Import job finished at {job_end} with {failed} failed section(s)"
                )
                logger.warning(f"Total duration: {duration}")
                logger.warning("=" * 60)
            else:
                metrics.JOB_RUNS_TOTAL.labels(outcome="success").inc()
                metrics.LAST_SUCCESS_TIMESTAMP.set_to_current_time()
                logger.info("=" * 60)
                logger.info(f"Import job completed successfully at {job_end}")
                logger.info(f"Total duration: {duration}")
                logger.info("=" * 60)

        except Exception as e:  # noqa: BLE001
            metrics.JOB_RUNS_TOTAL.labels(outcome="error").inc()

            job_end = datetime.now()  # noqa: DTZ005
            duration = job_end - job_start
            logger.error("=" * 60)
            logger.error(f"Import job failed at {job_end}")
            logger.error(f"Duration before failure: {duration}")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            # Don't re-raise - we want the scheduler to continue running

    def start(self):
        """Start the scheduler"""
        try:
            # Add the job - every 2 hours from 8 AM to 10 PM
            self.scheduler.add_job(
                func=self.run_import_job,
                trigger=CronTrigger(minute=0, hour="8-22/2"),
                id="import_job",
                name="Import Media Files",
                misfire_grace_time=300,  # 5 minutes grace period
                coalesce=True,  # If multiple jobs are queued, run only the latest
                max_instances=1,  # Only one instance at a time
            )

            logger.info("Importrr scheduler started (every 2 hours from 8 AM to 10 PM)")
            logger.info(
                "Scheduler configured with max_instances=1 to prevent overlapping jobs"
            )

            # Run once on startup
            logger.info("Running initial import on startup...")
            self.run_import_job()

            # Start the scheduler for future runs
            logger.info("Starting scheduled runs...")
            self.scheduler.start()

        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler shutdown requested")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            logger.debug("Full traceback:", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    logger.info("Starting importrr scheduler service")
    if os.getenv("METRICS_ENABLED", "true").lower() in ("1", "true", "yes"):
        metrics.start(os.getenv("METRICS_PORT", "9201"))
    scheduler = ImportrrScheduler()
    scheduler.start()

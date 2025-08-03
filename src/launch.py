import logging
import signal
import sys
import os
from datetime import datetime

from importrr.config import Config
from importrr.sort import Sort

# Check if we're running as scheduler or one-time
SCHEDULER_MODE = os.getenv('SCHEDULER_MODE', 'false').lower() == 'true'

if SCHEDULER_MODE:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO,  # Change to INFO by default, DEBUG is too verbose
                    format='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

def main_process():
    """Main processing function that can be called from scheduler or directly"""
    try:
        logger.info("Starting importrr application")
        config = Config()
        
        total_sections = len(config.get_data())
        logger.info(f"Processing {total_sections} configuration sections")
        
        for i, d in enumerate(config.get_data(), 1):
            try:
                logger.info(f"Processing section {i}/{total_sections}: {d.get('album')}")
                sort = Sort(d.get('album'), d.get('archive'))
                for import_dir in d.get('import'):
                    sort.launch(import_dir)
            except Exception as e:
                logger.error(f"Failed to process section {i}: {e}")
                logger.debug(f"Section details: {d}")
                # Continue with next section instead of crashing
                continue
        
        logger.info("Importrr application completed successfully")
        
    except Exception as e:
        logger.error(f"Fatal error in importrr application: {e}")
        logger.debug("Full traceback:", exc_info=True)
        raise  # Re-raise for scheduler to handle

class ImportrrScheduler:
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.setup_signal_handlers()
        
        # Get schedule from environment variables or use defaults
        self.schedule_hour = os.getenv('SCHEDULE_HOUR', '6-22/2')  # Every 2 hours from 6am to 10pm
        self.schedule_minute = os.getenv('SCHEDULE_MINUTE', '0')   # At the top of the hour
        self.timezone = os.getenv('TIMEZONE', 'UTC')
        
        logger.info(f"Scheduler initialized with schedule: {self.schedule_minute} {self.schedule_hour} * * *")
        logger.info(f"Timezone: {self.timezone}")
    
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
        job_start = datetime.now()
        logger.info("=" * 60)
        logger.info(f"Starting scheduled import job at {job_start}")
        logger.info("=" * 60)
        
        try:
            # Run the main import process
            main_process()
            
            job_end = datetime.now()
            duration = job_end - job_start
            logger.info("=" * 60)
            logger.info(f"Import job completed successfully at {job_end}")
            logger.info(f"Total duration: {duration}")
            logger.info("=" * 60)
            
        except Exception as e:
            job_end = datetime.now()
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
            # Add the job with cron trigger
            self.scheduler.add_job(
                func=self.run_import_job,
                trigger=CronTrigger(
                    minute=self.schedule_minute,
                    hour=self.schedule_hour,
                    timezone=self.timezone
                ),
                id='import_job',
                name='Import Media Files',
                misfire_grace_time=300,  # 5 minutes grace period
                coalesce=True,  # If multiple jobs are queued, run only the latest
                max_instances=1  # Only one instance at a time
            )
            
            logger.info("Scheduler started successfully")
            logger.info("Next scheduled runs:")
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                logger.info(f"  - {job.name}: {next_run}")
            
            # Start the scheduler (this blocks)
            self.scheduler.start()
            
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
        except Exception as e:
            logger.error(f"Scheduler failed to start: {e}")
            sys.exit(1)

def run_scheduler():
    """Run the scheduler service"""
    if not SCHEDULER_MODE:
        logger.error("APScheduler not available. Install with: pip install APScheduler")
        sys.exit(1)
        
    logger.info("Starting importrr scheduler service")
    
    # Check if we should run immediately on startup
    run_on_startup = os.getenv('RUN_ON_STARTUP', 'false').lower() == 'true'
    if run_on_startup:
        logger.info("RUN_ON_STARTUP=true, running import job immediately...")
        scheduler = ImportrrScheduler()
        scheduler.run_import_job()
    
    # Start the scheduler
    scheduler = ImportrrScheduler()
    scheduler.start()

if __name__ == '__main__':
    # Check what mode we're running in
    if SCHEDULER_MODE:
        # Running as scheduler service
        run_scheduler()
    else:
        # Running as one-time execution (traditional behavior)
        try:
            main_process()
        except Exception:
            exit(1)

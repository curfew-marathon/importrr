import logging
import signal
import sys
import os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from importrr.config import Config
from importrr.sort import Sort

logging.basicConfig(level=logging.INFO,
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
            # Add the job - every 2 hours from 8 AM to 10 PM
            self.scheduler.add_job(
                func=self.run_import_job,
                trigger=CronTrigger(minute=0, hour='8-22/2'),
                id='import_job',
                name='Import Media Files',
                misfire_grace_time=300,  # 5 minutes grace period
                coalesce=True,  # If multiple jobs are queued, run only the latest
                max_instances=1  # Only one instance at a time
            )
            
            logger.info("Importrr scheduler started (every 2 hours from 8 AM to 10 PM)")
            
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

if __name__ == '__main__':
    logger.info("Starting importrr scheduler service")
    scheduler = ImportrrScheduler()
    scheduler.start()

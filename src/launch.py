import logging

from importrr.config import Config
from importrr.sort import Sort

logging.basicConfig(level=logging.INFO,  # Change to INFO by default, DEBUG is too verbose
                    format='%(asctime)s %(levelname)-8s %(message)s',
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

if __name__ == '__main__':
    try:
        main_process()
    except Exception:
        exit(1)

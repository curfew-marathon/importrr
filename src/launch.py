import logging

from importrr.config import Config
from importrr.sort import Sort

logging.basicConfig(level=logging.INFO,  # Change to INFO by default, DEBUG is too verbose
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting importrr application")
    config = Config()
    
    total_sections = len(config.get_data())
    logger.info(f"Processing {total_sections} configuration sections")
    
    for i, d in enumerate(config.get_data(), 1):
        logger.info(f"Processing section {i}/{total_sections}: {d.get('album')}")
        sort = Sort(d.get('album'), d.get('archive'))
        for import_dir in d.get('import'):
            sort.launch(import_dir)
    
    logger.info("Importrr application completed successfully")

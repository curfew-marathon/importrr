import logging
import os.path
from configparser import ConfigParser

CANDIDATES = ['config.ini', '/config/config.ini']

logger = logging.getLogger(__name__)

class Config:

    def __init__(self):
        parser = ConfigParser()
        
        # Try to find and read config file
        config_found = False
        for candidate in CANDIDATES:
            if os.path.exists(candidate):
                logger.info(f"Loading configuration from: {candidate}")
                parser.read(candidate)
                config_found = True
                break
        
        if not config_found:
            logger.warning(f"No configuration file found in: {CANDIDATES}")
            raise FileNotFoundError(f"Configuration file not found in: {CANDIDATES}")

        if 'global' not in parser.sections():
            raise ValueError("Missing required 'global' section in configuration")

        self.album_root = parser['global']['album_dir']
        self.archive_root = parser['global']['archive_dir']
        logger.info(f"Album root directory: {self.album_root}")
        logger.info(f"Archive root directory: {self.archive_root}")
        
        self.data = []

        for section_name in parser.sections():
            if 'global' == section_name:
                continue

            logger.debug(f"Processing configuration section: {section_name}")
            album_dir = os.path.join(self.album_root, section_name)
            import_value = parser[section_name]['import_dir'].split(',')
            serial = parser[section_name].get('serial', None)  # Use get() to avoid KeyError
            archive_dir = os.path.join(self.archive_root, section_name)

            d = {'album': album_dir, 'archive': archive_dir, 'import': import_value, 'serial': serial}
            self.data.append(d)
            logger.debug(f"Added section: {section_name} with {len(import_value)} import directories")

        logger.info(f"Configuration loaded successfully with {len(self.data)} sections")

    def get_album(self):
        return self.album_root

    def get_archive(self):
        return self.archive_root

    def get_data(self):
        return self.data

    def get_serial(self, d):
        for dict in self.data:
            if d == dict.get('archive'):
                return dict.get('serial')
        raise KeyError("No serial for " + d)

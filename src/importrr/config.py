import os.path
from configparser import ConfigParser

CANDIDATES = ['config.ini', '/config/config.ini']


class Config:

    def __init__(self):
        parser = ConfigParser()
        parser.read(CANDIDATES)

        self.album_root = parser['global']['album_dir']
        self.archive_root = parser['global']['archive_dir']
        self.data = []

        for section_name in parser.sections():
            if 'global' == section_name:
                continue

            album_dir = os.path.join(self.album_root, section_name)
            import_value = parser[section_name]['import_dir'].split(',')
            serial = parser[section_name]['serial']
            archive_dir = os.path.join(self.archive_root, section_name)

            d = {'album': album_dir, 'archive': archive_dir, 'import': import_value, 'serial': serial}
            self.data.append(d)

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

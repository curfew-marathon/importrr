import logging

from importrr.config import Config
from importrr.sort import Sort

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    config = Config()
    for d in config.get_data():
        sort = Sort(d.get('album'), d.get('archive'))
        for import_dir in d.get('import'):
            sort.launch(import_dir)

import logging
import sys

from importrr import sort

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    if 3 == len(sys.argv):
        sort.launch(sys.argv[1], sys.argv[2])
    elif 4 == len(sys.argv):
        sort.launch(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: " + sys.argv[0] + " root_dir import_dir [archive dir]")
        sys.exit(1)

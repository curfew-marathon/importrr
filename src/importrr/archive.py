import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def copy(root_dir, sorted_files, archive_dir):
    if not sorted_files:
        return

    logger.info("Copying a version of the files to the archive dir")
    lock_file = os.path.join(archive_dir, "write.lock")
    try:
        if os.path.isfile(lock_file):
            logger.warning("Lock file already exists")
        else:
            Path(lock_file).touch()

        for f in sorted_files:
            to_file = os.path.join(archive_dir, f)
            Path(os.path.dirname(to_file)).mkdir(parents=True, exist_ok=True)
            shutil.copy2(os.path.join(root_dir, f), to_file)

    finally:
        os.remove(lock_file)

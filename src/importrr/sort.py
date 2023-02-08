import logging
import os
import time
from datetime import datetime

from importrr import archive, exifhelper

logger = logging.getLogger(__name__)

# in minutes
TIME_CUTOFF = 3


def cleanup(work_dir):
    logger.info("Removing directory " + work_dir)
    os.rmdir(work_dir)


def sort_media(root_dir, import_dir):
    exifhelper.backfill_videos(import_dir, root_dir)
    splits = exifhelper.organize(import_dir, root_dir)

    result = []
    for split in splits:
        index = split.find(' --> ')
        if -1 != index:
            s = split[index + 6:-1]
            result.append(s)
            logger.debug("Media moved to " + s)
    return result


def get_media_files(import_dir, time_cutoff):
    result = []
    entries = os.listdir(import_dir)
    for d in entries:
        f = os.path.join(import_dir, d)
        if os.path.isfile(f):
            last_time = last_accessed(f)
            if last_time <= time_cutoff:
                result.append(d)
            else:
                logger.info("Skipping file " + d)
        elif os.path.isdir(f):
            logger.info("Found directory " + d)
        else:
            logger.warning("Cannot resolve " + d)
    return result


def make_work_dir(cur_dir, work_dir, file_list):
    if not file_list:
        return
    os.mkdir(work_dir)
    for f in file_list:
        f_from = os.path.join(cur_dir, f)
        f_to = os.path.join(work_dir, f)
        logger.debug("Rename " + f_from + " to " + f_to)
        os.rename(f_from, f_to)


def last_accessed(file):
    created = os.stat(file).st_ctime
    modified = os.stat(file).st_mtime
    accessed = os.stat(file).st_atime
    return max(created, modified, accessed)


class Sort:

    def __init__(self, root_dir, archive_dir=None):
        if not os.path.isdir(root_dir):
            raise Exception("Directory doesn't exist " + root_dir)
        if archive_dir is not None and not os.path.isdir(archive_dir):
            raise Exception("Directory doesn't exist " + archive_dir)
        self.root_dir = root_dir
        self.archive_dir = archive_dir

    def launch(self, import_dir):
        start = time.time()
        time_cutoff = start - 60 * TIME_CUTOFF
        prefix = datetime.fromtimestamp(time_cutoff).strftime('%Y%m%d%H%M%S')

        import_dir = os.path.join(self.root_dir, import_dir)
        result = get_media_files(import_dir, time_cutoff)
        if result:
            work_dir = os.path.join(import_dir, prefix)
            make_work_dir(import_dir, work_dir, result)
            sorted_media = sort_media(self.root_dir, os.path.join('', 'import', prefix))
            if os.listdir(work_dir):
                logger.warning("Was not able to clear all files")
            else:
                logger.info("Cleared all files")
                cleanup(work_dir)

            if self.archive_dir is not None:
                archive.copy(self.root_dir, sorted_media, self.archive_dir, prefix)

        logger.info("Processed " + str(len(result)) + " files in " + str(time.time() - start) + "ms")

import logging
import os
import time
from datetime import datetime

from importrr import archive, exifhelper

logger = logging.getLogger(__name__)

# in minutes
TIME_CUTOFF = 2


def cleanup(work_dir):
    try:
        logger.debug(f"Removing temporary directory: {work_dir}")
        os.rmdir(work_dir)
        logger.debug(f"Successfully removed directory: {work_dir}")
    except OSError as e:
        logger.error(f"Failed to remove directory {work_dir}: {e}")


def sort_media(root_dir, import_dir):
    exifhelper.adjust_extensions(import_dir, root_dir)
    exifhelper.adjust_screenshots(import_dir, root_dir)
    exifhelper.backfill_videos(import_dir, root_dir)
    splits = exifhelper.organize(import_dir, root_dir)

    result = []
    for split in splits:
        if not split or not split.strip():  # Skip empty lines
            continue
            
        index = split.find(' --> ')
        if index != -1:  # More pythonic comparison
            try:
                s = split[index + 6:-1]
                if s and s.strip():  # Only add non-empty results
                    result.append(s.strip())
            except IndexError:
                logger.warning(f"Failed to parse ExifTool output line: {split}")
                continue
                
    logger.info(f"Organized {len(result)} files to {root_dir}")
    return result


def get_media_files(import_dir, time_cutoff):
    if not os.path.exists(import_dir):
        logger.warning(f"Import directory does not exist: {import_dir}")
        return []
        
    if not os.path.isdir(import_dir):
        logger.error(f"Import path is not a directory: {import_dir}")
        return []
    
    try:
        entries = os.listdir(import_dir)
    except PermissionError as e:
        logger.error(f"Permission denied accessing directory {import_dir}: {e}")
        return []
    except OSError as e:
        logger.error(f"Error accessing directory {import_dir}: {e}")
        return []
        
    result = []
    logger.debug(f"Scanning {len(entries)} entries in {import_dir}")
    
    for d in entries:
        f = os.path.join(import_dir, d)
        try:
            if os.path.isfile(f):
                last_time = last_accessed(f)
                if last_time <= time_cutoff:
                    result.append(d)
                    logger.debug(f"Added file for processing: {d}")
                else:
                    logger.debug(f"Skipping recently accessed file: {d}")
            elif os.path.isdir(f):
                logger.debug(f"Skipping directory: {d}")
            else:
                logger.warning(f"Cannot resolve file type for: {d}")
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot access {d}: {e}")
            continue
    
    logger.info(f"Found {len(result)} files ready for processing in {import_dir}")
    return result


def make_work_dir(cur_dir, work_dir, file_list):
    if not file_list:
        logger.debug("No files to move, skipping work directory creation")
        return
    try:
        logger.debug(f"Creating work directory: {work_dir}")
        
        # Handle case where directory already exists
        if os.path.exists(work_dir):
            if os.path.isdir(work_dir):
                logger.warning(f"Work directory already exists, using existing: {work_dir}")
            else:
                raise OSError(f"Work directory path exists but is not a directory: {work_dir}")
        else:
            os.mkdir(work_dir)
        
        for f in file_list:
            f_from = os.path.join(cur_dir, f)
            f_to = os.path.join(work_dir, f)
            
            # Check if target file already exists
            if os.path.exists(f_to):
                logger.warning(f"Target file already exists, skipping: {f}")
                continue
                
            os.rename(f_from, f_to)
            logger.debug(f"Moved file: {f}")
            
        logger.info(f"Moved {len(file_list)} files to temporary processing directory")
    except OSError as e:
        logger.error(f"Failed to create work directory or move files: {e}")
        raise


def last_accessed(file):
    created = os.stat(file).st_ctime
    modified = os.stat(file).st_mtime
    accessed = os.stat(file).st_atime
    return max(created, modified, accessed)


class Sort:

    def __init__(self, root_dir, archive_dir=None):
        if not os.path.isdir(root_dir):
            raise IOError("Directory doesn't exist " + root_dir)
        if archive_dir is not None and not os.path.isdir(archive_dir):
            raise IOError("Directory doesn't exist " + archive_dir)
        self.root_dir = root_dir
        self.archive_dir = archive_dir

    def launch(self, import_dir):
        logger.info(f"Starting processing for import directory: {import_dir}")
        start = time.time()
        time_cutoff = start - 60 * TIME_CUTOFF
        prefix = datetime.fromtimestamp(time_cutoff).strftime('%Y%m%d%H%M%S')

        import_dir = os.path.join(self.root_dir, import_dir)
        result = get_media_files(import_dir, time_cutoff)
        
        if result:
            logger.info(f"Processing {len(result)} files")
            work_dir = os.path.join(import_dir, prefix)
            make_work_dir(import_dir, work_dir, result)
            sorted_media = sort_media(self.root_dir, work_dir)  # Use work_dir directly
            
            remaining_files = os.listdir(work_dir) if os.path.exists(work_dir) else []
            if remaining_files:
                logger.warning(f"Unable to process {len(remaining_files)} files - they remain in {work_dir}")
                logger.debug(f"Remaining files: {remaining_files}")
            else:
                logger.info("Successfully processed all files")
                cleanup(work_dir)

            if self.archive_dir is not None:
                logger.info(f"Creating archive with {len(sorted_media)} files")
                archive.copy(self.root_dir, sorted_media, self.archive_dir, prefix)
        else:
            logger.info("No files found for processing")

        elapsed = time.time() - start
        logger.info(f"Completed processing {len(result)} files in {elapsed:.2f}s")

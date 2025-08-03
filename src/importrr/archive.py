import logging
import os
import tarfile

from importrr import transcode

logger = logging.getLogger(__name__)

# Max Tar size in GB
MAX_SIZE = 1000000000


def copy(root_dir, sorted_files, archive_dir, prefix):
    if not sorted_files:
        logger.debug("No files to archive")
        return

    logger.info(f"Starting archive creation for {len(sorted_files)} files")
    index = 0
    size = 0
    files = []

    for f in sorted_files:
        if f.endswith(".mov"):
            logger.debug(f"Converting MOV file: {f}")
            f = transcode.convert(root_dir, f)
            if f is None:
                logger.warning("Skipping file due to MOV conversion failure")
                continue  # Skip this file if conversion failed
        
        file = os.path.join(root_dir, f)
        try:
            file_size = os.stat(file).st_size
            logger.debug(f"Adding file to archive: {f} ({file_size} bytes)")
        except OSError as e:
            logger.error(f"Cannot access file {f}: {e}")
            continue
            
        if not files:  # Check if list is empty instead of None
            files.append(f)
            size = file_size
            continue
        elif size + file_size > MAX_SIZE:
            logger.info(f"Archive size limit reached, creating archive {index}")
            create_tar(root_dir, files, archive_dir, prefix, index)

            # reset all the things
            index += 1
            size = 0
            files.clear()

        files.append(f)
        size += file_size

    # Clear the last tar
    if files:
        logger.info(f"Creating final archive {index}")
        create_tar(root_dir, files, archive_dir, prefix, index)
    
    logger.info(f"Archive creation completed - created {index + 1} archive(s)")


def create_tar(root_dir, sorted_files, archive_dir, prefix, index):
    tar_file = os.path.join(archive_dir, prefix + "-" + str(index) + ".tar")
    logger.info(f"Creating archive: {tar_file} with {len(sorted_files)} files")
    
    try:
        with tarfile.open(tar_file, "w") as tar:
            for f in sorted_files:
                file_path = os.path.join(root_dir, f)
                if os.path.exists(file_path):
                    tar.add(file_path, arcname=f, recursive=False)
                    logger.debug(f"Added to archive: {f}")
                else:
                    logger.warning(f"File not found for archiving: {f}")
        
        archive_size = os.path.getsize(tar_file)
        logger.info(f"Archive created successfully: {tar_file} ({archive_size} bytes)")
        
    except Exception as e:
        logger.error(f"Failed to create archive {tar_file}: {e}")
        raise

import logging
import os
import tarfile

from importrr import transcode

logger = logging.getLogger(__name__)

# Max Tar size in GB
MAX_SIZE = 1000000000


def copy(root_dir, sorted_files, archive_dir, prefix):
    """Transcode MOVs and roll every sorted file into .tar archives.

    Returns True only if every entry was archived; False if any file was
    skipped (failed MOV conversion or unreadable file), so the caller can
    keep the batch's work_dir and manifest for recovery.
    """
    if not sorted_files:
        logger.debug("No files to archive")
        return True

    logger.info(f"Starting archive creation for {len(sorted_files)} files")
    index = 0
    size = 0
    files = []
    failed = []

    for f in sorted_files:
        if f.endswith(".mov"):
            logger.debug(f"Converting MOV file: {f}")
            converted = transcode.convert(root_dir, f)
            if converted is None:
                logger.warning(f"Skipping file due to MOV conversion failure: {f}")
                failed.append(f)
                continue  # Skip this file if conversion failed
            f = converted

        file = os.path.join(root_dir, f)
        try:
            file_size = os.stat(file).st_size
            logger.debug(f"Adding file to archive: {f} ({file_size} bytes)")
        except OSError as e:
            logger.error(f"Cannot access file {f}: {e}")
            failed.append(f)
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
        total_archives = index + 1
    else:
        total_archives = index  # No final archive was created

    logger.info(f"Archive creation completed - created {total_archives} archive(s)")

    if failed:
        logger.warning(
            f"Archive incomplete: {len(failed)} file(s) not archived: {failed}"
        )
    return not failed


def create_tar(root_dir, sorted_files, archive_dir, prefix, index):
    """Write the given files into a single .tar at archive_dir/<prefix>-<index>.tar."""
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

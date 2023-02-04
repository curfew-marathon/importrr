import logging
import os
import tarfile

logger = logging.getLogger(__name__)


def copy(root_dir, sorted_files, archive_dir, prefix):
    if not sorted_files:
        return

    create_tar(root_dir, sorted_files, archive_dir, prefix)


def create_tar(root_dir, sorted_files, archive_dir, prefix):
    tar_file = os.path.join(archive_dir, prefix + ".tar")
    logger.info("Creating tar ", tar_file)
    with tarfile.open(tar_file, "w") as tar:
        for f in sorted_files:
            tar.add(os.path.join(root_dir, f), arcname=f, recursive=False)

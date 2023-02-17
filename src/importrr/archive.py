import logging
import os
import tarfile

from importrr import transcode

logger = logging.getLogger(__name__)

# Max Tar size in GB
MAX_SIZE = 2 * 1000000000


def copy(root_dir, sorted_files, archive_dir, prefix):
    if not sorted_files:
        return

    index = 0
    size = 0
    files = []

    for f in sorted_files:
        if f.endswith(".mov"):
            f = transcode.convert(root_dir, f)
        file = os.path.join(root_dir, f)
        file_size = os.stat(file).st_size
        if files is None:
            files.append(f)
            size = file_size
            continue
        elif size + file_size > MAX_SIZE:
            create_tar(root_dir, files, archive_dir, prefix, index)

            # reset all the things
            index += 1
            size = 0
            files.clear()

        files.append(f)
        size += file_size

    # Clear the last tar
    if files:
        create_tar(root_dir, files, archive_dir, prefix, index)


def create_tar(root_dir, sorted_files, archive_dir, prefix, index):
    tar_file = os.path.join(archive_dir, prefix + "-" + str(index) + ".tar")
    logger.info("Creating tar " + tar_file)
    with tarfile.open(tar_file, "w") as tar:
        for f in sorted_files:
            tar.add(os.path.join(root_dir, f), arcname=f, recursive=False)

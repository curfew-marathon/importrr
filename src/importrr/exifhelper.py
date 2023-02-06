import logging
import os

from exiftool import ExifToolHelper

logger = logging.getLogger(__name__)


def organize(import_dir, root_dir):
    os.chdir(root_dir)

    logger.info("Renaming and sorting the files")
    with ExifToolHelper(common_args=[]) as et:
        # verbose because we need to get the new names of the files
        output = et.execute('-verbose',
                            '-filename<${DateTimeOriginal#;DateFmt("%Y/%m")}/$DateTimeOriginal%-c.%e',
                            '-d',
                            '%Y%m%d-%H%M%S',
                            import_dir)

        # split string
        splits = output.split('\n')
        return splits


def backfill_videos(import_dir, root_dir):
    os.chdir(root_dir)

    logger.info("Updating the movie files")
    with ExifToolHelper(common_args=[]) as et:
        # output is thrown away so we don't need verbose
        output = et.execute('-overwrite_original',
                            '-datetimeoriginal<CreateDate',
                            '-if',
                            'not $datetimeoriginal',
                            '-ext',
                            '3GP',
                            '-ext',
                            'MOV',
                            '-ext',
                            'MP4',
                            import_dir)

import logging
import os

from exiftool import ExifToolHelper

logger = logging.getLogger(__name__)


def organize_media(import_dir, root_dir):
    with ExifToolHelper(common_args=[]) as et:
        backfill_videos(et, import_dir, root_dir)
        adjust_screenshots(et, import_dir, root_dir)
        return organize_media(et, import_dir, root_dir)


def organize_media(et, import_dir, root_dir):
    os.chdir(root_dir)

    logger.info("Renaming and sorting the files")
    # verbose because we need to get the new names of the files
    output = et.execute('-verbose',
                        '-filename<${DateTimeOriginal#;DateFmt("%Y/%m")}/$DateTimeOriginal%-c.%e',
                        '-d',
                        '%Y%m%d-%H%M%S',
                        import_dir)

    # split string
    splits = output.split('\n')
    return splits


def adjust_screenshots(et, import_dir, root_dir):
    os.chdir(root_dir)

    logger.info("Adjust the screenshot files")
    # output is thrown away so we don't need verbose
    # adjust the names of the PNG files which are really JPG
    et.execute('-filename<%f.$fileTypeExtension',
               '-ext',
               'PNG',
               import_dir)

    # if there is any date in the metadata then add it in
    et.execute('-overwrite_original',
               '-datetimeoriginal<CreateDate',
               '-if',
               'not $datetimeoriginal',
               '-ext',
               'JPG',
               '-ext',
               'PNG',
               import_dir)

    # for everything that's left just use the file modify date
    et.execute('-overwrite_original',
               '-datetimeoriginal<FileModifyDate',
               '-if',
               'not $datetimeoriginal',
               '-ext',
               'JPG',
               '-ext',
               'PNG',
               import_dir)


def backfill_videos(et, import_dir, root_dir):
    os.chdir(root_dir)

    logger.info("Updating the movie files")
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

import logging
import os

from exiftool import ExifToolHelper
from exiftool.exceptions import ExifToolExecuteError

logger = logging.getLogger(__name__)


def organize(import_dir, root_dir):
    logger.info("Renaming and sorting the files")
    # verbose because we need to get the new names of the files
    params = ['-verbose',
              '-filename<${DateTimeOriginal#;DateFmt("%Y/%m")}/$DateTimeOriginal%-c.%e',
              '-d',
              '%Y%m%d-%H%M%S',
              import_dir]

    output = run_exiftool(root_dir, params, False)
    # split string
    splits = output.split('\n')
    return splits


def adjust_extensions(import_dir, root_dir):
    logger.info("Adjust the file extensions")
    # adjust the names of the files based on their MIME type so Exiftool doesn't error out
    params = ['-filename<%f.$fileTypeExtension',
              '-ext',
              'GIF',
              '-ext',
              'JPG',
              '-ext',
              'PNG',
              '-ext',
              '3GP',
              '-ext',
              'MOV',
              '-ext',
              'MP4',
              import_dir]
    run_exiftool(root_dir, params)


def adjust_screenshots(import_dir, root_dir):
    logger.info("Adjust the screenshots")
    # if there is any date in the metadata then add it in
    params = ['-overwrite_original',
              '-EXIF:DateTimeOriginal<PNG:CreateDate',
              '-XMP:DateCreated<PNG:CreateDate',
              '-if',
              'not $datetimeoriginal',
              '-ext',
              'GIF',
              '-ext',
              'JPG',
              '-ext',
              'PNG',
              import_dir]
    run_exiftool(root_dir, params)

    params = ['-overwrite_original',
              '-EXIF:DateTimeOriginal<XMP:DateCreated',
              '-if',
              'not $datetimeoriginal',
              '-ext',
              'GIF',
              '-ext',
              'JPG',
              '-ext',
              'PNG',
              import_dir]
    run_exiftool(root_dir, params)

    # for everything that's left just use the file modify date
    params = ['-overwrite_original',
              '-EXIF:DateTimeOriginal<FileModifyDate',
              '-XMP:DateCreated<FileModifyDate',
              '-if',
              'not $datetimeoriginal',
              '-ext',
              'GIF',
              '-ext',
              'JPG',
              '-ext',
              'PNG',
              import_dir]
    run_exiftool(root_dir, params)


def copy_tags(root_dir, input_file, output_file):
    logger.info("Copying the tags over " + input_file + " -> " + output_file)
    params = ['-overwrite_original',
              '-TagsFromFile',
              input_file,
              '-all:all>all:all',
              output_file]

    run_exiftool(root_dir, params)


def backfill_videos(import_dir, root_dir):
    backfill_video_tag(import_dir, root_dir, 'CreationDate')
    backfill_video_tag(import_dir, root_dir, 'CreateDate')


def backfill_video_tag(import_dir, root_dir, tag):
    logger.info("Updating the movie files by " + tag)
    params = ['-overwrite_original',
              '-datetimeoriginal<' + tag,
              '-time:all<$' + tag,
              '-if',
              'not $datetimeoriginal',
              '-ext',
              '3GP',
              '-ext',
              'MOV',
              '-ext',
              'MP4',
              import_dir]
    run_exiftool(root_dir, params)


def run_exiftool(root_dir, params, on_error=True):
    os.chdir(root_dir)

    try:
        with ExifToolHelper(common_args=[]) as et:
            return et.execute(*params)
    except ExifToolExecuteError as e:
        # exiftool will return error code 2 when all files fail the condition
        if e.stdout is not None:
            logger.warning("stdout")
            logger.warning(e.stdout)
        if e.stderr is not None:
            logger.warning("stderr")
            logger.warning(e.stderr)
        if 1 == e.returncode:
            if on_error and " 0 image files read" not in e.stdout or not on_error:
                raise e

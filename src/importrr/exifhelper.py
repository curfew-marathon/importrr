import logging
import os

from exiftool import ExifToolHelper
from exiftool.exceptions import ExifToolExecuteError

logger = logging.getLogger(__name__)


def organize(import_dir, root_dir):
    logger.info("Organizing files by date and renaming")
    logger.debug(f"Processing files in: {import_dir}")
    # verbose because we need to get the new names of the files
    params = [
        "-verbose",
        '-filename<${DateTimeOriginal#;DateFmt("%Y/%m")}/$DateTimeOriginal%-c.%e',
        "-d",
        "%Y%m%d-%H%M%S",
        import_dir,
    ]

    output = run_exiftool(root_dir, params, False)
    # split string
    splits = output.split("\n")
    logger.debug(f"ExifTool returned {len(splits)} output lines")
    return splits


def adjust_extensions(import_dir, root_dir):
    logger.info("Adjusting file extensions based on MIME types")
    logger.debug(f"Processing files in: {import_dir}")
    # adjust the names of the files based on their MIME type so Exiftool doesn't error out
    params = [
        "-filename<%f.$fileTypeExtension",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "PNG",
        "-ext",
        "3GP",
        "-ext",
        "MOV",
        "-ext",
        "MP4",
        import_dir,
    ]
    run_exiftool(root_dir, params)


def adjust_screenshots(import_dir, root_dir):
    logger.info("Backfilling EXIF dates for screenshots and images")
    logger.debug(f"Processing files in: {import_dir}")

    common_params = [
        "-if",
        "not $datetimeoriginal",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "PNG",
        import_dir,
    ]

    # if there is any date in the metadata then add it in
    # Three sequential calls enforce priority: PNG:CreateDate > XMP:DateCreated > FileModifyDate.
    # Each call re-checks "not $datetimeoriginal" so later calls only run if earlier ones found nothing.
    params = [
        "-overwrite_original",
        "-EXIF:DateTimeOriginal<PNG:CreateDate",
        "-XMP:DateCreated<PNG:CreateDate",
    ] + common_params
    run_exiftool(root_dir, params)

    params = [
        "-overwrite_original",
        "-EXIF:DateTimeOriginal<XMP:DateCreated",
    ] + common_params
    run_exiftool(root_dir, params)

    # for everything that's left just use the file modify date
    params = [
        "-overwrite_original",
        "-EXIF:DateTimeOriginal<FileModifyDate",
        "-XMP:DateCreated<FileModifyDate",
    ] + common_params
    run_exiftool(root_dir, params)


def copy_tags(root_dir, input_file, output_file):
    logger.debug(f"Copying EXIF tags: {input_file} -> {output_file}")
    params = [
        "-overwrite_original",
        "-TagsFromFile",
        input_file,
        "-all:all>all:all",
        output_file,
    ]

    run_exiftool(root_dir, params)


def backfill_videos(import_dir, root_dir):
    logger.info("Backfilling video metadata dates")
    backfill_video_tag(import_dir, root_dir, "CreationDate")
    backfill_video_tag(import_dir, root_dir, "CreateDate")


def backfill_video_tag(import_dir, root_dir, tag):
    logger.debug(f"Backfilling video dates using {tag} metadata")
    params = [
        "-overwrite_original",
        "-datetimeoriginal<" + tag,
        "-time:all<$" + tag,
        "-if",
        "not $datetimeoriginal",
        "-ext",
        "3GP",
        "-ext",
        "MOV",
        "-ext",
        "MP4",
        import_dir,
    ]
    run_exiftool(root_dir, params)


def classify_unprocessed(root_dir, work_dir, names):
    """Explain why each still-present file was not organized.

    ``names`` is the raw ``os.listdir(work_dir)`` after the sort phase - the
    files ExifTool never moved into the album tree. Returns
    ``[{"name": str, "reason": str}]``, one entry per media file (the manifest
    itself is skipped). Best effort: any ExifTool failure degrades to a generic
    reason rather than raising, so the diagnostic never breaks the pipeline.
    """
    media = [n for n in names if not n.startswith("manifest.yml")]
    if not media:
        return []

    os.chdir(root_dir)
    meta_by_name = {}
    try:
        with ExifToolHelper(common_args=[], check_execute=False) as et:
            for meta in et.get_tags(
                [os.path.join(work_dir, n) for n in media],
                tags=["DateTimeOriginal", "FileType", "Error"],
            ):
                meta_by_name[os.path.basename(meta.get("SourceFile", ""))] = meta
    except ExifToolExecuteError as e:
        logger.warning(f"Could not probe unprocessed files with ExifTool: {e}")

    skipped = []
    for name in media:
        meta = meta_by_name.get(name, {})
        error = meta.get("Error")
        if error:
            reason = f"unreadable or unsupported: {error}"
        elif not meta:
            reason = "unreadable or unsupported: ExifTool returned no metadata"
        elif not meta.get("DateTimeOriginal"):
            reason = (
                f"no capture date in metadata (type={meta.get('FileType') or 'unknown'})"
            )
        else:
            reason = "not renamed by ExifTool (unexpected)"
        skipped.append({"name": name, "reason": reason})
        logger.warning(f"Skipped (not imported): {name} - {reason}")

    return skipped


def run_exiftool(root_dir, params, on_error=True):
    logger.debug(
        f"Running ExifTool with params: {' '.join(params[:3])}..."
    )  # Show first few params
    os.chdir(root_dir)

    try:
        with ExifToolHelper(common_args=[]) as et:
            result = et.execute(*params)
            logger.debug("ExifTool execution completed successfully")
            return result
    except ExifToolExecuteError as e:
        # exiftool will return error code 2 when all files fail the condition
        if e.stdout is not None:
            logger.error("ExifTool stdout:")
            logger.error(e.stdout)
        if e.stderr is not None:
            logger.error("ExifTool stderr:")
            logger.error(e.stderr)
        if 1 == e.returncode:
            if (on_error and " 0 image files read" not in e.stdout) or not on_error:
                logger.error(f"ExifTool failed with return code {e.returncode}")
                raise
        else:
            logger.warning(
                f"ExifTool returned non-zero exit code {e.returncode} but continuing"
            )

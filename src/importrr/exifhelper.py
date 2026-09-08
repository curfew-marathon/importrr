import logging
import os

from exiftool import ExifToolHelper
from exiftool.exceptions import ExifToolExecuteError

from importrr import metrics

logger = logging.getLogger(__name__)

# Embedded capture-date sources tried before falling back to the file mtime,
# ordered *lowest* priority first: ExifTool keeps the last redirect that
# resolves, so the best source (EXIF:CreateDate) must come last. This mirrors
# the priority order of photo-stage's DATE_SOURCES (toolbox/photo-stage,
# photo_stage/exiftool.py) for the tags the two share, with the PNG-native
# tags slotted in alongside PNG:CreationTime. Keep the two in sync.
_EMBEDDED_DATE_SOURCES = (
    "EXIF:ModifyDate",
    "PNG:ModifyDate",
    "PNG:CreateDate",
    "PNG:CreationTime",
    "Composite:GPSDateTime",
    "IPTC:DateCreated",
    "XMP:CreateDate",
    "XMP:DateCreated",
    "EXIF:CreateDate",
)


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
    # adjust the names of the files based on their MIME type so Exiftool doesn't
    # error out. JPEG is listed as well as JPG: ExifTool's "-ext JPG" does not
    # match a ".jpeg" name, so without it those files skip every later pass;
    # "-filename<%f.$fileTypeExtension" then normalises them to ".jpg".
    # -P: a pure rename must never bump the file mtime (a later pass may use it).
    params = [
        "-P",
        "-filename<%f.$fileTypeExtension",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "JPEG",
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
    """Give GIF/JPG/PNG files a DateTimeOriginal when they arrive without one.

    Pass A copies the best available *embedded* date (see
    :data:`_EMBEDDED_DATE_SOURCES`). Whatever is still dateless afterwards is
    logged file by file and counted, then Pass B stamps it with the file mtime -
    a last resort that is frequently wrong (it is just when the file last hit a
    disk), hence the warning.
    """
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

    # Pass A: one call, every embedded source redirected at both DateTimeOriginal
    # and XMP:DateCreated. ExifTool keeps the last redirect that resolves, and
    # _EMBEDDED_DATE_SOURCES is ordered worst-first, so the best source wins.
    params = ["-overwrite_original", "-P"]
    for source in _EMBEDDED_DATE_SOURCES:
        params.append(f"-EXIF:DateTimeOriginal<{source}")
        params.append(f"-XMP:DateCreated<{source}")
    run_exiftool(root_dir, params + common_params)

    # Anything still without a date is about to be guessed from its mtime.
    # Best effort: a probe failure must not stop the batch from being sorted.
    try:
        guessed = _images_missing_capture_date(import_dir, root_dir)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not enumerate dateless files before mtime pass: {e}")
        guessed = []
    for name in guessed:
        logger.warning(
            f"No capture date in {name} - using file mtime (likely wrong)"
        )
        metrics.DATES_GUESSED_FROM_MTIME_TOTAL.inc()

    # Pass B: last resort - the file modify date.
    params = [
        "-overwrite_original",
        "-P",
        "-EXIF:DateTimeOriginal<FileModifyDate",
        "-XMP:DateCreated<FileModifyDate",
    ] + common_params
    run_exiftool(root_dir, params)


def _images_missing_capture_date(import_dir, root_dir):
    """Basenames of GIF/JPG/PNG files under ``import_dir`` that still have no
    ``DateTimeOriginal``.

    ExifTool does the filtering natively (``-if`` + ``-p``) and prints only the
    failing names, so this stays flat in memory no matter how large the batch.
    An empty batch, or one where every file already has a date, yields ``[]``.
    """
    params = [
        "-if",
        "not $datetimeoriginal",
        "-p",
        "$filename",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "PNG",
        import_dir,
    ]
    # on_error=False: ExifTool exits 2 ("all files failed the condition") when
    # every file already has a date - that is the happy path here, not an error.
    output = run_exiftool(root_dir, params, False)
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


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
    ``[{"name": str, "reason": str}]``, one entry per file. Best effort: any
    ExifTool failure degrades to a generic reason rather than raising, so the
    diagnostic never breaks the pipeline.

    The batch manifest is not written until after this runs, and ``make_work_dir``
    renames any staged file that collides with the manifest name, so every entry
    here is a genuine unorganized file.
    """
    media = list(names)
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
    except Exception as e:  # noqa: BLE001
        # Best effort: a missing exiftool, a stopped helper, or a parse error
        # must not break the pipeline. Every file falls back to a generic reason.
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
            reason = f"no capture date in metadata (type={meta.get('FileType') or 'unknown'})"
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

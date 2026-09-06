import logging
import os
import time
from datetime import datetime

import yaml

from importrr import archive, exifhelper, metrics

logger = logging.getLogger(__name__)

# in minutes
TIME_CUTOFF = 2

# Write-Ahead Log written into the work_dir before the slow transcode/archive
# phase so a crash leaves a durable record of the batch.
MANIFEST_NAME = "manifest.yml"


def cleanup(work_dir):
    """Delete work_dir only when it holds nothing but (optionally) the manifest.

    If any media files remain, leave the directory *and* the manifest untouched
    for manual inspection / recovery.
    """
    if not os.path.isdir(work_dir):
        logger.debug(f"Work directory already gone, nothing to clean up: {work_dir}")
        return

    try:
        entries = os.listdir(work_dir)
    except OSError as e:
        logger.error(f"Failed to list directory {work_dir}: {e}")
        return

    leftovers = [e for e in entries if e != MANIFEST_NAME]
    if leftovers:
        logger.warning(
            f"Work directory left intact for manual inspection/recovery "
            f"({len(leftovers)} unprocessed file(s)): {work_dir}"
        )
        logger.debug(f"Unprocessed entries: {leftovers}")
        return

    try:
        manifest_path = os.path.join(work_dir, MANIFEST_NAME)
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
            logger.debug(f"Removed manifest: {manifest_path}")
        os.rmdir(work_dir)
        logger.debug(f"Successfully removed directory: {work_dir}")
    except OSError as e:
        logger.error(f"Failed to remove directory {work_dir}: {e}")


def write_manifest(root_dir, work_dir, batch_id, entries):
    """Persist the batch (what is about to be transcoded and archived) as YAML.

    A failure to write the manifest is logged but does not stop the pipeline.
    """
    files = []
    for entry in entries:
        album_rel = entry["album_path"]
        album_abs = os.path.abspath(os.path.join(root_dir, album_rel))
        item = {
            "original_name": entry["original_name"],
            "album_path": album_abs,
        }
        if album_abs.lower().endswith(".mov"):
            item["transcoded_mp4_path"] = os.path.splitext(album_abs)[0] + ".mp4"
        files.append(item)

    doc = {"batch_id": batch_id, "files": files}
    manifest_path = os.path.join(work_dir, MANIFEST_NAME)
    tmp_path = f"{manifest_path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh, default_flow_style=False, sort_keys=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, manifest_path)
        logger.info(f"Wrote manifest with {len(files)} entries: {manifest_path}")
    except OSError as e:
        logger.warning(f"Failed to write manifest {manifest_path}: {e}")
        # Don't leave a partial temp file behind: cleanup() would read it as
        # leftover media and refuse to remove the work_dir.
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def sort_media(root_dir, import_dir):
    """Run the ExifTool sort phase and return one entry per organized file.

    Each entry is ``{"original_name": <name entering organize()>, "album_path":
    <root-relative path it was moved to>}``, parsed from ExifTool's verbose
    ``' --> '`` output.
    """
    exifhelper.adjust_extensions(import_dir, root_dir)
    exifhelper.adjust_screenshots(import_dir, root_dir)
    exifhelper.backfill_videos(import_dir, root_dir)
    splits = exifhelper.organize(import_dir, root_dir)

    result = []
    for split in splits:
        if not split or not split.strip():  # Skip empty lines
            continue

        index = split.find(" --> ")
        if index != -1:  # More pythonic comparison
            try:
                s = split[index + 6 : -1]
                if s and s.strip():  # Only add non-empty results
                    src = split[:index].strip().strip("'")
                    result.append(
                        {
                            "original_name": os.path.basename(src),
                            "album_path": s.strip(),
                        }
                    )
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
                logger.warning(
                    f"Work directory already exists, using existing: {work_dir}"
                )
            else:
                raise OSError(
                    f"Work directory path exists but is not a directory: {work_dir}"
                )
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
    def __init__(self, root_dir, archive_dir=None, section=None):
        if not os.path.isdir(root_dir):
            raise OSError("Directory doesn't exist " + root_dir)
        if archive_dir is not None and not os.path.isdir(archive_dir):
            raise OSError("Directory doesn't exist " + archive_dir)
        self.root_dir = root_dir
        self.archive_dir = archive_dir
        # Label value for per-section metrics. Falls back to the album folder
        # name for callers that construct Sort directly (e.g. tests).
        self.section = section or os.path.basename(os.path.normpath(root_dir))

    def launch(self, import_dir):
        """Sort a batch, write its manifest, archive it, then clean up.

        Order is strict: sort -> write manifest -> transcode + archive ->
        cleanup, and cleanup only runs after a fully successful archive.
        """
        logger.info(f"Starting processing for import directory: {import_dir}")
        start = time.time()
        time_cutoff = start - 60 * TIME_CUTOFF
        prefix = datetime.fromtimestamp(time_cutoff).strftime("%Y%m%d%H%M%S")  # noqa: DTZ006

        abs_root_dir = os.path.abspath(self.root_dir)
        abs_import_dir = os.path.abspath(os.path.join(abs_root_dir, import_dir))

        if os.path.commonpath([abs_root_dir, abs_import_dir]) != abs_root_dir:
            logger.error(f"Path traversal attempt detected: {import_dir}")
            return

        import_dir = abs_import_dir
        result = []
        # finally: record the batch duration even when a step below raises, so
        # slow archive/transcode failures still land in the histogram.
        try:
            result = get_media_files(import_dir, time_cutoff)
            metrics.FILES_DISCOVERED_TOTAL.labels(section=self.section).inc(len(result))

            if result:
                logger.info(f"Processing {len(result)} files")
                work_dir = os.path.join(import_dir, prefix)
                make_work_dir(import_dir, work_dir, result)
                entries = sort_media(self.root_dir, work_dir)  # Use work_dir directly
                sorted_media = [entry["album_path"] for entry in entries]
                metrics.FILES_ORGANIZED_TOTAL.labels(section=self.section).inc(
                    len(entries)
                )

                remaining_files = (
                    os.listdir(work_dir) if os.path.exists(work_dir) else []
                )
                metrics.WORKDIR_LEFTOVER_FILES.labels(section=self.section).set(
                    len(remaining_files)
                )
                if remaining_files:
                    logger.warning(
                        f"Unable to process {len(remaining_files)} files - they remain in {work_dir}"
                    )
                    logger.debug(f"Remaining files: {remaining_files}")
                else:
                    logger.info("Successfully processed all files")

                # Write-Ahead Log: record the batch before the slow, crash-prone
                # transcode + archive phase so it can be recovered after a hard kill.
                if os.path.isdir(work_dir):
                    write_manifest(self.root_dir, work_dir, prefix, entries)

                archive_complete = True
                if self.archive_dir is not None:
                    logger.info(f"Creating archive with {len(sorted_media)} files")
                    try:
                        archive_complete = archive.copy(
                            self.root_dir,
                            sorted_media,
                            self.archive_dir,
                            prefix,
                            self.section,
                        )
                    except Exception:
                        # A tar or file-I/O error leaves the batch unarchived
                        # just as a False return does; count it before it
                        # propagates so the metric does not silently miss it.
                        metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(
                            section=self.section
                        ).inc()
                        raise

                # Safe cleanup runs only after a fully successful archive. On a
                # partial failure the work_dir and its manifest are kept so the
                # batch can be recovered. cleanup() also independently refuses to
                # delete a work_dir that still holds media.
                if archive_complete:
                    cleanup(work_dir)
                else:
                    metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(section=self.section).inc()
                    logger.warning(
                        f"Archive incomplete - keeping {work_dir} and its manifest "
                        f"for recovery"
                    )
            else:
                metrics.WORKDIR_LEFTOVER_FILES.labels(section=self.section).set(0)
                logger.info("No files found for processing")
        finally:
            elapsed = time.time() - start
            metrics.BATCH_DURATION_SECONDS.observe(elapsed)
            logger.info(f"Completed processing {len(result)} files in {elapsed:.2f}s")

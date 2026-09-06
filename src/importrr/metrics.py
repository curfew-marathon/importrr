import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Wall-clock buckets shared by every timing histogram. importrr runs are slow:
# ffmpeg with `-preset slower` on a large MOV can take many minutes, a batch
# rolls dozens of files, and a full job walks every config section. The job has
# been OOM-killed in the past, so buckets deliberately extend past 1800s -
# otherwise a legitimately slow-but-successful run collapses into +Inf.
_SECONDS_BUCKETS = (
    1,
    5,
    15,
    30,
    60,
    120,
    300,
    600,
    1200,
    1800,
    3600,
    7200,
    float("inf"),
)

# --- job level -----------------------------------------------------------------

JOB_RUNS_TOTAL = Counter(
    "importrr_job_runs_total",
    "Scheduled import job runs, by outcome",
    ["outcome"],  # "success" (all sections ok) | "partial" (some failed) | "error"
)
JOB_DURATION_SECONDS = Histogram(
    "importrr_job_duration_seconds",
    "Wall-clock time for one full import job (all config sections)",
    buckets=_SECONDS_BUCKETS,
)
LAST_SUCCESS_TIMESTAMP = Gauge(
    "importrr_last_success_timestamp_seconds",
    "Unix time the last import job completed with every section successful",
)
SECTION_FAILURES_TOTAL = Counter(
    "importrr_section_failures_total",
    "Config sections that raised during a job run",
    ["section"],
)

# --- sort / batch phase -------------------------------------------------------

FILES_DISCOVERED_TOTAL = Counter(
    "importrr_files_discovered_total",
    "Media files found ready for processing",
    ["section"],
)
FILES_ORGANIZED_TOTAL = Counter(
    "importrr_files_organized_total",
    "Files successfully sorted and renamed into the album tree",
    ["section"],
)
WORKDIR_LEFTOVER_FILES = Gauge(
    "importrr_workdir_leftover_files",
    "Files left behind in a work_dir after the most recent batch (recovery needed)",
    ["section"],
)
BATCH_DURATION_SECONDS = Histogram(
    "importrr_batch_duration_seconds",
    "Wall-clock time to process one import_dir batch",
    buckets=_SECONDS_BUCKETS,
)

# --- archive phase -----------------------------------------------------------

ARCHIVES_CREATED_TOTAL = Counter(
    "importrr_archives_created_total", "Tar archives written", ["section"]
)
ARCHIVED_BYTES_TOTAL = Counter(
    "importrr_archived_bytes_total",
    "Total bytes written into tar archives",
    ["section"],
)
ARCHIVE_INCOMPLETE_TOTAL = Counter(
    "importrr_archive_incomplete_total",
    "Batches whose archive finished with missing or failed files",
    ["section"],
)

# --- transcode phase --------------------------------------------------------

TRANSCODE_TOTAL = Counter(
    "importrr_transcode_total",
    "MOV to MP4 conversions, by outcome",
    ["outcome"],  # "success" | "failure"
)
TRANSCODE_DURATION_SECONDS = Histogram(
    "importrr_transcode_duration_seconds",
    "Wall-clock time for one MOV to MP4 conversion",
    buckets=_SECONDS_BUCKETS,
)
TRANSCODE_INPUT_BYTES_TOTAL = Counter(
    "importrr_transcode_input_bytes_total", "Total input bytes fed to ffmpeg"
)
TRANSCODE_OUTPUT_BYTES_TOTAL = Counter(
    "importrr_transcode_output_bytes_total", "Total output bytes produced by ffmpeg"
)


def start(port):
    """Start the metrics HTTP server. Never raises: a bad port value, a
    collision, or any other startup failure is logged and swallowed so a
    metrics problem can never take the daemon down."""
    try:
        start_http_server(int(port))
        logger.info("Metrics server listening on :%s/metrics", port)
    except Exception as e:  # noqa: BLE001 - startup failures are explicitly non-fatal
        logger.error(
            "Could not start metrics server on port %r (%s) - continuing without metrics",
            port,
            e,
        )

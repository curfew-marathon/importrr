# importrr

importrr is a Python application designed to automate importing of image and movie files into a photo library. It wraps around Phil Harvey's [ExifTool](https://exiftool.org/) which does the heavy lifting behind the scenes. Following the DRY (don't repeat yourself) principle, the application follows the same steps to adjust and clean up the files before sorting and storing them in the photo library. Once running, the images only need to be copied into the import directories and they will be properly organized into the photo album.

## Features

- **Automatic photo/video import and organization** by date
- **MOV to MP4 conversion** using FFmpeg for better compatibility
- **EXIF metadata cleanup** and date standardization
- **Intelligent file naming** with collision handling
- **Archive creation** for backup purposes
- **Built-in scheduler** runs every 2 hours automatically
- **Prometheus metrics** endpoint for monitoring
- **Docker support** for easy deployment

# Configuration

Create a `config.ini` file in the root directory or in `/config/config.ini` with the following structure:

```ini
[global]
album_dir = /path/to/albums
archive_dir = /path/to/archives

[home]
import_dir = personal,photos

[work]
import_dir = corporate
```

## Configuration Parameters

- **album_dir**: Root directory for album storage (e.g., `/path/to/albums`)
- **archive_dir**: Root directory for archive storage (e.g., `/path/to/archives`)
- **import_dir**: Comma-separated list of subdirectories to monitor for importing

## How it works:

The `global` section defines the root directories. Each additional section (like `[home]` or `[work]`) creates a separate processing area:

- Images from `/path/to/albums/home/personal` and `/path/to/albums/home/photos` → sorted into `/path/to/albums/home/yyyy/mm/` → archived to `/path/to/archives/home/`
- Images from `/path/to/albums/work/corporate` → sorted into `/path/to/albums/work/yyyy/mm/` → archived to `/path/to/archives/work/`

Using multiple import directories is handy when importing images from multiple devices which could potentially have naming collisions.

## Error handling:

Image files which cannot be cleaned, are corrupted or have malformed EXIF data will be left in a timestamped directory. Assuming the data can be manually fixed by the user, the image files can be placed back into the import directory for re-import.  

# How it works

1. **File discovery**: Find files in the `import_dir` which have not been accessed in the last 2 minutes
2. **Safe processing**: Move the files to a timestamped sub-folder for processing
3. **Format standardization**: Adjust all file extensions based on each file's MIME types
4. **Video conversion**: Convert MOV files to MP4 using FFmpeg for better compatibility
5. **EXIF cleanup**: Update blank Exif DateTimeCreated using CreateDate or FileModifyDate when available
6. **Organization**: Sort files into `yyyy/mm` folders and rename to `yyyymmdd-hhmmss-c.ext` format
7. **Archiving**: Create tar archives of the processed images in the archive directory

# Scheduling

importrr uses APScheduler for intelligent job scheduling with built-in error handling and logging.

## Default behavior:
- **Runs every 2 hours** from 8 AM to 10 PM (8, 10, 12, 2, 4, 6, 8, 10 PM)
- **Runs once immediately** on startup
- **Automatic recovery** - failed jobs don't stop the scheduler
- **Graceful shutdown** handling

# Metrics

importrr exposes Prometheus metrics over HTTP so job health, throughput and
transcode cost can be monitored.

- Endpoint: `http://<host>:9201/metrics`
- `METRICS_ENABLED` (default `true`) - set to `0`/`false`/`no` to disable the server
- `METRICS_PORT` (default `9201`) - port the `/metrics` server binds

Any metrics startup failure (port in use, bad port value, anything else) is
logged and swallowed; it never stops the scheduler.

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `importrr_job_runs_total` | counter | `outcome` | Scheduled job runs (`success` = all sections ok, `partial` = some failed, `error` = run aborted) |
| `importrr_job_duration_seconds` | histogram | | Time for one full job (all sections) |
| `importrr_last_success_timestamp_seconds` | gauge | | Unix time of the last job where every section succeeded |
| `importrr_section_failures_total` | counter | `section` | Config sections that raised during a job run |
| `importrr_files_discovered_total` | counter | `section` | Media files found ready to process |
| `importrr_files_organized_total` | counter | `section` | Files sorted into the album tree |
| `importrr_workdir_leftover_files` | gauge | `section` | Files left in a work_dir after the last batch |
| `importrr_batch_duration_seconds` | histogram | | Time to process one import_dir batch |
| `importrr_archives_created_total` | counter | `section` | Tar archives written |
| `importrr_archived_bytes_total` | counter | `section` | Bytes written into tar archives |
| `importrr_archive_incomplete_total` | counter | `section` | Batches whose archive had missing/failed files |
| `importrr_transcode_total` | counter | `outcome` | MOV to MP4 conversions (`success`/`failure`) |
| `importrr_transcode_duration_seconds` | histogram | | Time for one MOV to MP4 conversion |
| `importrr_transcode_input_bytes_total` | counter | | Input bytes fed to ffmpeg |
| `importrr_transcode_output_bytes_total` | counter | | Output bytes produced by ffmpeg |

To scrape it from the standalone Prometheus stack, add a `job_name: importrr`
target pointing at the Docker host on port 9201.

# Usage

## Docker Compose (Recommended)

The easiest way to run importrr is with `docker-compose.yml` plus a local `.env`:

```bash
# Set your paths (edit the copy - .env is gitignored)
cp .env.example .env
$EDITOR .env

# Start / stop
./start.sh          # --pull refreshes the image, --logs follows logs
./stop.sh           # --images also drops the pulled image
```

`docker-compose.yml` keeps no host-specific values - directories, the NFS server
address and its exports all come from `.env` (see `.env.example` for every
variable). `./start.sh` creates `.env` from the example if it is missing,
validates the compose file, brings the stack up, and checks the container does
not crash-loop.

The container starts the scheduler automatically and runs every 2 hours. The
metrics endpoint (see [Metrics](#metrics)) is published on `METRICS_PORT`
(default `9201`); set `METRICS_ENABLED=false` in `.env` to turn it off.

### Plain `docker run` (alternative)

```bash
sudo docker pull curfewmarathon/importrr

docker run -d \
  -v /path/to/config:/config \
  -v /path/to/photos:/data \
  -p 9201:9201 \
  curfewmarathon/importrr
```

The `/data` mount must contain both the `album_dir` and `archive_dir` roots from
your `config.ini`. If they live on separate paths, add a `-v` for each so
archives are not written into the container's own layer.

### Building from source (optional):

```bash
# Build the container locally
docker build -t importrr .

## Local Development

For development or testing, you can run importrr locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scheduler (same as Docker behavior)
python3 src/launch.py

# Or run the main process once for testing
python3 -c "from src.launch import main_process; main_process()"
```
# Requirements

- **Python 3.7+**
- **ExifTool** - for EXIF metadata manipulation
- **FFmpeg** - for video transcoding (MOV to MP4)
- **Docker** (optional) - for containerized deployment

# License

importrr is free software under the terms of the GNU General Public License.
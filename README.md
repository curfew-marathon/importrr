# importrr

importrr is a Python application designed to automate importing of image and movie files into a photo library. It wraps around Phil Harvey's [ExifTool](https://exiftool.org/) which does the heavy lifting behind the scenes. Following the DRY (don't repeat yourself) principle, the application follows the same steps to adjust and clean up the files before sorting and storing them in the photo library. Once running, the images only need to be copied into the import directories and they will be properly organized into the photo album.

## Features

- **Automatic photo/video import and organization** by date
- **MOV to MP4 conversion** using FFmpeg for better compatibility
- **EXIF metadata cleanup** and date standardization
- **Intelligent file naming** with collision handling
- **Archive creation** for backup purposes
- **Built-in scheduler** runs every 2 hours automatically
- **Docker support** for easy deployment

# Configuration

The configuration file is read from `/config/config.ini` (or `config.ini` in the current directory)

## File structure:

```ini
[global]
album_dir = /album
archive_dir = /archive

[folder1]
import_dir = import1

[folder2]
import_dir = import2,import3
```

The `global` section outlines the root folders which apply to each of the sections. The `[section]` will be appended to the root folders and the images will be pulled in from the `import_dir` directories. The `import_dir` can support multiple values separated by a comma.

## Example:

In the configuration above for `folder1`, the images will be imported from `/album/folder1/import1`, renamed and sorted into `/album/folder1/yyyy/mm/yyyymmdd-hhmmss-c.ext` and a tar of the images placed in `/archive/folder1/yyyymmdd-hhmmss-c.tar`

For `folder2`, there will be two iterations:
1. Images from `/album/folder2/import2` → sorted into `/album/folder2/yyyy/mm/` → archived to `/archive/folder2/`
2. Images from `/album/folder2/import3` → sorted into `/album/folder2/yyyy/mm/` → archived to `/archive/folder2/`

Using multiple import directories is handy when importing images from multiple devices which could potentially have naming collisions.

## Error handling:

Image files which cannot be cleaned, are corrupted or have malformed EXIF data will be left in a timestamped directory of `import_dir`. Assuming the data can be manually fixed by the user, the image files can be placed back into the import directory for re-import.  

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

# Usage

## Docker (Recommended)

The easiest way to run importrr is with Docker:

```bash
# Build the container
docker build -t importrr .

# Run with volume mounts for your config and photos
docker run -d \
  -v /path/to/config:/config \
  -v /path/to/photos:/album \
  -v /path/to/archive:/archive \
  importrr
```

The container will start the scheduler automatically and run every 2 hours.

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
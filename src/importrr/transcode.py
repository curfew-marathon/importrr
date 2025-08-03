import logging
import os.path

import ffmpy

from importrr import exifhelper

FFMPEG_PARAMS = '-c:v libx264 -preset slower -crf 20 -c:a aac -b:a 160k -vf format=yuv420p -movflags +faststart'

logger = logging.getLogger(__name__)


def convert(root_dir, source_file):
    logger.info(f"Converting MOV to MP4: {source_file}")
    result = source_file[:-3] + 'mp4'
    output_file = os.path.join(root_dir, result)
    input_file = os.path.join(root_dir, source_file)

    if not os.path.exists(input_file):
        logger.error(f"Input file does not exist: {input_file}")
        return None  # Return None to skip file if conversion fails

    try:
        transcode(input_file, output_file)
        if not os.path.exists(output_file):
            logger.error(f"Output file was not created: {output_file}")
            return None
        
        # Get file sizes for logging
        input_size = os.path.getsize(input_file)
        output_size = os.path.getsize(output_file)
        logger.info(f"Conversion successful: {source_file} ({input_size} bytes) -> {result} ({output_size} bytes)")
        
        exifhelper.copy_tags(root_dir, input_file, output_file)
        return result
    except Exception as e:
        logger.error(f"Failed to convert {source_file}: {e}")
        return None  # Return None to skip file if conversion fails


def transcode(input_file, output_file):
    logger.debug(f"Starting FFmpeg transcoding: {input_file} -> {output_file}")
    try:
        ff = ffmpy.FFmpeg(
            inputs={input_file: '-y'},
            outputs={
                output_file: FFMPEG_PARAMS}
        )
        logger.debug(f"FFmpeg command: {ff.cmd}")
        ff.run()
        logger.debug("FFmpeg transcoding completed successfully")
    except ffmpy.FFRuntimeError as e:
        logger.error(f"FFmpeg failed with exit code: {e.exit_code}")
        if e.stdout:
            logger.error(f"FFmpeg stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"FFmpeg stderr: {e.stderr}")
        # Safely remove output file if it exists
        if os.path.exists(output_file):
            os.remove(output_file)
            logger.debug(f"Removed failed output file: {output_file}")
        raise e

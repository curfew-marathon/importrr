import logging
import os.path

import ffmpy

from importrr import exifhelper

FFMPEG_PARAMS = '-c:v libx264 -preset slower -crf 20 -c:a aac -b:a 160k -vf format=yuv420p -movflags +faststart'

logger = logging.getLogger(__name__)


def convert(root_dir, source_file):
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
        exifhelper.copy_tags(root_dir, input_file, output_file)
        return result
    except Exception as e:
        logger.error(f"Failed to convert {source_file}: {e}")
        return None  # Return None to skip file if conversion fails


def transcode(input_file, output_file):
    try:
        ff = ffmpy.FFmpeg(
            inputs={input_file: '-y'},
            outputs={
                output_file: FFMPEG_PARAMS}
        )
        logger.debug(ff.cmd)
        ff.run()
    except ffmpy.FFRuntimeError as e:
        logger.error(e.exit_code)
        logger.error(e.stdout)
        logger.error(e.stderr)
        # Safely remove output file if it exists
        if os.path.exists(output_file):
            os.remove(output_file)
        raise e

import os
from unittest.mock import MagicMock, patch

import pytest
from ffmpy import FFRuntimeError

from src.importrr.transcode import FFMPEG_PARAMS, convert, transcode


@patch("src.importrr.transcode.transcode")
@patch("src.importrr.transcode.os.path.exists")
def test_convert_input_not_exists(mock_exists, mock_transcode):
    mock_exists.return_value = False

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result is None
    mock_transcode.assert_not_called()
    mock_exists.assert_called_once_with(os.path.join(root_dir, source_file))


@patch("src.importrr.transcode.exifhelper.copy_tags")
@patch("src.importrr.transcode.os.path.getsize")
@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.transcode")
def test_convert_success(mock_transcode, mock_exists, mock_getsize, mock_copy_tags):
    mock_exists.side_effect = [True, True]  # input exists, output exists
    mock_getsize.side_effect = [1024, 512]  # input size, output size

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result == "test_video.mp4"
    mock_transcode.assert_called_once_with(
        os.path.join(root_dir, "test_video.mov"),
        os.path.join(root_dir, "test_video.mp4"),
    )
    mock_copy_tags.assert_called_once_with(
        root_dir,
        os.path.join(root_dir, "test_video.mov"),
        os.path.join(root_dir, "test_video.mp4"),
    )


@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.transcode")
def test_convert_output_not_created(mock_transcode, mock_exists):
    mock_exists.side_effect = [True, False]  # input exists, output does not exist

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result is None
    mock_transcode.assert_called_once_with(
        os.path.join(root_dir, "test_video.mov"),
        os.path.join(root_dir, "test_video.mp4"),
    )


@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.transcode")
def test_convert_exception(mock_transcode, mock_exists):
    mock_exists.return_value = True  # input exists
    mock_transcode.side_effect = Exception("FFmpeg error")

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result is None
    mock_transcode.assert_called_once_with(
        os.path.join(root_dir, "test_video.mov"),
        os.path.join(root_dir, "test_video.mp4"),
    )


@patch("src.importrr.transcode.ffmpy.FFmpeg")
def test_transcode_success(mock_ffmpeg_class):
    mock_ffmpeg_instance = MagicMock()
    mock_ffmpeg_class.return_value = mock_ffmpeg_instance

    input_file = "input.mov"
    output_file = "output.mp4"

    transcode(input_file, output_file)

    mock_ffmpeg_class.assert_called_once_with(
        inputs={input_file: "-y"}, outputs={output_file: FFMPEG_PARAMS}
    )
    mock_ffmpeg_instance.run.assert_called_once()


@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.os.remove")
@patch("src.importrr.transcode.ffmpy.FFmpeg")
def test_transcode_failure(mock_ffmpeg_class, mock_remove, mock_exists):
    mock_ffmpeg_instance = MagicMock()
    mock_ffmpeg_class.return_value = mock_ffmpeg_instance

    # Setup FFRuntimeError
    error = FFRuntimeError(cmd="ffmpeg", exit_code=1, stdout="out", stderr="err")
    mock_ffmpeg_instance.run.side_effect = error

    mock_exists.return_value = True

    input_file = "input.mov"
    output_file = "output.mp4"

    with pytest.raises(FFRuntimeError) as excinfo:
        transcode(input_file, output_file)

    assert excinfo.value.exit_code == 1
    mock_exists.assert_called_once_with(output_file)
    mock_remove.assert_called_once_with(output_file)


@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.os.remove")
@patch("src.importrr.transcode.ffmpy.FFmpeg")
def test_transcode_failure_no_output_file(mock_ffmpeg_class, mock_remove, mock_exists):
    mock_ffmpeg_instance = MagicMock()
    mock_ffmpeg_class.return_value = mock_ffmpeg_instance

    # Setup FFRuntimeError
    error = FFRuntimeError(cmd="ffmpeg", exit_code=1, stdout=None, stderr=None)
    mock_ffmpeg_instance.run.side_effect = error

    mock_exists.return_value = False

    input_file = "input.mov"
    output_file = "output.mp4"

    with pytest.raises(FFRuntimeError):
        transcode(input_file, output_file)

    mock_exists.assert_called_once_with(output_file)
    mock_remove.assert_not_called()

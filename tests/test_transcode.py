import os
from unittest.mock import patch

from src.importrr.transcode import convert


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
    mock_transcode.assert_called_once_with(os.path.join(root_dir, "test_video.mov"), os.path.join(root_dir, "test_video.mp4"))
    mock_copy_tags.assert_called_once_with(root_dir, os.path.join(root_dir, "test_video.mov"), os.path.join(root_dir, "test_video.mp4"))

@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.transcode")
def test_convert_output_not_created(mock_transcode, mock_exists):
    mock_exists.side_effect = [True, False]  # input exists, output does not exist

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result is None
    mock_transcode.assert_called_once_with(os.path.join(root_dir, "test_video.mov"), os.path.join(root_dir, "test_video.mp4"))

@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.transcode")
def test_convert_exception(mock_transcode, mock_exists):
    mock_exists.return_value = True  # input exists
    mock_transcode.side_effect = Exception("FFmpeg error")

    root_dir = "/test/root"
    source_file = "test_video.mov"

    result = convert(root_dir, source_file)

    assert result is None
    mock_transcode.assert_called_once_with(os.path.join(root_dir, "test_video.mov"), os.path.join(root_dir, "test_video.mp4"))

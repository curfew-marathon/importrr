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


@patch("src.importrr.transcode.transcode")
@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.os.path.getsize")
@patch("src.importrr.transcode.exifhelper.copy_tags")
def test_convert_filename_generation(
    mock_copy_tags, mock_getsize, mock_exists, mock_transcode
):
    mock_exists.side_effect = [True, True]  # input exists, output exists
    mock_getsize.return_value = 100

    root_dir = "/test/root"
    source_file = "test_video.MOV"

    result = convert(root_dir, source_file)

    assert result == "test_video.mp4"


@patch("src.importrr.transcode.transcode")
@patch("src.importrr.transcode.os.path.exists")
@patch("src.importrr.transcode.os.path.getsize")
@patch("src.importrr.transcode.exifhelper.copy_tags")
def test_convert_filename_generation_long_extension(
    mock_copy_tags, mock_getsize, mock_exists, mock_transcode
):
    mock_exists.side_effect = [True, True]  # input exists, output exists
    mock_getsize.return_value = 100

    root_dir = "/test/root"
    source_file = "test_video.mpeg"

    result = convert(root_dir, source_file)

    assert result == "test_video.mp4"

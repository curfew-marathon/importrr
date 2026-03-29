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

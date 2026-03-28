import os
import pytest
from unittest.mock import patch

from importrr.transcode import convert


@patch('importrr.transcode.os.path.exists')
@patch('importrr.transcode.transcode')
def test_convert_skip_non_existent_input(mock_transcode, mock_exists):
    mock_exists.return_value = False

    result = convert('/fake/dir', 'video.mov')

    assert result is None
    mock_exists.assert_called_once_with(os.path.join('/fake/dir', 'video.mov'))
    mock_transcode.assert_not_called()

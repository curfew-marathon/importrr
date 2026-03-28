import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.modules['ffmpy'] = MagicMock()
sys.modules['exiftool'] = MagicMock()
sys.modules['exiftool.exceptions'] = MagicMock()

from src.importrr.transcode import convert

@patch('src.importrr.transcode.os.path.exists')
def test_convert_input_not_exists(mock_exists):
    mock_exists.return_value = False
    assert convert('/root', 'file.mov') is None

@patch('src.importrr.transcode.os.path.exists')
@patch('src.importrr.transcode.os.path.getsize')
@patch('src.importrr.transcode.transcode')
@patch('src.importrr.transcode.exifhelper.copy_tags')
def test_convert_success(mock_copy_tags, mock_transcode, mock_getsize, mock_exists):
    mock_exists.side_effect = [True, True]
    mock_getsize.return_value = 100
    assert convert('/root', 'file.mov') == 'file.mp4'

@patch('src.importrr.transcode.os.path.exists')
@patch('src.importrr.transcode.transcode')
def test_convert_output_not_created(mock_transcode, mock_exists):
    mock_exists.side_effect = [True, False]
    assert convert('/root', 'file.mov') is None

@patch('src.importrr.transcode.os.path.exists')
@patch('src.importrr.transcode.transcode')
def test_convert_exception(mock_transcode, mock_exists):
    mock_exists.return_value = True
    mock_transcode.side_effect = Exception("Transcode error")
    assert convert('/root', 'file.mov') is None

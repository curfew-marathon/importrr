import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.modules['ffmpy'] = MagicMock()
sys.modules['exiftool'] = MagicMock()
sys.modules['exiftool.exceptions'] = MagicMock()

from src.importrr.sort import get_media_files, last_accessed, cleanup, Sort

@patch('src.importrr.sort.os.path.exists')
def test_get_media_files_not_exists(mock_exists):
    mock_exists.return_value = False
    assert get_media_files('/fake/dir', 123) == []

@patch('src.importrr.sort.os.path.exists')
@patch('src.importrr.sort.os.path.isdir')
def test_get_media_files_not_dir(mock_isdir, mock_exists):
    mock_exists.return_value = True
    mock_isdir.return_value = False
    assert get_media_files('/fake/file', 123) == []

@patch('src.importrr.sort.os.rmdir')
def test_cleanup_success(mock_rmdir):
    cleanup('/fake/dir')
    mock_rmdir.assert_called_once_with('/fake/dir')

@patch('src.importrr.sort.os.rmdir', side_effect=OSError)
def test_cleanup_error(mock_rmdir):
    cleanup('/fake/dir')
    mock_rmdir.assert_called_once_with('/fake/dir')

@patch('src.importrr.sort.os.stat')
def test_last_accessed(mock_stat):
    mock_stat_result = MagicMock()
    mock_stat_result.st_ctime = 10
    mock_stat_result.st_mtime = 20
    mock_stat_result.st_atime = 15
    mock_stat.return_value = mock_stat_result
    assert last_accessed('file.jpg') == 20

@patch('src.importrr.sort.os.path.isdir')
def test_sort_init_root_dir_not_exist(mock_isdir):
    mock_isdir.return_value = False
    with pytest.raises(IOError):
        Sort('/nonexistent', '/archive')

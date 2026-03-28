import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.modules['ffmpy'] = MagicMock()
sys.modules['exiftool'] = MagicMock()
sys.modules['exiftool.exceptions'] = MagicMock()

from src.importrr.archive import copy, create_tar

def test_copy_empty_list():
    assert copy('/root', [], '/archive', 'prefix') is None

@patch('src.importrr.archive.tarfile.open')
@patch('src.importrr.archive.os.path.exists')
@patch('src.importrr.archive.os.path.getsize')
def test_create_tar_success(mock_getsize, mock_exists, mock_taropen):
    mock_exists.return_value = True
    mock_getsize.return_value = 100
    mock_tar = MagicMock()
    mock_taropen.return_value.__enter__.return_value = mock_tar

    create_tar('/root', ['file1.jpg', 'file2.jpg'], '/archive', 'prefix', 1)

    assert mock_tar.add.call_count == 2

@patch('src.importrr.archive.tarfile.open')
@patch('src.importrr.archive.os.path.exists')
@patch('src.importrr.archive.os.path.getsize')
def test_create_tar_file_not_found(mock_getsize, mock_exists, mock_taropen):
    mock_exists.return_value = False
    mock_getsize.return_value = 100
    mock_tar = MagicMock()
    mock_taropen.return_value.__enter__.return_value = mock_tar

    create_tar('/root', ['file1.jpg'], '/archive', 'prefix', 1)

    mock_tar.add.assert_not_called()

@patch('src.importrr.archive.tarfile.open')
def test_create_tar_exception(mock_taropen):
    mock_taropen.side_effect = Exception("Tar error")
    with pytest.raises(Exception, match="Tar error"):
        create_tar('/root', ['file1.jpg'], '/archive', 'prefix', 1)

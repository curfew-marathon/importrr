import os
from unittest.mock import patch

import pytest

from src.importrr.sort import Sort


@pytest.fixture
def mock_directories(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    return root_dir, archive_dir


@patch("src.importrr.sort.get_media_files")
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.sort_media")
@patch("src.importrr.sort.archive.copy")
def test_launch_valid_import_dir(
    mock_copy,
    mock_sort_media,
    mock_make_work_dir,
    mock_get_media_files,
    mock_directories,
):
    root_dir, archive_dir = mock_directories
    sort = Sort(str(root_dir), str(archive_dir))

    # Mock return values
    mock_get_media_files.return_value = ["test.jpg"]
    mock_sort_media.return_value = ["test.jpg"]

    # Valid relative path
    sort.launch("images")

    # Verify get_media_files is called with correct path
    expected_path = os.path.abspath(os.path.join(str(root_dir), "images"))
    mock_get_media_files.assert_called_once()
    assert mock_get_media_files.call_args[0][0] == expected_path


@patch("src.importrr.sort.get_media_files")
@patch("src.importrr.sort.logger")
def test_launch_path_traversal_parent(
    mock_logger, mock_get_media_files, mock_directories
):
    root_dir, archive_dir = mock_directories
    sort = Sort(str(root_dir), str(archive_dir))

    # Path traversing outside root via parent dir
    sort.launch("../outside")

    # Verify processing was blocked
    mock_get_media_files.assert_not_called()
    mock_logger.error.assert_called_once_with(
        "Path traversal attempt detected: ../outside"
    )


@patch("src.importrr.sort.get_media_files")
@patch("src.importrr.sort.logger")
def test_launch_path_traversal_absolute(
    mock_logger, mock_get_media_files, mock_directories
):
    root_dir, archive_dir = mock_directories
    sort = Sort(str(root_dir), str(archive_dir))

    # Absolute path traversing outside root
    sort.launch("/etc")

    # Verify processing was blocked
    mock_get_media_files.assert_not_called()
    mock_logger.error.assert_called_once_with("Path traversal attempt detected: /etc")


@patch("src.importrr.sort.get_media_files")
@patch("src.importrr.sort.logger")
def test_launch_path_traversal_complex(
    mock_logger, mock_get_media_files, mock_directories
):
    root_dir, archive_dir = mock_directories
    sort = Sort(str(root_dir), str(archive_dir))

    # Complex path traversing outside root
    sort.launch("images/../../outside")

    # Verify processing was blocked
    mock_get_media_files.assert_not_called()
    mock_logger.error.assert_called_once_with(
        "Path traversal attempt detected: images/../../outside"
    )

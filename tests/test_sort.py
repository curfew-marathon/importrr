from unittest.mock import patch

import pytest

from src.importrr.sort import make_work_dir


@patch("src.importrr.sort.logger")
def test_make_work_dir_empty_list(mock_logger):
    make_work_dir("/cur", "/work", [])
    mock_logger.debug.assert_called_once_with(
        "No files to move, skipping work directory creation"
    )


@patch("src.importrr.sort.os.rename")
@patch("src.importrr.sort.os.mkdir")
@patch("src.importrr.sort.os.path.exists")
@patch("src.importrr.sort.logger")
def test_make_work_dir_success(mock_logger, mock_exists, mock_mkdir, mock_rename):
    mock_exists.return_value = False
    file_list = ["file1.jpg", "file2.jpg"]

    make_work_dir("/cur", "/work", file_list)

    mock_mkdir.assert_called_once_with("/work")
    assert mock_rename.call_count == 2
    mock_rename.assert_any_call("/cur/file1.jpg", "/work/file1.jpg")
    mock_rename.assert_any_call("/cur/file2.jpg", "/work/file2.jpg")
    mock_logger.info.assert_called_once_with(
        "Moved 2 files to temporary processing directory"
    )


@patch("src.importrr.sort.os.rename")
@patch("src.importrr.sort.os.path.isdir")
@patch("src.importrr.sort.os.path.exists")
@patch("src.importrr.sort.logger")
def test_make_work_dir_existing_dir(mock_logger, mock_exists, mock_isdir, mock_rename):
    mock_exists.side_effect = lambda path: path == "/work" or path == "/work/file1.jpg"
    mock_isdir.return_value = True
    file_list = ["file1.jpg", "file2.jpg"]

    make_work_dir("/cur", "/work", file_list)

    mock_logger.warning.assert_any_call(
        "Work directory already exists, using existing: /work"
    )
    # file1.jpg exists in target, so it should be skipped
    mock_logger.warning.assert_any_call(
        "Target file already exists, skipping: file1.jpg"
    )
    mock_rename.assert_called_once_with("/cur/file2.jpg", "/work/file2.jpg")


@patch("src.importrr.sort.os.path.isdir")
@patch("src.importrr.sort.os.path.exists")
def test_make_work_dir_existing_file_not_dir(mock_exists, mock_isdir):
    mock_exists.return_value = True
    mock_isdir.return_value = False

    with pytest.raises(
        OSError, match="Work directory path exists but is not a directory: /work"
    ):
        make_work_dir("/cur", "/work", ["file1.jpg"])


@patch("src.importrr.sort.os.mkdir")
@patch("src.importrr.sort.os.path.exists")
@patch("src.importrr.sort.logger")
def test_make_work_dir_mkdir_error(mock_logger, mock_exists, mock_mkdir):
    mock_exists.return_value = False
    mock_mkdir.side_effect = OSError("Permission denied")

    with pytest.raises(OSError, match="Permission denied"):
        make_work_dir("/cur", "/work", ["file1.jpg"])

    mock_logger.error.assert_called_once_with(
        "Failed to create work directory or move files: Permission denied"
    )


@patch("src.importrr.sort.os.rename")
@patch("src.importrr.sort.os.mkdir")
@patch("src.importrr.sort.os.path.exists")
@patch("src.importrr.sort.logger")
def test_make_work_dir_rename_error(mock_logger, mock_exists, mock_mkdir, mock_rename):
    mock_exists.return_value = False
    mock_rename.side_effect = OSError("Rename failed")

    with pytest.raises(OSError, match="Rename failed"):
        make_work_dir("/cur", "/work", ["file1.jpg"])

    mock_logger.error.assert_called_once_with(
        "Failed to create work directory or move files: Rename failed"
    )

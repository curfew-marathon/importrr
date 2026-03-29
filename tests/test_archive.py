import os
from unittest.mock import MagicMock, call, patch

import pytest

from src.importrr.archive import copy, create_tar

# --- Tests for copy ---

@patch("src.importrr.archive.logger")
def test_copy_no_files(mock_logger):
    copy("/test/root", [], "/test/archive", "test_prefix")
    mock_logger.debug.assert_called_once_with("No files to archive")


@patch("src.importrr.archive.transcode.convert")
@patch("src.importrr.archive.logger")
def test_copy_mov_conversion_failure(mock_logger, mock_convert):
    mock_convert.return_value = None
    copy("/test/root", ["video.mov"], "/test/archive", "test_prefix")
    mock_logger.warning.assert_called_once_with("Skipping file due to MOV conversion failure")


@patch("src.importrr.archive.os.stat")
@patch("src.importrr.archive.logger")
def test_copy_oserror_on_stat(mock_logger, mock_stat):
    mock_stat.side_effect = OSError("Access denied")
    copy("/test/root", ["image.jpg"], "/test/archive", "test_prefix")
    mock_logger.error.assert_called_once_with("Cannot access file image.jpg: Access denied")


@patch("src.importrr.archive.create_tar")
@patch("src.importrr.archive.os.stat")
def test_copy_single_tar(mock_stat, mock_create_tar):
    # Mock stat to return a small size
    mock_stat_obj = MagicMock()
    mock_stat_obj.st_size = 1024
    mock_stat.return_value = mock_stat_obj

    root_dir = "/test/root"
    sorted_files = ["image1.jpg", "image2.jpg"]
    archive_dir = "/test/archive"
    prefix = "test_prefix"

    copy(root_dir, sorted_files, archive_dir, prefix)

    mock_create_tar.assert_called_once_with(
        root_dir, ["image1.jpg", "image2.jpg"], archive_dir, prefix, 0
    )


@patch("src.importrr.archive.create_tar")
@patch("src.importrr.archive.os.stat")
@patch("src.importrr.archive.MAX_SIZE", 1500)  # Override MAX_SIZE for testing
def test_copy_create_multiple_tars(mock_stat, mock_create_tar):
    # Mock stat to return sizes that will trigger multiple archives
    # First file: 1000
    # Second file: 600 (Total 1600 > 1500 -> create archive 0 with first file)
    # Third file: 500 (Total 1100 < 1500)
    # Fourth file: 500 (Total 1600 > 1500 -> create archive 1 with second and third file)
    # Fifth file: 1000 -> goes into final archive 2

    mock_stat_objs = []
    for size in [1000, 600, 500, 500, 1000]:
        mock_obj = MagicMock()
        mock_obj.st_size = size
        mock_stat_objs.append(mock_obj)

    mock_stat.side_effect = mock_stat_objs

    root_dir = "/test/root"
    sorted_files = ["file1.jpg", "file2.jpg", "file3.jpg", "file4.jpg", "file5.jpg"]
    archive_dir = "/test/archive"
    prefix = "test_prefix"

    copy(root_dir, sorted_files, archive_dir, prefix)

    assert mock_create_tar.call_count == 3

    # Expected calls to create_tar
    # Because `files` is a list that gets modified in-place and cleared,
    # mock_calls stores a reference to the same list.
    # Let's check call_count and indices instead to avoid the in-place modification issue.
    assert mock_create_tar.call_count == 3
    calls = mock_create_tar.mock_calls
    assert calls[0].args[4] == 0  # index of first archive
    assert calls[1].args[4] == 1  # index of second archive
    assert calls[2].args[4] == 2  # index of final archive


# --- Tests for create_tar ---

@patch("src.importrr.archive.os.path.getsize")
@patch("src.importrr.archive.os.path.exists")
@patch("src.importrr.archive.tarfile.open")
def test_create_tar_success(mock_tarfile_open, mock_exists, mock_getsize):
    mock_exists.return_value = True
    mock_getsize.return_value = 2048

    mock_tar = MagicMock()
    # enter context manager
    mock_tarfile_open.return_value.__enter__.return_value = mock_tar

    root_dir = "/test/root"
    sorted_files = ["file1.jpg", "file2.jpg"]
    archive_dir = "/test/archive"
    prefix = "test_prefix"
    index = 0

    create_tar(root_dir, sorted_files, archive_dir, prefix, index)

    expected_tar_file = os.path.join(archive_dir, f"{prefix}-{index}.tar")

    mock_tarfile_open.assert_called_once_with(expected_tar_file, "w")

    expected_add_calls = [
        call(os.path.join(root_dir, "file1.jpg"), arcname="file1.jpg", recursive=False),
        call(os.path.join(root_dir, "file2.jpg"), arcname="file2.jpg", recursive=False),
    ]
    mock_tar.add.assert_has_calls(expected_add_calls)
    mock_getsize.assert_called_once_with(expected_tar_file)


@patch("src.importrr.archive.logger")
@patch("src.importrr.archive.os.path.getsize")
@patch("src.importrr.archive.os.path.exists")
@patch("src.importrr.archive.tarfile.open")
def test_create_tar_file_not_found(mock_tarfile_open, mock_exists, mock_getsize, mock_logger):
    # first file exists, second does not
    mock_exists.side_effect = [True, False]
    mock_getsize.return_value = 1024

    mock_tar = MagicMock()
    mock_tarfile_open.return_value.__enter__.return_value = mock_tar

    root_dir = "/test/root"
    sorted_files = ["file1.jpg", "file2.jpg"]
    archive_dir = "/test/archive"
    prefix = "test_prefix"
    index = 0

    create_tar(root_dir, sorted_files, archive_dir, prefix, index)

    # tar.add should only be called for file1
    mock_tar.add.assert_called_once_with(
        os.path.join(root_dir, "file1.jpg"), arcname="file1.jpg", recursive=False
    )

    # logger should warn about file2
    mock_logger.warning.assert_called_once_with("File not found for archiving: file2.jpg")


@patch("src.importrr.archive.logger")
@patch("src.importrr.archive.tarfile.open")
def test_create_tar_exception(mock_tarfile_open, mock_logger):
    mock_tarfile_open.side_effect = PermissionError("Permission denied")

    root_dir = "/test/root"
    sorted_files = ["file1.jpg"]
    archive_dir = "/test/archive"
    prefix = "test_prefix"
    index = 0

    with pytest.raises(PermissionError, match="Permission denied"):
        create_tar(root_dir, sorted_files, archive_dir, prefix, index)

    expected_tar_file = os.path.join(archive_dir, f"{prefix}-{index}.tar")
    mock_logger.error.assert_called_once_with(f"Failed to create archive {expected_tar_file}: Permission denied")

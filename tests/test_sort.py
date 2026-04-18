from unittest.mock import patch

from importrr.sort import cleanup


@patch("importrr.sort.logger")
@patch("os.rmdir")
def test_cleanup_success(mock_rmdir, mock_logger):
    cleanup("/tmp/work_dir")
    mock_rmdir.assert_called_once_with("/tmp/work_dir")
    mock_logger.debug.assert_any_call("Removing temporary directory: /tmp/work_dir")
    mock_logger.debug.assert_any_call("Successfully removed directory: /tmp/work_dir")


@patch("importrr.sort.logger")
@patch("os.rmdir")
def test_cleanup_failure(mock_rmdir, mock_logger):
    mock_rmdir.side_effect = OSError("Permission denied")
    cleanup("/tmp/work_dir")
    mock_rmdir.assert_called_once_with("/tmp/work_dir")
    mock_logger.error.assert_called_once_with(
        "Failed to remove directory /tmp/work_dir: Permission denied"
    )

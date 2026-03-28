from unittest.mock import patch
import pytest  # noqa: F401

from src.importrr.exifhelper import adjust_extensions


@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_extensions_params(mock_run_exiftool):
    import_dir = "/test/import/dir"
    root_dir = "/test/root/dir"

    adjust_extensions(import_dir, root_dir)

    expected_params = [
        "-filename<%f.$fileTypeExtension",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "PNG",
        "-ext",
        "3GP",
        "-ext",
        "MOV",
        "-ext",
        "MP4",
        import_dir,
    ]

    mock_run_exiftool.assert_called_once_with(root_dir, expected_params)

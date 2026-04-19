from unittest.mock import patch
import pytest

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

    # Verify the exact params list, particularly that the right extensions are present
    actual_params = mock_run_exiftool.call_args[0][1]
    assert "-ext" in actual_params
    assert "GIF" in actual_params
    assert "JPG" in actual_params
    assert "PNG" in actual_params
    assert "3GP" in actual_params
    assert "MOV" in actual_params
    assert "MP4" in actual_params


@patch("src.importrr.exifhelper.run_exiftool")
@pytest.mark.parametrize("tag", ["CreationDate", "CreateDate"])
def test_backfill_video_tag_params(mock_run_exiftool, tag):
    import_dir = "/test/import/dir"
    root_dir = "/test/root/dir"

    from src.importrr.exifhelper import backfill_video_tag

    backfill_video_tag(import_dir, root_dir, tag)

    expected_params = [
        "-overwrite_original",
        "-datetimeoriginal<" + tag,
        "-time:all<$" + tag,
        "-if",
        "not $datetimeoriginal",
        "-ext",
        "3GP",
        "-ext",
        "MOV",
        "-ext",
        "MP4",
        import_dir,
    ]

    mock_run_exiftool.assert_called_once_with(root_dir, expected_params)


@patch("src.importrr.exifhelper.run_exiftool")
def test_organize_params(mock_run_exiftool):
    import_dir = "/test/import/dir"
    root_dir = "/test/root/dir"

    mock_run_exiftool.return_value = "file1\nfile2\nfile3"

    from src.importrr.exifhelper import organize

    result = organize(import_dir, root_dir)

    expected_params = [
        "-verbose",
        '-filename<${DateTimeOriginal#;DateFmt("%Y/%m")}/$DateTimeOriginal%-c.%e',
        "-d",
        "%Y%m%d-%H%M%S",
        import_dir,
    ]

    mock_run_exiftool.assert_called_once_with(root_dir, expected_params, False)
    assert result == ["file1", "file2", "file3"]


@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_screenshots_params(mock_run_exiftool):
    import_dir = "/test/import/dir"
    root_dir = "/test/root/dir"

    from src.importrr.exifhelper import adjust_screenshots

    adjust_screenshots(import_dir, root_dir)

    assert mock_run_exiftool.call_count == 1

    mock_run_exiftool.assert_called_once_with(
        root_dir,
        [
            "-overwrite_original",
            "-EXIF:DateTimeOriginal<FileModifyDate",
            "-XMP:DateCreated<FileModifyDate",
            "-EXIF:DateTimeOriginal<XMP:DateCreated",
            "-XMP:DateCreated<XMP:DateCreated",
            "-EXIF:DateTimeOriginal<PNG:CreateDate",
            "-XMP:DateCreated<PNG:CreateDate",
            "-if",
            "not $datetimeoriginal",
            "-ext",
            "GIF",
            "-ext",
            "JPG",
            "-ext",
            "PNG",
            import_dir,
        ],
    )


@patch("src.importrr.exifhelper.run_exiftool")
def test_copy_tags_params(mock_run_exiftool):
    from src.importrr.exifhelper import copy_tags

    copy_tags("/test/root", "/test/root/in.mov", "/test/root/out.mp4")

    mock_run_exiftool.assert_called_once_with(
        "/test/root",
        [
            "-overwrite_original",
            "-TagsFromFile",
            "/test/root/in.mov",
            "-all:all>all:all",
            "/test/root/out.mp4",
        ],
    )


@patch("src.importrr.exifhelper.backfill_video_tag")
def test_backfill_videos_calls_both_tags(mock_backfill_video_tag):
    from src.importrr.exifhelper import backfill_videos

    backfill_videos("/test/import", "/test/root")

    assert mock_backfill_video_tag.call_count == 2
    assert mock_backfill_video_tag.mock_calls[0].args == (
        "/test/import",
        "/test/root",
        "CreationDate",
    )
    assert mock_backfill_video_tag.mock_calls[1].args == (
        "/test/import",
        "/test/root",
        "CreateDate",
    )


@patch("src.importrr.exifhelper.os.chdir")
@patch("src.importrr.exifhelper.ExifToolHelper")
def test_run_exiftool_success(mock_exiftool_helper, mock_chdir):
    from src.importrr.exifhelper import run_exiftool

    mock_context = mock_exiftool_helper.return_value.__enter__.return_value
    mock_context.execute.return_value = "ok"

    result = run_exiftool("/test/root", ["-test"])

    assert result == "ok"
    mock_chdir.assert_called_once_with("/test/root")
    mock_context.execute.assert_called_once_with("-test")


@patch("src.importrr.exifhelper.os.chdir")
@patch("src.importrr.exifhelper.ExifToolHelper")
@pytest.mark.parametrize(
    "returncode, stdout, stderr, on_error, should_raise",
    [
        (2, None, None, True, False),
        (1, " 0 image files read", "some error", True, False),
        (1, "some normal output", None, True, True),
        (1, " 0 image files read", None, False, True),
    ],
)
def test_run_exiftool_error_handling(
    mock_exiftool_helper,
    mock_chdir,
    returncode,
    stdout,
    stderr,
    on_error,
    should_raise,
):
    from src.importrr.exifhelper import run_exiftool
    from exiftool.exceptions import ExifToolExecuteError

    # To support both the local mock ExifToolExecuteError which takes any args
    # and the real pyexiftool which expects (status, cmd_stdout, cmd_stderr, params),
    # we instantiate with multiple args or handle gracefully.
    try:
        error = ExifToolExecuteError(returncode, stdout, stderr, "-test")
    except TypeError:
        error = ExifToolExecuteError(returncode)

    error.returncode = returncode
    error.stdout = stdout
    error.stderr = stderr

    mock_context = mock_exiftool_helper.return_value.__enter__.return_value
    mock_context.execute.side_effect = error

    if should_raise:
        with pytest.raises(ExifToolExecuteError):
            run_exiftool("/test/root", ["-test"], on_error=on_error)
    else:
        run_exiftool("/test/root", ["-test"], on_error=on_error)

    mock_chdir.assert_called_once_with("/test/root")

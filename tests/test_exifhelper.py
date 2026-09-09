from unittest.mock import call, patch

import pytest

from src.importrr.exifhelper import adjust_extensions


@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_extensions_params(mock_run_exiftool):
    import_dir = "/test/import/dir"
    root_dir = "/test/root/dir"

    adjust_extensions(import_dir, root_dir)

    expected_params = [
        "-P",
        "-filename<%f.$fileTypeExtension",
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "JPEG",
        "-ext",
        "PNG",
        "-ext",
        "HEIC",
        "-ext",
        "HEIF",
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
    assert "-P" in actual_params  # a rename must not bump mtime
    assert "-ext" in actual_params
    for ext in ("GIF", "JPG", "JPEG", "PNG", "HEIC", "HEIF", "3GP", "MOV", "MP4"):
        assert ext in actual_params  # ".jpeg"/".HEIC" would skip later passes otherwise


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

    from src.importrr.exifhelper import (
        _EMBEDDED_DATE_SOURCES,
        _IMAGE_EXTS,
        adjust_screenshots,
    )

    mock_run_exiftool.return_value = None  # probe: no dateless files

    adjust_screenshots(import_dir, root_dir)

    # Pass A (embedded sources), the dateless-file probe, Pass B (mtime).
    assert mock_run_exiftool.call_count == 3

    # EXIF-dated still formats. HEIC/HEIF included so a stripped re-encode gets
    # the same fallback as a dateless JPG instead of being left unorganized.
    assert _IMAGE_EXTS == ("GIF", "JPG", "PNG", "HEIC", "HEIF")
    ext_args = [
        "-ext",
        "GIF",
        "-ext",
        "JPG",
        "-ext",
        "PNG",
        "-ext",
        "HEIC",
        "-ext",
        "HEIF",
    ]

    common = ["-if", "not $datetimeoriginal", *ext_args, import_dir]

    embedded = ["-overwrite_original", "-P"]
    for source in _EMBEDDED_DATE_SOURCES:
        embedded += [
            f"-EXIF:DateTimeOriginal<{source}",
            f"-XMP:DateCreated<{source}",
        ]

    mock_run_exiftool.assert_has_calls(
        [
            call(root_dir, embedded + common),
            call(
                root_dir,
                [
                    "-if",
                    "not $datetimeoriginal",
                    "-p",
                    "$filename",
                    *ext_args,
                    import_dir,
                ],
                False,
            ),
            call(
                root_dir,
                [
                    "-overwrite_original",
                    "-P",
                    "-EXIF:DateTimeOriginal<FileModifyDate",
                    "-XMP:DateCreated<FileModifyDate",
                ]
                + common,
            ),
        ],
        any_order=False,
    )
    # FileModifyDate is the last resort, never an embedded source.
    assert "FileModifyDate" not in _EMBEDDED_DATE_SOURCES
    # Pin the whole priority order (worst first, so exiftool's "last valid"
    # redirect picks the best). This mirrors photo-stage's DATE_SOURCES; a silent
    # reorder here would desync the two tools.
    assert _EMBEDDED_DATE_SOURCES == (
        "EXIF:ModifyDate",
        "PNG:ModifyDate",
        "PNG:CreateDate",
        "PNG:CreationTime",
        "Composite:GPSDateTime",
        "IPTC:DateCreated",
        "XMP:CreateDate",
        "XMP:DateCreated",
        "EXIF:CreateDate",
    )


@patch("src.importrr.exifhelper.metrics.DATES_GUESSED_FROM_MTIME_TOTAL")
@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_screenshots_warns_and_counts_mtime_guesses(
    mock_run_exiftool, mock_counter, caplog
):
    from src.importrr.exifhelper import adjust_screenshots

    # Pass A returns anything; the probe (2nd call) returns two dateless names.
    mock_run_exiftool.side_effect = [None, "a.jpg\nb.png\n", None]

    with caplog.at_level("WARNING"):
        adjust_screenshots("/imp", "/root")

    warned = [r.message for r in caplog.records if "using file mtime" in r.message]
    assert warned == [
        "No capture date in a.jpg - using file mtime (likely wrong)",
        "No capture date in b.png - using file mtime (likely wrong)",
    ]
    assert mock_counter.inc.call_count == 2


@patch("src.importrr.exifhelper.metrics.DATES_GUESSED_FROM_MTIME_TOTAL")
@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_screenshots_no_guesses_when_probe_empty(
    mock_run_exiftool, mock_counter
):
    from src.importrr.exifhelper import adjust_screenshots

    mock_run_exiftool.return_value = None  # probe finds nothing dateless

    adjust_screenshots("/imp", "/root")

    mock_counter.inc.assert_not_called()


@patch("src.importrr.exifhelper.metrics.DATES_GUESSED_FROM_MTIME_TOTAL")
@patch("src.importrr.exifhelper.run_exiftool")
def test_adjust_screenshots_does_not_count_when_mtime_pass_fails(
    mock_run_exiftool, mock_counter, caplog
):
    from src.importrr.exifhelper import adjust_screenshots

    # Pass A ok, probe finds a dateless file, Pass B raises.
    mock_run_exiftool.side_effect = [None, "a.jpg\n", RuntimeError("exiftool blew up")]

    with pytest.raises(RuntimeError), caplog.at_level("WARNING"):
        adjust_screenshots("/imp", "/root")

    # Pass B never applied the mtime date, so nothing is warned or counted.
    assert not any("using file mtime" in r.message for r in caplog.records)
    mock_counter.inc.assert_not_called()


@patch("src.importrr.exifhelper.run_exiftool")
def test_images_missing_capture_date_parses_and_tolerates_empty(mock_run_exiftool):
    from src.importrr.exifhelper import _images_missing_capture_date

    mock_run_exiftool.return_value = "one.jpg\ntwo.png\n\n"
    assert _images_missing_capture_date("/imp", "/root") == ["one.jpg", "two.png"]

    mock_run_exiftool.return_value = None  # exiftool exit 2 -> run_exiftool -> None
    assert _images_missing_capture_date("/imp", "/root") == []


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
    from exiftool.exceptions import ExifToolExecuteError

    from src.importrr.exifhelper import run_exiftool

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


# --- classify_unprocessed ---


def _classify_with(tag_dicts):
    with (
        patch("src.importrr.exifhelper.os.chdir"),
        patch("src.importrr.exifhelper.ExifToolHelper") as mock_helper,
    ):
        et = mock_helper.return_value.__enter__.return_value
        et.get_tags.return_value = tag_dicts

        from src.importrr.exifhelper import classify_unprocessed

        return classify_unprocessed("/album", "/album/import/20260905184400", NAMES)


NAMES = ["VID_1.mov", "BAD.txt", "OK.jpg"]


def test_classify_unprocessed_reasons():
    result = _classify_with(
        [
            {
                "SourceFile": "/album/import/20260905184400/VID_1.mov",
                "FileType": "MOV",
            },
            {
                "SourceFile": "/album/import/20260905184400/BAD.txt",
                "Error": "Unknown file type",
            },
            {
                "SourceFile": "/album/import/20260905184400/OK.jpg",
                "FileType": "JPEG",
                "DateTimeOriginal": "2026:09:05 18:44:00",
            },
        ]
    )

    assert result == [
        {"name": "VID_1.mov", "reason": "no capture date in metadata (type=MOV)"},
        {"name": "BAD.txt", "reason": "unreadable or unsupported: Unknown file type"},
        {"name": "OK.jpg", "reason": "not renamed by ExifTool (unexpected)"},
    ]


def test_classify_unprocessed_no_metadata_is_generic_reason():
    result = _classify_with([])
    assert {item["name"] for item in result} == {"VID_1.mov", "BAD.txt", "OK.jpg"}
    # No metadata returned for any file -> generic unreadable reason.
    assert all("ExifTool returned no metadata" in item["reason"] for item in result)


def test_classify_unprocessed_classifies_every_name():
    # No name is special-cased: even a file called "manifest.yml" gets a reason
    # (make_work_dir renames such collisions before we get here).
    with (
        patch("src.importrr.exifhelper.os.chdir"),
        patch("src.importrr.exifhelper.ExifToolHelper") as mock_helper,
    ):
        mock_helper.return_value.__enter__.return_value.get_tags.return_value = []

        from src.importrr.exifhelper import classify_unprocessed

        result = classify_unprocessed(
            "/album",
            "/work",
            ["manifest.yml", "manifest.yml.tmp", "manifest.yml.jpg"],
        )

    assert [item["name"] for item in result] == [
        "manifest.yml",
        "manifest.yml.tmp",
        "manifest.yml.jpg",
    ]


def test_classify_unprocessed_survives_exiftool_error(caplog):
    from exiftool.exceptions import ExifToolExecuteError

    with (
        patch("src.importrr.exifhelper.os.chdir"),
        patch("src.importrr.exifhelper.ExifToolHelper") as mock_helper,
    ):
        et = mock_helper.return_value.__enter__.return_value
        try:
            err = ExifToolExecuteError(1, "out", "err", "-p")
        except TypeError:
            err = ExifToolExecuteError(1)
        et.get_tags.side_effect = err

        from src.importrr.exifhelper import classify_unprocessed

        result = classify_unprocessed("/album", "/work", ["a.mov"])

    assert result == [
        {
            "name": "a.mov",
            "reason": "unreadable or unsupported: ExifTool returned no metadata",
        }
    ]


def test_classify_unprocessed_empty():
    from src.importrr.exifhelper import classify_unprocessed

    assert classify_unprocessed("/album", "/work", []) == []

import os
from unittest.mock import Mock, patch

import pytest
import yaml

from importrr import metrics
from importrr.sort import (
    MANIFEST_NAME,
    Sort,
    _skip_category,
    cleanup,
    get_media_files,
    make_work_dir,
    sort_media,
    write_manifest,
)


def _hist_count(histogram):
    for sample in histogram.collect()[0].samples:
        if sample.name.endswith("_count"):
            return sample.value
    return 0


# --- Sort.__init__ validation ---


def test_sort_init_raises_when_root_dir_missing(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(OSError, match="Directory doesn't exist"):
        Sort(str(missing))


def test_sort_init_raises_when_archive_dir_missing(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    missing_archive = tmp_path / "nope"
    with pytest.raises(OSError, match="Directory doesn't exist"):
        Sort(str(root), str(missing_archive))


# --- sort_media parsing ---


@patch("importrr.sort.exifhelper")
def test_sort_media_parses_original_name_and_album_path(mock_exifhelper):
    mock_exifhelper.organize.return_value = [
        "'/work/20260905184400/IMG_1234.jpg' --> '2026/09/20260905-184400.jpg'",
        "'/work/20260905184400/VID_9999.mov' --> '2026/09/20260905-184530.mov'",
        "",
        "    ",
        "1 image files updated",
    ]

    entries = sort_media("/album", "/work/20260905184400")

    assert entries == [
        {
            "original_name": "IMG_1234.jpg",
            "album_path": "2026/09/20260905-184400.jpg",
        },
        {
            "original_name": "VID_9999.mov",
            "album_path": "2026/09/20260905-184530.mov",
        },
    ]


# --- write_manifest ---


def test_write_manifest_shape(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    entries = [
        {"original_name": "IMG_1234.jpg", "album_path": "2026/09/x.jpg"},
        {"original_name": "VID_9999.mov", "album_path": "2026/09/y.mov"},
    ]

    write_manifest(str(tmp_path), str(work_dir), "20260905184400", entries)

    manifest_path = work_dir / MANIFEST_NAME
    assert manifest_path.exists()

    doc = yaml.safe_load(manifest_path.read_text())
    assert doc["batch_id"] == "20260905184400"
    assert isinstance(doc["batch_id"], str)

    jpg, mov = doc["files"]
    assert jpg == {
        "original_name": "IMG_1234.jpg",
        "album_path": os.path.abspath(str(tmp_path / "2026/09/x.jpg")),
    }
    assert "transcoded_mp4_path" not in jpg

    assert mov["album_path"] == os.path.abspath(str(tmp_path / "2026/09/y.mov"))
    assert mov["transcoded_mp4_path"] == os.path.abspath(
        str(tmp_path / "2026/09/y.mp4")
    )
    assert doc["skipped"] == []


def test_write_manifest_records_skipped(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    skipped = [
        {"name": "VID_1.mov", "reason": "no capture date in metadata (type=MOV)"},
        {"name": "notes.txt", "reason": "unreadable or unsupported: Unknown file type"},
    ]

    write_manifest(str(tmp_path), str(work_dir), "b", [], skipped)

    doc = yaml.safe_load((work_dir / MANIFEST_NAME).read_text())
    assert doc["files"] == []
    assert doc["skipped"] == skipped


def test_write_manifest_leaves_no_temp_file_on_success(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    write_manifest(str(tmp_path), str(work_dir), "b", [])

    assert (work_dir / MANIFEST_NAME).exists()
    assert list(work_dir.iterdir()) == [work_dir / MANIFEST_NAME]


def test_write_manifest_write_failure_is_swallowed(tmp_path):
    # work_dir does not exist -> open() raises OSError, which must be caught,
    # and no manifest or temp file is created.
    missing = tmp_path / "missing"
    write_manifest(str(tmp_path), str(missing), "b", [])
    assert not missing.exists()


# --- Sort.launch pipeline ordering ---


@patch("importrr.sort.os.path.exists", return_value=False)
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy")
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_pipeline_order(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_isdir,
    _mock_exists,
    tmp_path,
):
    mock_get_media_files.return_value = ["a.jpg"]
    mock_sort_media.return_value = [{"original_name": "a.jpg", "album_path": "a.jpg"}]
    mock_copy.return_value = True

    manager = Mock()
    manager.attach_mock(mock_sort_media, "sort_media")
    manager.attach_mock(mock_write_manifest, "write_manifest")
    manager.attach_mock(mock_copy, "copy")
    manager.attach_mock(mock_cleanup, "cleanup")

    sort = Sort(str(tmp_path), str(tmp_path))
    before_discovered = metrics.FILES_DISCOVERED_TOTAL.labels(
        section=sort.section
    )._value.get()
    before_organized = metrics.FILES_ORGANIZED_TOTAL.labels(
        section=sort.section, media_type="image"
    )._value.get()

    sort.launch("images")

    assert [c[0] for c in manager.mock_calls] == [
        "sort_media",
        "write_manifest",
        "copy",
        "cleanup",
    ]
    assert (
        metrics.FILES_DISCOVERED_TOTAL.labels(section=sort.section)._value.get()
        == before_discovered + 1
    )
    assert (
        metrics.FILES_ORGANIZED_TOTAL.labels(
            section=sort.section, media_type="image"
        )._value.get()
        == before_organized + 1
    )


@patch("importrr.sort.logger")
@patch("importrr.sort.os.path.exists", return_value=False)
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy")
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_keeps_work_dir_when_archive_incomplete(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_isdir,
    _mock_exists,
    mock_logger,
    tmp_path,
):
    mock_get_media_files.return_value = ["a.jpg"]
    mock_sort_media.return_value = [{"original_name": "a.jpg", "album_path": "a.jpg"}]
    mock_copy.return_value = False

    sort = Sort(str(tmp_path), str(tmp_path))
    before_incomplete = metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(
        section=sort.section
    )._value.get()

    sort.launch("images")

    mock_cleanup.assert_not_called()
    assert any(
        "Archive incomplete" in str(c.args[0]) for c in mock_logger.warning.mock_calls
    )
    assert (
        metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(section=sort.section)._value.get()
        == before_incomplete + 1
    )


@patch("importrr.sort.os.path.exists", return_value=False)
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy")
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_counts_incomplete_when_archive_raises(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_isdir,
    _mock_exists,
    tmp_path,
):
    mock_get_media_files.return_value = ["a.jpg"]
    mock_sort_media.return_value = [{"original_name": "a.jpg", "album_path": "a.jpg"}]
    mock_copy.side_effect = OSError("tar write failed")

    sort = Sort(str(tmp_path), str(tmp_path))
    before_incomplete = metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(
        section=sort.section
    )._value.get()
    before_batches = _hist_count(metrics.BATCH_DURATION_SECONDS)

    with pytest.raises(OSError, match="tar write failed"):
        sort.launch("images")

    # The exception propagates for recovery handling, but the batch is still
    # counted as an incomplete archive, its duration is still recorded, and
    # cleanup is skipped.
    mock_cleanup.assert_not_called()
    assert (
        metrics.ARCHIVE_INCOMPLETE_TOTAL.labels(section=sort.section)._value.get()
        == before_incomplete + 1
    )
    assert _hist_count(metrics.BATCH_DURATION_SECONDS) == before_batches + 1


@patch("importrr.sort.logger")
@patch("importrr.sort.exifhelper.classify_unprocessed")
@patch("importrr.sort.os.listdir", return_value=["stuck.mov"])
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.os.path.exists", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy", return_value=True)
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_passes_skip_reasons_to_manifest(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_exists,
    _mock_isdir,
    _mock_listdir,
    mock_classify,
    mock_logger,
    tmp_path,
):
    mock_get_media_files.return_value = ["ok.jpg", "stuck.mov"]
    mock_sort_media.return_value = [{"original_name": "ok.jpg", "album_path": "ok.jpg"}]
    skipped = [
        {"name": "stuck.mov", "reason": "no capture date in metadata (type=MOV)"}
    ]
    mock_classify.return_value = skipped

    sort = Sort(str(tmp_path), str(tmp_path))
    sort.launch("images")

    mock_classify.assert_called_once()
    assert mock_classify.call_args[0][0] == sort.root_dir
    assert mock_classify.call_args[0][2] == ["stuck.mov"]

    # skipped list is threaded into the manifest as the 5th positional arg
    assert mock_write_manifest.call_args[0][4] == skipped
    assert any(
        "Unable to process 1 files" in str(c.args[0])
        for c in mock_logger.warning.mock_calls
    )


@patch("importrr.sort.exifhelper.classify_unprocessed")
@patch("importrr.sort.os.listdir", return_value=["stuck.mov"])
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.os.path.exists", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy", return_value=True)
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_counts_skipped_files_by_category(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_exists,
    _mock_isdir,
    _mock_listdir,
    mock_classify,
    tmp_path,
):
    mock_get_media_files.return_value = ["ok.jpg", "stuck.mov"]
    mock_sort_media.return_value = [{"original_name": "ok.jpg", "album_path": "ok.jpg"}]
    mock_classify.return_value = [
        {"name": "stuck.mov", "reason": "no capture date in metadata (type=MOV)"}
    ]

    sort = Sort(str(tmp_path), str(tmp_path))
    before = metrics.FILES_SKIPPED_TOTAL.labels(
        section=sort.section, reason="no_capture_date"
    )._value.get()

    sort.launch("images")

    assert (
        metrics.FILES_SKIPPED_TOTAL.labels(
            section=sort.section, reason="no_capture_date"
        )._value.get()
        == before + 1
    )


@patch("importrr.sort.os.listdir", return_value=[])
@patch("importrr.sort.os.path.isdir", return_value=True)
@patch("importrr.sort.os.path.exists", return_value=True)
@patch("importrr.sort.cleanup")
@patch("importrr.sort.archive.copy", return_value=True)
@patch("importrr.sort.write_manifest")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.make_work_dir")
@patch("importrr.sort.get_media_files")
def test_launch_counts_organized_files_by_media_type(
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_write_manifest,
    mock_copy,
    mock_cleanup,
    _mock_exists,
    _mock_isdir,
    _mock_listdir,
    tmp_path,
):
    mock_get_media_files.return_value = ["a.jpg", "b.mov", "c.txt"]
    mock_sort_media.return_value = [
        {"original_name": "a.jpg", "album_path": "2026/09/a.jpg"},
        {"original_name": "b.mov", "album_path": "2026/09/b.mov"},
        {"original_name": "c.txt", "album_path": "2026/09/c.txt"},
    ]

    sort = Sort(str(tmp_path), str(tmp_path))
    before = {
        media_type: metrics.FILES_ORGANIZED_TOTAL.labels(
            section=sort.section, media_type=media_type
        )._value.get()
        for media_type in ("image", "video", "other")
    }

    sort.launch("images")

    for media_type in ("image", "video", "other"):
        assert (
            metrics.FILES_ORGANIZED_TOTAL.labels(
                section=sort.section, media_type=media_type
            )._value.get()
            == before[media_type] + 1
        )


@patch("importrr.sort.get_media_files", return_value=[])
def test_launch_no_files_found_resets_leftover_gauge(mock_get_media_files, tmp_path):
    sort = Sort(str(tmp_path), str(tmp_path))
    metrics.WORKDIR_LEFTOVER_FILES.labels(section=sort.section).set(5)

    sort.launch("images")

    assert metrics.WORKDIR_LEFTOVER_FILES.labels(section=sort.section)._value.get() == 0


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("unreadable or unsupported: Unknown file type", "unreadable"),
        ("unreadable or unsupported: ExifTool returned no metadata", "unreadable"),
        ("no capture date in metadata (type=MOV)", "no_capture_date"),
        ("not renamed by ExifTool (unexpected)", "other"),
    ],
)
def test_skip_category(reason, expected):
    assert _skip_category(reason) == expected


# --- make_work_dir manifest-name collision ---


@patch("importrr.sort.logger")
def test_make_work_dir_renames_reserved_manifest_name(mock_logger, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / MANIFEST_NAME).write_text("user data")
    (src / f"{MANIFEST_NAME}.tmp").write_text("more user data")
    (src / "photo.jpg").write_text("img")
    work = tmp_path / "work"

    make_work_dir(
        str(src),
        str(work),
        [MANIFEST_NAME, f"{MANIFEST_NAME}.tmp", "photo.jpg"],
    )

    assert (work / f"{MANIFEST_NAME}.orig").read_text() == "user data"
    assert (work / f"{MANIFEST_NAME}.tmp.orig").read_text() == "more user data"
    assert (work / "photo.jpg").read_text() == "img"
    assert not (work / MANIFEST_NAME).exists()
    assert any(
        "collides with the reserved manifest name" in str(c.args[0])
        for c in mock_logger.warning.mock_calls
    )


@patch("importrr.sort.exifhelper.classify_unprocessed")
@patch("importrr.sort.sort_media")
@patch("importrr.sort.archive.copy", return_value=True)
def test_launch_preserves_user_file_named_manifest(
    mock_copy, mock_sort_media, mock_classify, tmp_path
):
    album = tmp_path / "album"
    (album / "images").mkdir(parents=True)
    (album / "images" / MANIFEST_NAME).write_text("PRECIOUS USER DATA")

    mock_sort_media.return_value = []  # ExifTool organizes nothing
    mock_classify.return_value = [
        {"name": f"{MANIFEST_NAME}.orig", "reason": "no capture date in metadata"}
    ]

    with patch("importrr.sort.last_accessed", return_value=0):
        Sort(str(album), str(tmp_path)).launch("images")

    work_dirs = [p for p in (album / "images").iterdir() if p.is_dir()]
    assert len(work_dirs) == 1
    wd = work_dirs[0]
    # The user's file survived intact under .orig, retained for inspection.
    assert (wd / f"{MANIFEST_NAME}.orig").read_text() == "PRECIOUS USER DATA"
    # The WAL is a separate file that did not clobber it.
    manifest = yaml.safe_load((wd / MANIFEST_NAME).read_text())
    assert manifest["batch_id"]
    assert manifest["skipped"] == mock_classify.return_value


# --- cleanup ---


def test_cleanup_removes_empty_dir(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    cleanup(str(work_dir))

    assert not work_dir.exists()


def test_cleanup_removes_dir_with_only_manifest(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / MANIFEST_NAME).write_text("batch_id: x\n")

    cleanup(str(work_dir))

    assert not work_dir.exists()


@patch("importrr.sort.logger")
def test_cleanup_keeps_dir_and_manifest_when_media_remains(mock_logger, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / MANIFEST_NAME).write_text("batch_id: x\n")
    (work_dir / "leftover.jpg").write_text("data")

    cleanup(str(work_dir))

    assert work_dir.exists()
    assert (work_dir / MANIFEST_NAME).exists()
    assert (work_dir / "leftover.jpg").exists()
    mock_logger.warning.assert_called_once()


def test_cleanup_missing_dir_is_noop(tmp_path):
    cleanup(str(tmp_path / "does-not-exist"))


@patch("importrr.sort.os.listdir", side_effect=OSError("boom"))
def test_cleanup_listdir_failure_is_swallowed(mock_listdir, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    cleanup(str(work_dir))  # must not raise

    assert work_dir.exists()


@patch("importrr.sort.os.rmdir", side_effect=OSError("boom"))
def test_cleanup_rmdir_failure_is_swallowed(mock_rmdir, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    cleanup(str(work_dir))  # must not raise


# --- get_media_files recency summary ---


@patch("importrr.sort.logger")
def test_get_media_files_logs_deferred_count(mock_logger, tmp_path):
    (tmp_path / "recent.jpg").write_text("x")

    # cutoff at the epoch -> the file counts as recently touched and is deferred
    result = get_media_files(str(tmp_path), 0)

    assert result == []
    assert any(
        "Deferred 1 recently touched file(s)" in str(c.args[0])
        for c in mock_logger.info.mock_calls
    )


@patch("importrr.sort.logger")
def test_get_media_files_no_deferred_message_when_all_eligible(mock_logger, tmp_path):
    (tmp_path / "old.jpg").write_text("x")

    # cutoff far in the future -> every file is eligible
    result = get_media_files(str(tmp_path), 2**40)

    assert result == ["old.jpg"]
    assert not any("Deferred" in str(c.args[0]) for c in mock_logger.info.mock_calls)


# --- get_media_files error handling ---


def test_get_media_files_missing_dir_returns_empty(tmp_path):
    assert get_media_files(str(tmp_path / "missing"), 0) == []


def test_get_media_files_not_a_directory_returns_empty(tmp_path):
    f = tmp_path / "not_a_dir"
    f.write_text("x")

    assert get_media_files(str(f), 0) == []


@patch("importrr.sort.os.listdir", side_effect=PermissionError("denied"))
def test_get_media_files_permission_error_returns_empty(mock_listdir, tmp_path):
    assert get_media_files(str(tmp_path), 0) == []


@patch("importrr.sort.os.listdir", side_effect=OSError("boom"))
def test_get_media_files_oserror_returns_empty(mock_listdir, tmp_path):
    assert get_media_files(str(tmp_path), 0) == []


def test_get_media_files_skips_subdirectories(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "old.jpg").write_text("x")

    result = get_media_files(str(tmp_path), 2**40)

    assert result == ["old.jpg"]


@patch("importrr.sort.os.path.isfile", side_effect=OSError("stat failed"))
def test_get_media_files_per_entry_stat_error_is_skipped(mock_isfile, tmp_path):
    (tmp_path / "broken.jpg").write_text("x")

    assert get_media_files(str(tmp_path), 2**40) == []


def test_get_media_files_unresolvable_entry_is_skipped(tmp_path):
    # A broken symlink is neither a file nor a directory (isfile/isdir both
    # return False without raising, since the target doesn't exist).
    (tmp_path / "weird").symlink_to(tmp_path / "does-not-exist")

    assert get_media_files(str(tmp_path), 2**40) == []


# --- make_work_dir error handling ---


def test_make_work_dir_noop_when_no_files(tmp_path):
    work_dir = tmp_path / "work"

    make_work_dir(str(tmp_path), str(work_dir), [])

    assert not work_dir.exists()


def test_make_work_dir_reuses_existing_directory(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_text("x")
    work_dir = tmp_path / "work"
    work_dir.mkdir()  # already exists

    make_work_dir(str(src), str(work_dir), ["a.jpg"])

    assert (work_dir / "a.jpg").read_text() == "x"


def test_make_work_dir_raises_when_target_path_is_a_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    work_dir = tmp_path / "work"
    work_dir.write_text("not a directory")  # path exists but is a file

    with pytest.raises(OSError, match="exists but is not a directory"):
        make_work_dir(str(src), str(work_dir), ["a.jpg"])


def test_make_work_dir_skips_file_already_at_destination(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_text("new")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "a.jpg").write_text("already there")

    make_work_dir(str(src), str(work_dir), ["a.jpg"])

    # The pre-existing destination file is left untouched, and the source
    # file is never moved.
    assert (work_dir / "a.jpg").read_text() == "already there"
    assert (src / "a.jpg").read_text() == "new"


@patch("importrr.sort.os.rename", side_effect=OSError("disk full"))
def test_make_work_dir_reraises_on_rename_failure(mock_rename, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_text("x")
    work_dir = tmp_path / "work"

    with pytest.raises(OSError, match="disk full"):
        make_work_dir(str(src), str(work_dir), ["a.jpg"])

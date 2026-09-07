import os
from unittest.mock import Mock, patch

import pytest
import yaml

from importrr import metrics
from src.importrr.sort import (
    MANIFEST_NAME,
    Sort,
    cleanup,
    get_media_files,
    sort_media,
    write_manifest,
)


def _hist_count(histogram):
    for sample in histogram.collect()[0].samples:
        if sample.name.endswith("_count"):
            return sample.value
    return 0


# --- sort_media parsing ---


@patch("src.importrr.sort.exifhelper")
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


@patch("src.importrr.sort.os.path.exists", return_value=False)
@patch("src.importrr.sort.os.path.isdir", return_value=True)
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.archive.copy")
@patch("src.importrr.sort.write_manifest")
@patch("src.importrr.sort.sort_media")
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files")
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
        section=sort.section
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
        metrics.FILES_ORGANIZED_TOTAL.labels(section=sort.section)._value.get()
        == before_organized + 1
    )


@patch("src.importrr.sort.logger")
@patch("src.importrr.sort.os.path.exists", return_value=False)
@patch("src.importrr.sort.os.path.isdir", return_value=True)
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.archive.copy")
@patch("src.importrr.sort.write_manifest")
@patch("src.importrr.sort.sort_media")
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files")
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


@patch("src.importrr.sort.os.path.exists", return_value=False)
@patch("src.importrr.sort.os.path.isdir", return_value=True)
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.archive.copy")
@patch("src.importrr.sort.write_manifest")
@patch("src.importrr.sort.sort_media")
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files")
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


@patch("src.importrr.sort.logger")
@patch("src.importrr.sort.exifhelper.classify_unprocessed")
@patch("src.importrr.sort.os.listdir", return_value=["stuck.mov"])
@patch("src.importrr.sort.os.path.isdir", return_value=True)
@patch("src.importrr.sort.os.path.exists", return_value=True)
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.archive.copy", return_value=True)
@patch("src.importrr.sort.write_manifest")
@patch("src.importrr.sort.sort_media")
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files")
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


@patch("src.importrr.sort.logger")
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


# --- get_media_files recency summary ---


@patch("src.importrr.sort.logger")
def test_get_media_files_logs_deferred_count(mock_logger, tmp_path):
    (tmp_path / "recent.jpg").write_text("x")

    # cutoff at the epoch -> the file counts as recently touched and is deferred
    result = get_media_files(str(tmp_path), 0)

    assert result == []
    assert any(
        "Deferred 1 recently touched file(s)" in str(c.args[0])
        for c in mock_logger.info.mock_calls
    )


@patch("src.importrr.sort.logger")
def test_get_media_files_no_deferred_message_when_all_eligible(mock_logger, tmp_path):
    (tmp_path / "old.jpg").write_text("x")

    # cutoff far in the future -> every file is eligible
    result = get_media_files(str(tmp_path), 2**40)

    assert result == ["old.jpg"]
    assert not any("Deferred" in str(c.args[0]) for c in mock_logger.info.mock_calls)

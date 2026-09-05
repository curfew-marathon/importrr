import os
from unittest.mock import patch

import yaml

from src.importrr.sort import MANIFEST_NAME, cleanup, sort_media, write_manifest

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


def test_write_manifest_write_failure_is_swallowed(tmp_path):
    # work_dir does not exist -> open() raises OSError, which must be caught
    write_manifest(str(tmp_path), str(tmp_path / "missing"), "b", [])


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

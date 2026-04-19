import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.importrr.sort import Sort, get_media_files, last_accessed, make_work_dir, sort_media


@patch("src.importrr.sort.exifhelper.organize")
@patch("src.importrr.sort.exifhelper.backfill_videos")
@patch("src.importrr.sort.exifhelper.adjust_screenshots")
@patch("src.importrr.sort.exifhelper.adjust_extensions")
def test_sort_media_parses_only_valid_lines(
    mock_adjust_extensions,
    mock_adjust_screenshots,
    mock_backfill_videos,
    mock_organize,
):
    # Simulate the list returned by exifhelper.organize() (i.e. output.split("\n")).
    # ExifTool wraps the target filename in single quotes; sort_media skips the
    # opening quote via [index+6:] and removes the closing quote via [:-1].
    mock_organize.return_value = [
        "",
        "no arrow line",
        "IMG_0001.JPG --> '2024/01/photo1.jpg'",
        "IMG_0002.JPG -->    ",
        "IMG_0003.JPG --> '2024/01/photo2.jpg'",
    ]

    result = sort_media("/root", "/import")

    assert result == ["2024/01/photo1.jpg", "2024/01/photo2.jpg"]
    mock_adjust_extensions.assert_called_once_with("/import", "/root")
    mock_adjust_screenshots.assert_called_once_with("/import", "/root")
    mock_backfill_videos.assert_called_once_with("/import", "/root")


def test_get_media_files_missing_or_invalid_import_dir(monkeypatch):
    monkeypatch.setattr("src.importrr.sort.os.path.exists", lambda _: False)
    assert get_media_files("/missing", 1) == []

    monkeypatch.setattr("src.importrr.sort.os.path.exists", lambda _: True)
    monkeypatch.setattr("src.importrr.sort.os.path.isdir", lambda _: False)
    assert get_media_files("/notadir", 1) == []


def test_get_media_files_filters_entries_and_handles_errors(monkeypatch):
    monkeypatch.setattr("src.importrr.sort.os.path.exists", lambda _: True)
    monkeypatch.setattr("src.importrr.sort.os.path.isdir", lambda p: p in ["/import", "/import/sub"])
    monkeypatch.setattr(
        "src.importrr.sort.os.listdir", lambda _: ["old.jpg", "new.jpg", "sub", "broken.jpg"]
    )
    monkeypatch.setattr(
        "src.importrr.sort.os.path.isfile",
        lambda p: p in ["/import/old.jpg", "/import/new.jpg", "/import/broken.jpg"],
    )

    def fake_last_accessed(path):
        if path.endswith("old.jpg"):
            return 10
        if path.endswith("new.jpg"):
            return 50
        raise PermissionError("denied")

    monkeypatch.setattr("src.importrr.sort.last_accessed", fake_last_accessed)
    assert get_media_files("/import", 20) == ["old.jpg"]


def test_get_media_files_handles_listdir_errors(monkeypatch):
    monkeypatch.setattr("src.importrr.sort.os.path.exists", lambda _: True)
    monkeypatch.setattr("src.importrr.sort.os.path.isdir", lambda _: True)
    monkeypatch.setattr(
        "src.importrr.sort.os.listdir",
        lambda _: (_ for _ in ()).throw(PermissionError("no access")),
    )
    assert get_media_files("/import", 1) == []


def test_make_work_dir_no_files_does_nothing(monkeypatch):
    called = {"mkdir": False}
    monkeypatch.setattr(
        "src.importrr.sort.os.mkdir", lambda _: called.__setitem__("mkdir", True)
    )
    make_work_dir("/cur", "/cur/work", [])
    assert called["mkdir"] is False


def test_make_work_dir_existing_dir_and_existing_target(tmp_path):
    cur_dir = tmp_path / "import"
    work_dir = cur_dir / "work"
    cur_dir.mkdir()
    work_dir.mkdir()
    (cur_dir / "a.jpg").write_text("a")
    (cur_dir / "b.jpg").write_text("b")
    (work_dir / "b.jpg").write_text("existing")

    make_work_dir(str(cur_dir), str(work_dir), ["a.jpg", "b.jpg"])

    assert not (cur_dir / "a.jpg").exists()
    assert (work_dir / "a.jpg").exists()
    assert (cur_dir / "b.jpg").exists()
    assert (work_dir / "b.jpg").exists()


def test_make_work_dir_existing_path_not_directory_raises(tmp_path):
    cur_dir = tmp_path / "import"
    cur_dir.mkdir()
    invalid_work_path = cur_dir / "work"
    invalid_work_path.write_text("not-a-dir")
    (cur_dir / "a.jpg").write_text("a")

    with pytest.raises(OSError, match="not a directory"):
        make_work_dir(str(cur_dir), str(invalid_work_path), ["a.jpg"])


def test_last_accessed_returns_max_of_timestamps(monkeypatch):
    stat = SimpleNamespace(st_ctime=1, st_mtime=5, st_atime=7)

    monkeypatch.setattr("src.importrr.sort.os.stat", lambda _: stat)
    assert last_accessed("/file") == 7


def test_sort_init_validates_directories(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    archive = tmp_path / "archive"
    archive.mkdir()

    Sort(str(root), str(archive))

    with pytest.raises(IOError):
        Sort(str(root / "missing"))
    with pytest.raises(IOError):
        Sort(str(root), str(archive / "missing"))


@patch("src.importrr.sort.get_media_files", return_value=[])
@patch("src.importrr.sort.make_work_dir")
def test_sort_launch_no_files(mock_make_work_dir, mock_get_media_files, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sorter = Sort(str(root))

    sorter.launch("images")
    mock_get_media_files.assert_called_once()
    mock_make_work_dir.assert_not_called()


@patch("src.importrr.sort.archive.copy")
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.sort_media", return_value=["sorted.jpg"])
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files", return_value=["in.jpg"])
@patch("src.importrr.sort.os.listdir", return_value=["leftover.jpg"])
@patch("src.importrr.sort.os.path.exists", return_value=True)
def test_sort_launch_with_remaining_files_skips_cleanup(
    mock_exists,
    mock_listdir,
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_cleanup,
    mock_archive_copy,
    tmp_path,
):
    root = tmp_path / "root"
    archive = tmp_path / "archive"
    root.mkdir()
    archive.mkdir()

    sorter = Sort(str(root), str(archive))
    sorter.launch("images")

    work_dir = mock_make_work_dir.call_args[0][1]
    prefix = os.path.basename(work_dir)
    mock_cleanup.assert_not_called()
    mock_archive_copy.assert_called_once_with(str(root), ["sorted.jpg"], str(archive), prefix)


@patch("src.importrr.sort.archive.copy")
@patch("src.importrr.sort.cleanup")
@patch("src.importrr.sort.sort_media", return_value=["sorted.jpg"])
@patch("src.importrr.sort.make_work_dir")
@patch("src.importrr.sort.get_media_files", return_value=["in.jpg"])
@patch("src.importrr.sort.os.listdir", return_value=[])
@patch("src.importrr.sort.os.path.exists", return_value=True)
def test_sort_launch_cleans_up_when_all_processed(
    mock_exists,
    mock_listdir,
    mock_get_media_files,
    mock_make_work_dir,
    mock_sort_media,
    mock_cleanup,
    mock_archive_copy,
    tmp_path,
):
    root = tmp_path / "root"
    archive = tmp_path / "archive"
    root.mkdir()
    archive.mkdir()

    sorter = Sort(str(root), str(archive))
    sorter.launch("images")

    work_dir = mock_make_work_dir.call_args[0][1]
    prefix = os.path.basename(work_dir)
    mock_cleanup.assert_called_once_with(work_dir)
    mock_archive_copy.assert_called_once_with(str(root), ["sorted.jpg"], str(archive), prefix)

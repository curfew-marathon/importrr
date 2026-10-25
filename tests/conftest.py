import pytest


@pytest.fixture
def mock_directories(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    return root_dir, archive_dir

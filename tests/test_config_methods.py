import pytest
from src.importrr.config import Config


@pytest.fixture
def dummy_config():
    config = Config.__new__(Config)
    config.album_root = "/album"
    config.archive_root = "/archive"
    config.data = [{"archive": "/archive/1", "serial": "S123"}]
    return config


def test_get_album(dummy_config):
    assert dummy_config.get_album() == "/album"


def test_get_archive(dummy_config):
    assert dummy_config.get_archive() == "/archive"


def test_get_data(dummy_config):
    assert len(dummy_config.get_data()) == 1


def test_get_serial_found(dummy_config):
    assert dummy_config.get_serial("/archive/1") == "S123"


def test_get_serial_not_found(dummy_config):
    with pytest.raises(KeyError):
        dummy_config.get_serial("/not_found")

import os
import unittest
from unittest.mock import patch

import pytest

from importrr.config import Config


class TestConfig(unittest.TestCase):
    def test_no_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config()

    @patch("importrr.config.os.path.exists", return_value=True)
    @patch("importrr.config.ConfigParser.sections", return_value=[])
    def test_missing_global_section(self, mock_sections, mock_exists):
        with self.assertRaisesRegex(
            ValueError, "Missing required 'global' section in configuration"
        ):
            Config()


def test_parses_valid_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        "[global]\n"
        "album_dir = /albums\n"
        "archive_dir = /archives\n"
        "\n"
        "[home]\n"
        "import_dir = personal, photos\n"
        "serial = ABC123\n"
        "\n"
        "[work]\n"
        "import_dir = corporate\n"
    )
    monkeypatch.setattr("importrr.config.CANDIDATES", [str(config_path)])

    config = Config()

    assert config.get_album() == "/albums"
    assert config.get_data() == [
        {
            "section": "home",
            "album": os.path.join("/albums", "home"),
            "archive": os.path.join("/archives", "home"),
            "import": ["personal", "photos"],
            "serial": "ABC123",
        },
        {
            "section": "work",
            "album": os.path.join("/albums", "work"),
            "archive": os.path.join("/archives", "work"),
            "import": ["corporate"],
            "serial": None,
        },
    ]


def test_missing_global_field(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[global]\nalbum_dir = /albums\n")
    monkeypatch.setattr("importrr.config.CANDIDATES", [str(config_path)])

    with pytest.raises(
        ValueError, match="Missing required configuration field in 'global' section"
    ):
        Config()


def test_missing_import_dir_field(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        "[global]\nalbum_dir = /albums\narchive_dir = /archives\n\n[home]\n"
    )
    monkeypatch.setattr("importrr.config.CANDIDATES", [str(config_path)])

    with pytest.raises(
        ValueError, match="Missing required 'import_dir' field in section 'home'"
    ):
        Config()


def test_empty_import_dir_field(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        "[global]\n"
        "album_dir = /albums\n"
        "archive_dir = /archives\n"
        "\n"
        "[home]\n"
        "import_dir = ,  ,\n"
    )
    monkeypatch.setattr("importrr.config.CANDIDATES", [str(config_path)])

    with pytest.raises(
        ValueError, match="Empty or invalid 'import_dir' field in section 'home'"
    ):
        Config()

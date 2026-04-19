import textwrap

import pytest

from src.importrr.config import Config


def test_config_init_valid_config(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        textwrap.dedent(
            """
            [global]
            album_dir = /albums
            archive_dir = /archives

            [home]
            import_dir = camera, phone ,  , sd
            serial = ABC123

            [work]
            import_dir = corp
            """
        ).strip()
    )

    monkeypatch.setattr("src.importrr.config.CANDIDATES", [str(config_file)])
    cfg = Config()

    assert cfg.get_album() == "/albums"
    assert cfg.get_data() == [
        {
            "album": "/albums/home",
            "archive": "/archives/home",
            "import": ["camera", "phone", "sd"],
            "serial": "ABC123",
        },
        {
            "album": "/albums/work",
            "archive": "/archives/work",
            "import": ["corp"],
            "serial": None,
        },
    ]


def test_config_init_missing_global_field(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        textwrap.dedent(
            """
            [global]
            archive_dir = /archives

            [home]
            import_dir = camera
            """
        ).strip()
    )

    monkeypatch.setattr("src.importrr.config.CANDIDATES", [str(config_file)])
    with pytest.raises(
        ValueError, match="Missing required configuration field in 'global' section"
    ):
        Config()


def test_config_init_missing_import_dir(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        textwrap.dedent(
            """
            [global]
            album_dir = /albums
            archive_dir = /archives

            [home]
            serial = CAM1
            """
        ).strip()
    )

    monkeypatch.setattr("src.importrr.config.CANDIDATES", [str(config_file)])
    with pytest.raises(
        ValueError, match="Missing required 'import_dir' field in section 'home'"
    ):
        Config()


def test_config_init_empty_import_dir(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        textwrap.dedent(
            """
            [global]
            album_dir = /albums
            archive_dir = /archives

            [home]
            import_dir = ,  ,    
            """
        ).strip()
    )

    monkeypatch.setattr("src.importrr.config.CANDIDATES", [str(config_file)])
    with pytest.raises(
        ValueError, match="Empty or invalid 'import_dir' field in section 'home'"
    ):
        Config()

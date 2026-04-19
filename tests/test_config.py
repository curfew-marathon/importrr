import unittest
from unittest.mock import patch, MagicMock
from src.importrr.config import Config


class TestConfig(unittest.TestCase):
    def test_no_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config()

    @patch("src.importrr.config.os.path.exists", return_value=True)
    @patch("src.importrr.config.ConfigParser.sections", return_value=[])
    def test_missing_global_section(self, mock_sections, mock_exists):
        with self.assertRaisesRegex(
            ValueError, "Missing required 'global' section in configuration"
        ):
            Config()

    @patch("src.importrr.config.os.path.exists", return_value=True)
    @patch("src.importrr.config.ConfigParser")
    def test_empty_import_dir(self, mock_config_parser_class, mock_exists):
        mock_parser = MagicMock()
        mock_config_parser_class.return_value = mock_parser

        mock_parser.sections.return_value = ["global", "camera"]

        def getitem_side_effect(key):
            if key == "global":
                return {"album_dir": "/album", "archive_dir": "/archive"}
            elif key == "camera":
                return {"import_dir": "   ,  "}
            raise KeyError(key)

        mock_parser.__getitem__.side_effect = getitem_side_effect

        with self.assertRaisesRegex(
            ValueError, "Empty or invalid 'import_dir' field in section 'camera'"
        ):
            Config()

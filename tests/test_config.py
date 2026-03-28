import unittest
from unittest.mock import patch
from src.importrr.config import Config

class TestConfig(unittest.TestCase):
    def test_no_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config()

    @patch('src.importrr.config.os.path.exists', return_value=True)
    @patch('src.importrr.config.ConfigParser.sections', return_value=[])
    def test_missing_global_section(self, mock_sections, mock_exists):
        with self.assertRaisesRegex(ValueError, "Missing required 'global' section in configuration"):
            Config()

import unittest
from unittest.mock import patch
import os
import tempfile
from src.importrr.config import Config

class TestConfig(unittest.TestCase):
    def test_no_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config()

    def test_get_serial(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("[global]\nalbum_dir = /albums\narchive_dir = /archives\n")
            f.write("[vacation]\nimport_dir = /import1\nserial = 12345\n")
            temp_name = f.name

        try:
            with patch('src.importrr.config.CANDIDATES', [temp_name]):
                config = Config()
                archive_path = os.path.join("/archives", "vacation")
                self.assertEqual(config.get_serial(archive_path), "12345")
        finally:
            os.remove(temp_name)

    def test_get_serial_not_found(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("[global]\nalbum_dir = /albums\narchive_dir = /archives\n")
            f.write("[vacation]\nimport_dir = /import1\nserial = 12345\n")
            temp_name = f.name

        try:
            with patch('src.importrr.config.CANDIDATES', [temp_name]):
                config = Config()
                with self.assertRaises(KeyError):
                    config.get_serial("/non/existent")
        finally:
            os.remove(temp_name)

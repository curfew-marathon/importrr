import unittest
from src.importrr.config import Config

class TestConfig(unittest.TestCase):
    def test_no_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config()

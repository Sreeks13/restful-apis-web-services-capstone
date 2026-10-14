import unittest

from settings import SETTINGS


class TestSettings(unittest.TestCase):
    def test_required_settings_exist(self):
        self.assertTrue(SETTINGS["base_url"].startswith("http"))
        self.assertGreater(SETTINGS["timeout"], 0)
        self.assertTrue(SETTINGS["username"])
        self.assertTrue(SETTINGS["password"])
        self.assertTrue(SETTINGS["client_name"])


if __name__ == "__main__":
    unittest.main()
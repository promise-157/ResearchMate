import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from services.runtime_info import RUNTIME_INFO_ENV, get_runtime_info


class RuntimeInfoTests(unittest.TestCase):
    def test_source_mode_has_explicit_manual_uninstall_boundary(self):
        with patch.dict(os.environ, {}, clear=True):
            result = get_runtime_info()
        self.assertEqual(result["platform"], "source")
        self.assertFalse(result["uninstall"]["available"])
        self.assertTrue(any(entry["ownership"] == "user_data" for entry in result["paths"]))

    def test_valid_desktop_payload_round_trips_without_touching_storage(self):
        payload = {
            "schema_version": 1,
            "platform": "windows_wsl",
            "platform_label": "Fixture desktop",
            "paths": [{"label": "Host", "path": "D:\\Fixture", "ownership": "application"}],
            "uninstall": {
                "available": True,
                "summary": "Fixture uninstall",
                "guide_path": "D:\\Fixture\\uninstall.txt",
            },
        }
        with patch.dict(os.environ, {RUNTIME_INFO_ENV: json.dumps(payload)}, clear=True):
            self.assertEqual(get_runtime_info(), payload)

    def test_invalid_desktop_payload_falls_back_to_source_mode(self):
        with patch.dict(os.environ, {RUNTIME_INFO_ENV: '{"schema_version":2}'}, clear=True):
            self.assertEqual(get_runtime_info()["platform"], "source")


if __name__ == "__main__":
    unittest.main()

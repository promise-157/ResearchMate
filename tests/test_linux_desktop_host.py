import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock


HOST_PATH = (
    Path(__file__).resolve().parents[1]
    / "packaging/linux/host/researchmate_linux_host.py"
)
SPEC = importlib.util.spec_from_file_location("researchmate_linux_host", HOST_PATH)
HOST = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(HOST)
SETUP_PATH = Path(__file__).resolve().parents[1] / "packaging/linux/setup_researchmate.py"
SETUP_SPEC = importlib.util.spec_from_file_location("researchmate_linux_setup", SETUP_PATH)
SETUP = importlib.util.module_from_spec(SETUP_SPEC)
assert SETUP_SPEC and SETUP_SPEC.loader
SETUP_SPEC.loader.exec_module(SETUP)


class LinuxDesktopHostTests(unittest.TestCase):
    def test_config_and_supervisor_command_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "desktop-config.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "project_path": "/fixture/project with spaces",
                "conda_executable": "/fixture/conda",
                "conda_environment": "researchmate-test",
                "port": 8124,
            }), encoding="utf-8")
            config = HOST.load_config(path)
            command = HOST.supervisor_command(config, "a" * 32)
            self.assertEqual(command[0], "/fixture/conda")
            self.assertIn("researchmate-test", command)
            self.assertIn("src/backend/desktop_runtime.py", command)
            self.assertEqual(command[-1], "8124")

    def test_invalid_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "desktop-config.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "project_path": "relative",
                "conda_executable": "/fixture/conda",
                "conda_environment": "bad;name",
                "port": 8000,
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                HOST.load_config(path)

    def test_fixture_supervisor_path_is_an_argument_not_shell_text(self):
        config = {
            "conda_executable": "/fixture/conda",
            "conda_environment": "fixture",
            "port": 8999,
        }
        command = HOST.supervisor_command(
            config, "b" * 32, "tests/fixtures/desktop_runtime_harness.py"
        )
        self.assertIn("tests/fixtures/desktop_runtime_harness.py", command)
        self.assertNotIn("sh", command)

    def test_desktop_exec_quotes_paths_with_spaces(self):
        self.assertEqual(
            SETUP.desktop_exec(Path("/home/example user/.local/bin/researchmate")),
            '"/home/example user/.local/bin/researchmate"',
        )

    def test_second_instance_activates_primary_over_private_socket(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": directory}
        ):
            activated = threading.Event()
            try:
                primary = HOST.SingleInstance(activated.set)
            except PermissionError as error:
                self.skipTest(f"sandbox forbids Unix sockets: {error}")
            self.assertTrue(primary.primary)
            secondary = HOST.SingleInstance(lambda: None)
            try:
                self.assertFalse(secondary.primary)
                self.assertTrue(secondary.activate_existing())
                self.assertTrue(activated.wait(2))
                self.assertEqual(primary.socket_path.stat().st_mode & 0o777, 0o600)
            finally:
                secondary.close()
                primary.close()


if __name__ == "__main__":
    unittest.main()

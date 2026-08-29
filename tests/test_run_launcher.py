import errno
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

import run as launcher


class PortLauncherTests(unittest.TestCase):
    def tearDown(self):
        launcher._vite_process = None

    def test_pid_parser_accepts_only_complete_numeric_lines(self):
        output = "  123\nnoise 456\n789\n"
        self.assertEqual(launcher._parse_pids(output), {123, 789} - {os.getpid()})

    def test_permission_error_is_not_reported_as_port_occupation(self):
        fake_socket = MagicMock()
        fake_socket.__enter__.return_value.bind.side_effect = OSError(
            errno.EACCES, "fixture denied"
        )
        with patch("run.socket.socket", return_value=fake_socket):
            with self.assertRaisesRegex(launcher.PortPermissionError, "无权检查"):
                launcher.check_port("127.0.0.1", 8000)

    def test_port_check_matches_server_restart_reuse_semantics(self):
        fake_socket = MagicMock()
        with patch("run.socket.socket", return_value=fake_socket):
            self.assertTrue(launcher.check_port("127.0.0.1", 8000))
        fake_socket.__enter__.return_value.setsockopt.assert_called_once_with(
            launcher.socket.SOL_SOCKET,
            launcher.socket.SO_REUSEADDR,
            1,
        )

    def test_linux_listener_is_terminated_and_verified(self):
        with patch("run._linux_listener_pids", return_value={123}), \
             patch("run._terminate_linux_pids", return_value=[]), \
             patch("run._wait_for_port", return_value=True), \
             patch("run._windows_listener_pids") as windows:
            cleared, detail = launcher.kill_port("127.0.0.1", 8000)
        self.assertTrue(cleared)
        self.assertIn("Linux", detail)
        windows.assert_not_called()

    def test_wsl_can_fall_back_to_windows_listener(self):
        with patch("run._linux_listener_pids", return_value=set()), \
             patch("run._windows_listener_pids", return_value={456}), \
             patch("run._terminate_windows_pids", return_value=[]), \
             patch("run._wait_for_port", return_value=True):
            cleared, detail = launcher.kill_port("127.0.0.1", 8000)
        self.assertTrue(cleared)
        self.assertIn("Windows", detail)

    def test_failure_reports_missing_listener_instead_of_suggesting_pkill(self):
        with patch("run._linux_listener_pids", return_value=set()), \
             patch("run._windows_listener_pids", return_value=set()):
            cleared, detail = launcher.kill_port("127.0.0.1", 8000)
        self.assertFalse(cleared)
        self.assertIn("未找到", detail)

    def test_listener_that_restarts_is_reported(self):
        with patch("run._linux_listener_pids", return_value={123}), \
             patch("run._terminate_linux_pids", return_value=[]), \
             patch("run._force_terminate_linux_pids", return_value=[]), \
             patch("run._windows_listener_pids", return_value=set()), \
             patch("run._wait_for_port", return_value=False):
            cleared, detail = launcher.kill_port("127.0.0.1", 8000)
        self.assertFalse(cleared)
        self.assertIn("自动重启", detail)

    def test_vite_waits_until_port_becomes_occupied(self):
        process = MagicMock()
        process.poll.return_value = None
        with patch("run.subprocess.Popen", return_value=process), \
             patch("run.check_port", side_effect=[True, False]) as check, \
             patch("run.time.sleep"):
            launcher.start_vite()
        self.assertEqual(check.call_count, 2)


if __name__ == "__main__":
    unittest.main()

import io
import json
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

import desktop_runtime


INSTANCE_ID = "0123456789abcdef0123456789abcdef"


class FakeProcess:
    def __init__(self, *, timeout_once=False):
        self.pid = 4321
        self.running = True
        self.timeout_once = timeout_once
        self.wait_calls = 0

    def poll(self):
        return None if self.running else 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.timeout_once:
            self.timeout_once = False
            raise subprocess.TimeoutExpired("fixture", timeout)
        self.running = False
        return 0


class DesktopRuntimeTests(unittest.TestCase):
    def make_supervisor(self, *, stdin_text="", process=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        fake_process = process or FakeProcess()
        return (
            desktop_runtime.DesktopRuntimeSupervisor(
                instance_id=INSTANCE_ID,
                stdin=io.StringIO(stdin_text),
                stdout=stdout,
                stderr=stderr,
                process_factory=MagicMock(return_value=fake_process),
                backend_command=["fixture-backend"],
                graceful_timeout=0.01,
            ),
            stdout,
            fake_process,
        )

    def events(self, output):
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_rejects_nonlocal_host_and_invalid_instance(self):
        with self.assertRaisesRegex(desktop_runtime.DesktopRuntimeError, "实例标识"):
            desktop_runtime.DesktopRuntimeSupervisor(instance_id="bad")
        with self.assertRaisesRegex(desktop_runtime.DesktopRuntimeError, "127.0.0.1"):
            desktop_runtime.DesktopRuntimeSupervisor(
                instance_id=INSTANCE_ID, host="0.0.0.0"
            )

    def test_port_conflict_fails_without_starting_or_killing_any_process(self):
        supervisor, output, _ = self.make_supervisor()
        with patch("desktop_runtime.port_is_available", return_value=False), \
             patch("desktop_runtime.os.killpg") as killpg:
            result = supervisor.run()
        self.assertEqual(result, 1)
        supervisor.process_factory.assert_not_called()
        killpg.assert_not_called()
        self.assertEqual(self.events(output)[-1]["event"], "startup_failed")
        self.assertIn("不会复用或终止", self.events(output)[-1]["message"])

    def test_host_shutdown_stops_exact_process_group(self):
        process = FakeProcess()
        supervisor, output, _ = self.make_supervisor(
            stdin_text=json.dumps(
                {"command": "shutdown", "instance_id": INSTANCE_ID}
            ) + "\n",
            process=process,
        )
        with patch("desktop_runtime.port_is_available", return_value=True), \
             patch("desktop_runtime.os.getpgid", return_value=4321), \
             patch("desktop_runtime.os.killpg") as killpg:
            result = supervisor.run()
        self.assertEqual(result, 0)
        killpg.assert_called_once_with(4321, signal.SIGTERM)
        event_names = [event["event"] for event in self.events(output)]
        self.assertIn("shutdown_started", event_names)
        self.assertEqual(event_names[-1], "backend_exited")

    def test_stdin_eof_requests_shutdown(self):
        process = FakeProcess()
        supervisor, output, _ = self.make_supervisor(process=process)
        with patch("desktop_runtime.port_is_available", return_value=True), \
             patch("desktop_runtime.os.getpgid", return_value=4321), \
             patch("desktop_runtime.os.killpg") as killpg:
            result = supervisor.run()
        self.assertEqual(result, 0)
        killpg.assert_called_once_with(4321, signal.SIGTERM)
        shutdown = next(
            event for event in self.events(output) if event["event"] == "shutdown_started"
        )
        self.assertEqual(shutdown["reason"], "host_eof")

    def test_mismatched_instance_is_ignored_until_eof(self):
        process = FakeProcess()
        frames = (
            json.dumps({"command": "shutdown", "instance_id": "f" * 32}) + "\n"
        )
        supervisor, output, _ = self.make_supervisor(stdin_text=frames, process=process)
        with patch("desktop_runtime.port_is_available", return_value=True), \
             patch("desktop_runtime.os.getpgid", return_value=4321), \
             patch("desktop_runtime.os.killpg") as killpg:
            result = supervisor.run()
        self.assertEqual(result, 0)
        killpg.assert_called_once_with(4321, signal.SIGTERM)
        warnings = [
            event for event in self.events(output) if event["event"] == "control_warning"
        ]
        self.assertIn("不匹配", warnings[0]["message"])

    def test_timeout_escalates_only_the_owned_process_group(self):
        process = FakeProcess(timeout_once=True)
        supervisor, output, _ = self.make_supervisor(process=process)
        with patch("desktop_runtime.port_is_available", return_value=True), \
             patch("desktop_runtime.os.getpgid", return_value=4321), \
             patch("desktop_runtime.os.killpg") as killpg:
            result = supervisor.run()
        self.assertEqual(result, 0)
        self.assertEqual(
            killpg.call_args_list,
            [
                unittest.mock.call(4321, signal.SIGTERM),
                unittest.mock.call(4321, signal.SIGKILL),
            ],
        )
        forced = [event for event in self.events(output) if event["event"] == "shutdown_forced"]
        self.assertEqual(len(forced), 1)

    def test_backend_logs_are_separate_from_protocol_stdout(self):
        process = MagicMock()
        process.pid = 4321
        supervisor, output, _ = self.make_supervisor(process=process)
        with patch("desktop_runtime.port_is_available", return_value=True), \
             patch("desktop_runtime.os.getpgid", return_value=4321):
            supervisor.start_backend()
        kwargs = supervisor.process_factory.call_args.kwargs
        self.assertIs(kwargs["stdout"], supervisor.stderr)
        self.assertIs(kwargs["stderr"], supervisor.stderr)
        self.assertEqual(self.events(output)[0]["event"], "backend_spawned")


if __name__ == "__main__":
    unittest.main()

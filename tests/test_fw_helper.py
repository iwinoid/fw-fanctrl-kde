"""Unit tests for scripts/fw_helper.py.

Run from the repository root:

    python3 -m unittest discover -s tests -v
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fw_helper


class RunJsonCommandTest(unittest.TestCase):
    def test_success(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               return_value=b'{"status": "success", "x": 1}'):
            result = fw_helper._run_json_command(["fw-fanctrl", "foo"])
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], {"status": "success", "x": 1})

    def test_status_not_success(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               return_value=b'{"status": "error", "reason": "boom"}'):
            result = fw_helper._run_json_command(["fw-fanctrl", "foo"])
        self.assertFalse(result["success"])
        self.assertIn("boom", result["message"])

    def test_not_found(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               side_effect=FileNotFoundError):
            result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertEqual(result, {"success": False, "message": "fw-fanctrl not found"})

    def test_timeout(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertIn("timed out", result["message"])

    def test_called_process_error(self):
        err = subprocess.CalledProcessError(1, "cmd", output=b"some stderr")
        with mock.patch.object(fw_helper.subprocess, "check_output", side_effect=err):
            result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("some stderr", result["message"])

    def test_invalid_json(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               return_value=b"not json"):
            result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])

    def test_message_clipped(self):
        long_output = "x" * 1000
        err = subprocess.CalledProcessError(1, "cmd", output=long_output.encode())
        with mock.patch.object(fw_helper.subprocess, "check_output", side_effect=err):
            result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertLessEqual(len(result["message"]), 400 + 1)  # one ellipsis char


class GetStatusTest(unittest.TestCase):
    def test_online(self):
        payload = json.dumps({
            "status": "success",
            "strategy": "Deaf",
            "temperature": 42.5,
            "speed": 63,
            "active": True,
            "movingAverageTemperature": 41.0,
            "effectiveTemperature": 41.5,
            "configuration": {"data": {"strategies": {"A": {}, "B": {}}}},
        }).encode()
        with mock.patch.object(fw_helper.subprocess, "check_output", return_value=payload):
            status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["currentStrategy"], "Deaf")
        self.assertEqual(status["temperature"], 42.5)
        self.assertEqual(status["fanSpeed"], 63)
        self.assertEqual(status["strategies"], ["A", "B"])

    def test_online_fallback_to_strategies(self):
        payload = json.dumps({
            "status": "success",
            "strategy": "Deaf",
            "configuration": {"data": {}},  # no strategies inside
        }).encode()
        with mock.patch.object(fw_helper.subprocess, "check_output", return_value=payload):
            with mock.patch.object(fw_helper, "get_strategies",
                                   return_value={"strategies": ["A", "B"]}):
                status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["strategies"], ["A", "B"])

    def test_error_status(self):
        payload = json.dumps({"status": "error", "reason": "broken"}).encode()
        with mock.patch.object(fw_helper.subprocess, "check_output", return_value=payload):
            status = fw_helper.get_status()
        self.assertFalse(status["online"])
        self.assertIn("broken", status["error"])

    def test_not_found(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               side_effect=FileNotFoundError):
            status = fw_helper.get_status()
        self.assertFalse(status["online"])
        self.assertEqual(status["error"], "fw-fanctrl not found")

    def test_timeout_and_invalid_json(self):
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               side_effect=subprocess.TimeoutExpired("cmd", 10)):
            self.assertFalse(fw_helper.get_status()["online"])
        with mock.patch.object(fw_helper.subprocess, "check_output",
                               return_value=b"garbage"):
            self.assertFalse(fw_helper.get_status()["online"])


class SimpleCommandsTest(unittest.TestCase):
    def test_get_strategies(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": True,
                                             "message": {"strategies": ["A"]}}):
            self.assertEqual(fw_helper.get_strategies(), {"strategies": ["A"]})

    def test_set_strategy_success(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": True,
                                             "message": {"strategy": "Deaf"}}):
            result = fw_helper.set_strategy("Deaf")
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Deaf")

    def test_set_strategy_failure(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": False, "message": "nope"}):
            self.assertFalse(fw_helper.set_strategy("X")["success"])

    def test_reload_pause_resume(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": True, "message": {}}):
            self.assertEqual(fw_helper.do_reload()["message"], "Reloaded")
            self.assertEqual(fw_helper.do_pause()["message"], "Paused")
            self.assertEqual(fw_helper.do_resume()["message"], "Resumed")


class ReadConfigTest(unittest.TestCase):
    def test_read_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            schema = os.path.join(tmp, "config.schema.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"defaultStrategy": "A", "strategies": {"A": {}}}, f)
            with open(schema, "w", encoding="utf-8") as f:
                json.dump({"type": "object"}, f)
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg), \
                 mock.patch.object(fw_helper, "SCHEMA_PATH", schema):
                data = fw_helper.read_config()
        self.assertIn("config", data)
        self.assertEqual(data["config"]["defaultStrategy"], "A")
        self.assertEqual(data["schema"], {"type": "object"})

    def test_missing_file(self):
        with mock.patch.object(fw_helper, "CONFIG_PATH", "/nonexistent/config.json"):
            data = fw_helper.read_config()
        self.assertIn("error", data)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("{not json")
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg):
                data = fw_helper.read_config()
        self.assertIn("error", data)

    def test_permission_error(self):
        with mock.patch("builtins.open", side_effect=PermissionError), \
             mock.patch.object(fw_helper.os.path, "exists", return_value=True), \
             mock.patch.object(fw_helper, "CONFIG_PATH", "/some/config.json"):
            data = fw_helper.read_config()
        self.assertIn("Permission", data["error"])


class SaveConfigTest(unittest.TestCase):
    def test_invalid_json(self):
        result = fw_helper.save_config("{oops")
        self.assertFalse(result["success"])
        self.assertIn("Invalid JSON", result["message"])

    def test_valid_json_forwards_to_set_config(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": True, "message": {}}) as m:
            result = fw_helper.save_config('{"a": 1}')
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Configuration saved successfully")
        args = m.call_args[0][0]
        self.assertEqual(args[0], "fw-fanctrl")
        self.assertEqual(args[-1], '{"a": 1}')


class SendNotificationTest(unittest.TestCase):
    def test_success(self):
        with mock.patch.object(fw_helper.subprocess, "run") as m:
            result = fw_helper.send_notification("t", "b")
        self.assertTrue(result["success"])
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0][0], "notify-send")

    def test_not_found(self):
        with mock.patch.object(fw_helper.subprocess, "run",
                               side_effect=FileNotFoundError):
            result = fw_helper.send_notification("t", "b")
        self.assertFalse(result["success"])
        self.assertIn("notify-send", result["message"])

    def test_timeout(self):
        with mock.patch.object(fw_helper.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("x", 5)):
            result = fw_helper.send_notification("t", "b")
        self.assertFalse(result["success"])


class MainDispatchTest(unittest.TestCase):
    def run_main(self, args):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["fw_helper.py"] + args), \
             mock.patch("sys.stdout", buf):
            fw_helper.main()
        return json.loads(buf.getvalue())

    def test_no_command(self):
        with self.assertRaises(SystemExit):
            self.run_main([])

    def test_unknown_command(self):
        with self.assertRaises(SystemExit):
            self.run_main(["frobnicate"])

    def test_get_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"defaultStrategy": "A"}, f)
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg):
                out = self.run_main(["get_config"])
        self.assertIn("config", out)

    def test_save_config_missing_arg(self):
        with self.assertRaises(SystemExit):
            self.run_main(["save_config"])

    def test_notify_missing_arg(self):
        with self.assertRaises(SystemExit):
            self.run_main(["notify", "title-only"])

    def test_notify_dispatch(self):
        with mock.patch.object(fw_helper, "send_notification",
                               return_value={"success": True, "message": "ok"}):
            out = self.run_main(["notify", "title", "body words"])
        self.assertTrue(out["success"])

    def test_set_strategy_joins_name(self):
        with mock.patch.object(fw_helper, "set_strategy",
                               return_value={"success": True, "message": "A"}) as m:
            out = self.run_main(["set_strategy", "A", "B"])
            m.assert_called_once_with("A B")
        self.assertTrue(out["success"])


if __name__ == "__main__":
    unittest.main()

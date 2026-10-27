"""Unit and integration tests for scripts/fw_helper.py.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Two kinds of tests:

* unit tests patch ``fw_helper.subprocess`` with a stand-in object, so the
  stdlib ``subprocess`` module itself is never mocked and parallel tests cannot
  pollute each other;
* integration tests execute the real helper script in a subprocess with a
  ``fw-fanctrl`` PATH shim, which covers the full CLI -> JSON contract without
  ever touching the real fw-fanctrl service.

Shim scripts are created under ``<repo>/tmp/`` and removed in cleanup.
"""

import glob
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER_PATH = os.path.join(PROJECT_ROOT, "scripts", "fw_helper.py")
TMP_ROOT = os.path.join(PROJECT_ROOT, "tmp")

sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
import fw_helper  # noqa: E402


# ─── Shared test helpers ──────────────────────────────────────────

def make_fake_subprocess(check_output=None, run=None):
    """Stand-in for the ``subprocess`` module bound to fw_helper only.

    Only that module attribute is patched (not the stdlib module object), so
    mocking here cannot affect other tests or threads.
    """
    fake = types.SimpleNamespace(
        PIPE=subprocess.PIPE,
        STDOUT=subprocess.STDOUT,
        DEVNULL=subprocess.DEVNULL,
        CalledProcessError=subprocess.CalledProcessError,
        TimeoutExpired=subprocess.TimeoutExpired,
    )
    fake.check_output = check_output or mock.Mock(
        side_effect=AssertionError("subprocess.check_output was not expected")
    )
    fake.run = run or mock.Mock(
        side_effect=AssertionError("subprocess.run was not expected")
    )
    return fake


class SubprocessPatchMixin:
    def patch_subprocess(self, **kwargs):
        fake = make_fake_subprocess(**kwargs)
        patcher = mock.patch.object(fw_helper, "subprocess", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def capture_check_output(self, results):
        """Patch check_output, returning the list of (args, kwargs) calls.

        ``results`` is a list of bytes to return or exceptions to raise, one
        entry per call.
        """
        calls = []
        pending = list(results)

        def fake_check_output(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            if not pending:
                raise AssertionError("unexpected extra subprocess.check_output call")
            item = pending.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        self.patch_subprocess(check_output=fake_check_output)
        return calls

    def run_json_payload(self, payload):
        return json.dumps(payload).encode()


# ─── _run_json_command ────────────────────────────────────────────

class RunJsonCommandTest(SubprocessPatchMixin, unittest.TestCase):
    def test_success(self):
        self.capture_check_output([b'{"status": "success", "x": 1}'])
        result = fw_helper._run_json_command(["fw-fanctrl", "foo"])
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], {"status": "success", "x": 1})

    def test_status_not_success(self):
        self.capture_check_output([b'{"status": "error", "reason": "boom"}'])
        result = fw_helper._run_json_command(["fw-fanctrl", "foo"])
        self.assertFalse(result["success"])
        self.assertIn("boom", result["message"])

    def test_not_found(self):
        self.capture_check_output([FileNotFoundError()])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertEqual(result, {"success": False, "message": "fw-fanctrl not found"})

    def test_timeout(self):
        self.capture_check_output([subprocess.TimeoutExpired("cmd", 10)])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertIn("timed out", result["message"])
        self.assertIn("10s", result["message"])

    def test_called_process_error_plain_stderr(self):
        err = subprocess.CalledProcessError(1, "cmd", output=b"", stderr=b"some stderr")
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("some stderr", result["message"])

    def test_called_process_error_plain_stdout(self):
        err = subprocess.CalledProcessError(1, "cmd", output=b"some stdout")
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertIn("some stdout", result["message"])

    def test_called_process_error_without_output(self):
        err = subprocess.CalledProcessError(7, "cmd")
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertIn("status 7", result["message"])

    def test_message_clipped(self):
        long_output = "x" * 1000
        err = subprocess.CalledProcessError(1, "cmd", output=long_output.encode())
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertLessEqual(len(result["message"]), 400 + 1)  # one ellipsis char

    def test_oserror(self):
        self.capture_check_output([OSError("cannot execute")])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("cannot execute", result["message"])

    def test_invalid_json(self):
        self.capture_check_output([b"not json"])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("not json", result["message"])

    def test_empty_output(self):
        self.capture_check_output([b""])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("no output", result["message"])

    def test_non_object_json(self):
        for payload, kind in ((b"[]", "list"), (b"null", "null"),
                              (b"42", "int"), (b'"text"', "str")):
            with self.subTest(payload=payload):
                self.capture_check_output([payload])
                result = fw_helper._run_json_command(["fw-fanctrl"])
                self.assertFalse(result["success"])
                self.assertIn("unexpected JSON type", result["message"])
                self.assertIn(kind, result["message"])

    def test_warning_line_around_json_is_tolerated(self):
        # A wrapper printing a warning on stdout must not break JSON parsing.
        self.capture_check_output(
            [b'[Warning] > deprecated command\n{"status": "success", "speed": 41}']
        )
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertTrue(result["success"])
        self.assertEqual(result["message"]["speed"], 41)

    def test_stderr_is_not_parsed_as_json(self):
        self.capture_check_output([b"warning on stderr\n"])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertIn("warning on stderr", result["message"])


class CalledProcessErrorJsonTest(SubprocessPatchMixin, unittest.TestCase):
    def test_reason_extracted_from_stderr(self):
        err = subprocess.CalledProcessError(
            1, "cmd", output=b"",
            stderr=b'{"status": "error", "reason": "[Errno 2] No such file or directory"}',
        )
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "[Errno 2] No such file or directory")
        self.assertNotIn('"status"', result["message"])

    def test_reason_extracted_from_stdout(self):
        err = subprocess.CalledProcessError(
            1, "cmd",
            output=b'{"status": "error", "reason": "service exploded"}',
            stderr=b"",
        )
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertEqual(result["message"], "service exploded")

    def test_plain_stderr_wins_when_no_error_json(self):
        err = subprocess.CalledProcessError(
            1, "cmd",
            output=b'{"status": "success"}',
            stderr=b"Traceback: real failure",
        )
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertIn("real failure", result["message"])

    def test_reason_clipped(self):
        reason = "r" * 1000
        err = subprocess.CalledProcessError(
            1, "cmd",
            stderr=json.dumps({"status": "error", "reason": reason}).encode(),
        )
        self.capture_check_output([err])
        result = fw_helper._run_json_command(["fw-fanctrl"])
        self.assertLessEqual(len(result["message"]), 401)


# ─── subprocess call contract ────────────────────────────────────

class SubprocessContractTest(SubprocessPatchMixin, unittest.TestCase):
    def test_check_output_uses_stderr_pipe_and_timeout(self):
        calls = self.capture_check_output([b'{"status": "success"}'])
        fw_helper._run_json_command(["fw-fanctrl", "foo"])
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args, ["fw-fanctrl", "foo"])
        self.assertEqual(kwargs["timeout"], fw_helper.CLI_TIMEOUT)
        self.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.assertNotEqual(kwargs["stderr"], subprocess.STDOUT)

    def test_get_status_check_output_contract(self):
        calls = self.capture_check_output([
            self.run_json_payload({
                "status": "success",
                "configuration": {"data": {"strategies": {"A": {}}}},
            })
        ])
        fw_helper.get_status()
        self.assertEqual(calls[0][1]["timeout"], fw_helper.CLI_TIMEOUT)
        self.assertEqual(calls[0][1]["stderr"], subprocess.PIPE)

    def test_save_config_check_output_contract(self):
        calls = self.capture_check_output([b'{"status": "success"}'])
        result = fw_helper.save_config('{"a": 1}')
        self.assertTrue(result["success"])
        self.assertEqual(calls[0][1]["timeout"], fw_helper.SAVE_TIMEOUT)
        self.assertEqual(calls[0][1]["stderr"], subprocess.PIPE)
        self.assertEqual(calls[0][0][0], "fw-fanctrl")

    def test_fallback_uses_short_timeout(self):
        calls = self.capture_check_output([
            self.run_json_payload({"status": "success", "configuration": {"data": {}}}),
            self.run_json_payload({"status": "success", "strategies": ["A"]}),
        ])
        status = fw_helper.get_status()
        self.assertEqual(status["strategies"], ["A"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["timeout"], fw_helper.CLI_TIMEOUT)
        self.assertEqual(calls[1][1]["timeout"], fw_helper.FALLBACK_TIMEOUT)
        self.assertLessEqual(fw_helper.FALLBACK_TIMEOUT, 3)
        # The fallback only queries `print list`, never a write command.
        self.assertEqual(calls[1][0], ["fw-fanctrl", "--output-format", "JSON", "print", "list"])

    def test_notify_check_output_contract(self):
        completed = types.SimpleNamespace(returncode=0, stderr=b"")
        self.patch_subprocess(run=mock.Mock(return_value=completed))
        fw_helper.send_notification("t", "b")
        kwargs = fw_helper.subprocess.run.call_args[1]
        self.assertEqual(kwargs["timeout"], fw_helper.NOTIFY_TIMEOUT)
        self.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["check"], False)


# ─── get_status ───────────────────────────────────────────────────

ONLINE_PAYLOAD = {
    "status": "success",
    "strategy": "Deaf",
    "temperature": 42.5,
    "speed": 63,
    "active": True,
    "movingAverageTemperature": 41.0,
    "effectiveTemperature": 41.5,
    "configuration": {"data": {"strategies": {"A": {}, "B": {}}}},
}


class GetStatusTest(SubprocessPatchMixin, unittest.TestCase):
    def test_online(self):
        self.capture_check_output([self.run_json_payload(ONLINE_PAYLOAD)])
        status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["currentStrategy"], "Deaf")
        self.assertEqual(status["temperature"], 42.5)
        self.assertEqual(status["fanSpeed"], 63)
        self.assertEqual(status["active"], True)
        self.assertEqual(status["strategies"], ["A", "B"])

    def test_online_fallback_to_strategies(self):
        calls = self.capture_check_output([
            self.run_json_payload({
                "status": "success",
                "strategy": "Deaf",
                "configuration": {"data": {}},
            }),
            self.run_json_payload({"status": "success", "strategies": ["A", "B"]}),
        ])
        status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["strategies"], ["A", "B"])
        self.assertEqual(calls[1][1]["timeout"], fw_helper.FALLBACK_TIMEOUT)

    def test_fallback_returns_no_strategies_on_failure(self):
        self.capture_check_output([
            self.run_json_payload({"status": "success", "configuration": {"data": {}}}),
            b"not json",
        ])
        status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["strategies"], [])

    def test_error_status(self):
        self.capture_check_output([b'{"status": "error", "reason": "broken"}'])
        status = fw_helper.get_status()
        self.assertFalse(status["online"])
        self.assertIn("broken", status["error"])

    def test_not_found(self):
        self.capture_check_output([FileNotFoundError()])
        status = fw_helper.get_status()
        self.assertFalse(status["online"])
        self.assertEqual(status["error"], "fw-fanctrl not found")

    def test_timeout_and_invalid_json(self):
        self.capture_check_output([subprocess.TimeoutExpired("cmd", 10)])
        self.assertFalse(fw_helper.get_status()["online"])
        self.capture_check_output([b"garbage"])
        self.assertFalse(fw_helper.get_status()["online"])

    def test_non_object_json(self):
        for payload in (b"[]", b"null", b"42"):
            with self.subTest(payload=payload):
                self.capture_check_output([payload])
                status = fw_helper.get_status()
                self.assertFalse(status["online"])
                self.assertIn("unexpected JSON type", status["error"])

    def test_missing_fields_are_null_not_garbage(self):
        from unittest import mock as _mock
        payload = self.run_json_payload({
            "status": "success",
            # no strategy/temperature/speed/movingAverageTemperature/effectiveTemperature
            # no configuration at all
        })
        self.capture_check_output([payload])
        with _mock.patch.object(fw_helper, "get_strategies",
                                return_value={"strategies": []}):
            status = fw_helper.get_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["currentStrategy"], "")
        self.assertIsNone(status["temperature"])
        self.assertIsNone(status["fanSpeed"])
        self.assertIsNone(status["movingAverageTemperature"])
        self.assertIsNone(status["effectiveTemperature"])
        self.assertIs(status["active"], False)
        self.assertEqual(status["strategies"], [])

    def test_null_fields_are_null(self):
        payload = self.run_json_payload({
            "status": "success",
            "strategy": None,
            "temperature": None,
            "speed": None,
            "active": None,
            "movingAverageTemperature": None,
            "effectiveTemperature": None,
            "configuration": {"data": {"strategies": {"A": {}}}},
        })
        self.capture_check_output([payload])
        status = fw_helper.get_status()
        self.assertEqual(status["currentStrategy"], "")
        self.assertIsNone(status["temperature"])
        self.assertIsNone(status["fanSpeed"])
        self.assertIsNone(status["movingAverageTemperature"])
        self.assertIsNone(status["effectiveTemperature"])
        self.assertIs(status["active"], False)

    def test_non_numeric_and_non_bool_values_are_normalized(self):
        payload = self.run_json_payload({
            "status": "success",
            "strategy": 7,
            "temperature": "52.5",
            "speed": "41",
            "active": "yes",
            "movingAverageTemperature": True,
            "effectiveTemperature": 41.7,
            "configuration": {"data": {"strategies": {"A": {}}}},
        })
        self.capture_check_output([payload])
        status = fw_helper.get_status()
        self.assertEqual(status["currentStrategy"], "")
        self.assertIsNone(status["temperature"])
        self.assertIsNone(status["fanSpeed"])
        self.assertIs(status["active"], False)
        self.assertIsNone(status["movingAverageTemperature"])
        self.assertEqual(status["effectiveTemperature"], 41.7)

    def test_non_finite_numbers_are_null(self):
        payload = (b'{"status": "success", "temperature": 1e999, '
                   b'"speed": 41, "configuration": {"data": {"strategies": {"A": {}}}}}')
        self.capture_check_output([payload])
        status = fw_helper.get_status()
        self.assertIsNone(status["temperature"])
        self.assertEqual(status["fanSpeed"], 41)

    def test_fan_speed_is_int(self):
        payload = self.run_json_payload({
            "status": "success",
            "speed": 41.7,
            "configuration": {"data": {"strategies": {"A": {}}}},
        })
        self.capture_check_output([payload])
        status = fw_helper.get_status()
        self.assertEqual(status["fanSpeed"], 41)
        self.assertIsInstance(status["fanSpeed"], int)

    def test_offline_error_is_clipped(self):
        self.capture_check_output([b"x" * 5000])
        status = fw_helper.get_status()
        self.assertLessEqual(len(status["error"]), 401)

    def test_output_contract_keys_and_types(self):
        self.capture_check_output([self.run_json_payload(ONLINE_PAYLOAD)])
        online = fw_helper.get_status()
        self.capture_check_output([b'{"status": "error", "reason": "offline"}'])
        offline = fw_helper.get_status()

        base_keys = {
            "online", "currentStrategy", "temperature", "fanSpeed", "active",
            "movingAverageTemperature", "effectiveTemperature", "strategies",
        }
        self.assertEqual(set(online), base_keys)
        self.assertEqual(set(offline), base_keys | {"error"})

        self.assertIsInstance(online["online"], bool)
        self.assertIsInstance(online["currentStrategy"], str)
        self.assertIsInstance(online["fanSpeed"], int)
        self.assertIsInstance(online["active"], bool)
        self.assertIsInstance(online["strategies"], list)
        self.assertIsInstance(offline["error"], str)
        self.assertIsNone(offline["temperature"])
        self.assertIsNone(offline["fanSpeed"])


# ─── simple commands ─────────────────────────────────────────────

class SimpleCommandsTest(SubprocessPatchMixin, unittest.TestCase):
    def test_get_strategies(self):
        self.capture_check_output([b'{"status": "success", "strategies": ["A", "B"]}'])
        self.assertEqual(fw_helper.get_strategies(), {"strategies": ["A", "B"]})

    def test_get_strategies_filters_non_strings(self):
        self.capture_check_output([b'{"status": "success", "strategies": ["A", 1, null]}'])
        self.assertEqual(fw_helper.get_strategies(), {"strategies": ["A"]})

    def test_get_strategies_failure(self):
        self.capture_check_output([FileNotFoundError()])
        self.assertEqual(fw_helper.get_strategies(), {"strategies": []})

    def test_get_strategies_wrong_type(self):
        self.capture_check_output([b'{"status": "success", "strategies": "A"}'])
        self.assertEqual(fw_helper.get_strategies(), {"strategies": []})

    def test_set_strategy_success(self):
        self.capture_check_output([b'{"status": "success", "strategy": "Deaf"}'])
        result = fw_helper.set_strategy("Deaf")
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Deaf")

    def test_set_strategy_failure(self):
        self.capture_check_output([b'{"status": "error", "reason": "nope"}'])
        result = fw_helper.set_strategy("X")
        self.assertFalse(result["success"])
        self.assertIn("nope", result["message"])

    def test_reload_pause_resume(self):
        for func, message in ((fw_helper.do_reload, "Reloaded"),
                              (fw_helper.do_pause, "Paused"),
                              (fw_helper.do_resume, "Resumed")):
            with self.subTest(func=func.__name__):
                self.capture_check_output([b'{"status": "success"}'])
                self.assertEqual(func()["message"], message)


# ─── read_config ─────────────────────────────────────────────────

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

    def test_non_object_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("[]")
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg):
                data = fw_helper.read_config()
        self.assertIn("error", data)
        self.assertIn("JSON object", data["error"])

    def test_broken_schema_does_not_hide_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            schema = os.path.join(tmp, "config.schema.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"defaultStrategy": "A"}, f)
            with open(schema, "w", encoding="utf-8") as f:
                f.write("{broken")
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg), \
                 mock.patch.object(fw_helper, "SCHEMA_PATH", schema):
                data = fw_helper.read_config()
        self.assertEqual(data["config"], {"defaultStrategy": "A"})
        self.assertEqual(data["schema"], {})

    def test_permission_error(self):
        with mock.patch("builtins.open", side_effect=PermissionError), \
             mock.patch.object(fw_helper.os.path, "exists", return_value=True), \
             mock.patch.object(fw_helper, "CONFIG_PATH", "/some/config.json"):
            data = fw_helper.read_config()
        self.assertIn("Permission", data["error"])

    def test_io_error(self):
        with mock.patch("builtins.open", side_effect=OSError("input/output error")), \
             mock.patch.object(fw_helper.os.path, "exists", return_value=True), \
             mock.patch.object(fw_helper, "CONFIG_PATH", "/some/config.json"):
            data = fw_helper.read_config()
        self.assertIn("input/output error", data["error"])

    def test_unexpected_error(self):
        with mock.patch("builtins.open", side_effect=RuntimeError("weird")), \
             mock.patch.object(fw_helper.os.path, "exists", return_value=True), \
             mock.patch.object(fw_helper, "CONFIG_PATH", "/some/config.json"):
            data = fw_helper.read_config()
        self.assertIn("weird", data["error"])


# ─── save_config: compact JSON + 4096 byte command limit ─────────

def make_config_with_command_len(command_len):
    """Config JSON whose compact set_config command is exactly command_len."""
    prefix = "--output-format JSON set_config "
    payload_len = command_len - len(prefix) - 2  # shlex.quote wraps in quotes
    filler_len = payload_len - len('{"x":""}')
    return json.dumps({"x": "a" * filler_len})


class BuildSetConfigCommandTest(unittest.TestCase):
    PREFIX = "--output-format JSON set_config "

    def command_bytes(self, argv):
        return len(shlex.join(argv[1:]).encode("utf-8"))

    def test_invalid_json(self):
        argv, error = fw_helper.build_set_config_command("{oops")
        self.assertIsNone(argv)
        self.assertIn("Invalid JSON", error)

    def test_non_object_payload(self):
        for payload in ("[]", "null", "42", '"text"'):
            with self.subTest(payload=payload):
                argv, error = fw_helper.build_set_config_command(payload)
                self.assertIsNone(argv)
                self.assertIn("JSON object", error)

    def test_compact_serialization(self):
        pretty = json.dumps({"strategies": {"A": {"points": [1, 2]}}}, indent=4)
        argv, error = fw_helper.build_set_config_command(pretty)
        self.assertIsNone(error)
        self.assertEqual(argv[0], "fw-fanctrl")
        self.assertEqual(argv[1:4], ["--output-format", "JSON", "set_config"])
        self.assertNotIn("\n", argv[-1])
        self.assertNotIn(" ", argv[-1])
        self.assertEqual(
            argv[-1],
            json.dumps(json.loads(pretty), ensure_ascii=False, separators=(",", ":")),
        )

    def test_command_size_matches_upstream_formula(self):
        argv, error = fw_helper.build_set_config_command('{"a": 1}')
        self.assertIsNone(error)
        expected = len(shlex.join(argv[1:]).encode("utf-8"))
        self.assertEqual(self.command_bytes(argv), expected)
        # upstream does shlex.join(["--output-format", "JSON", "set_config", json])
        expected_upstream = len(shlex.join(argv[1:]).encode("utf-8"))
        self.assertEqual(expected_upstream, expected)

    def test_exact_boundary_is_allowed(self):
        config = make_config_with_command_len(fw_helper.COMMAND_SOCKET_MAX_BYTES)
        argv, error = fw_helper.build_set_config_command(config)
        self.assertIsNone(error)
        self.assertEqual(
            self.command_bytes(argv), fw_helper.COMMAND_SOCKET_MAX_BYTES
        )

    def test_one_byte_over_limit_is_rejected(self):
        limit = fw_helper.COMMAND_SOCKET_MAX_BYTES
        config = make_config_with_command_len(limit + 1)
        argv, error = fw_helper.build_set_config_command(config)
        self.assertIsNone(argv)
        self.assertIn(str(limit + 1), error)
        self.assertIn(str(limit), error)
        self.assertIn("too large", error)

    def test_single_quotes_count_towards_size(self):
        # shlex.join escapes ' as '\'' (+3 bytes); the limit check must see it.
        payload_len = fw_helper.COMMAND_SOCKET_MAX_BYTES - len(self.PREFIX) - 2
        filler = "a" * (payload_len - len('{"x":""}'))
        config = json.dumps({"x": "'" + filler})
        argv, error = fw_helper.build_set_config_command(config)
        self.assertIsNone(argv)
        measured = len(shlex.join(
            ["--output-format", "JSON", "set_config", argv_compact(config)]
        ).encode("utf-8"))
        self.assertGreater(measured, fw_helper.COMMAND_SOCKET_MAX_BYTES)
        self.assertIn(str(measured), error)

    def test_non_ascii_uses_utf8_bytes(self):
        config = json.dumps({"x": "中" * 10}, ensure_ascii=False)
        argv, error = fw_helper.build_set_config_command(config)
        self.assertIsNone(error)
        self.assertIn("中", argv[-1])
        self.assertEqual(
            self.command_bytes(argv),
            len(self.PREFIX.encode("utf-8")) + len(argv[-1].encode("utf-8")) + 2,
        )

    def test_unserializable_payload(self):
        with mock.patch.object(fw_helper.json, "dumps", side_effect=TypeError("nope")):
            argv, error = fw_helper.build_set_config_command('{"a": 1}')
        self.assertIsNone(argv)
        self.assertIn("Invalid configuration", error)


def argv_compact(config_json_str):
    return json.dumps(
        json.loads(config_json_str), ensure_ascii=False, separators=(",", ":")
    )


class SaveConfigTest(SubprocessPatchMixin, unittest.TestCase):
    def test_invalid_json(self):
        result = fw_helper.save_config("{oops")
        self.assertFalse(result["success"])
        self.assertIn("Invalid JSON", result["message"])

    def test_non_object_payload(self):
        result = fw_helper.save_config("[]")
        self.assertFalse(result["success"])
        self.assertIn("JSON object", result["message"])

    def test_valid_json_forwards_compact_set_config(self):
        calls = self.capture_check_output([b'{"status": "success"}'])
        pretty = json.dumps({"a": 1, "b": {"c": [1, 2]}}, indent=4)
        result = fw_helper.save_config(pretty)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Configuration saved successfully")
        args = calls[0][0]
        self.assertEqual(args[0], "fw-fanctrl")
        self.assertEqual(args[1:4], ["--output-format", "JSON", "set_config"])
        self.assertEqual(args[-1], '{"a":1,"b":{"c":[1,2]}}')

    def test_oversized_config_is_not_sent(self):
        big = json.dumps({
            "defaultStrategy": "A",
            "strategies": {"A": {"pad": "a" * 6000}},
        })
        # No check_output entry: calling it would fail the test.
        self.capture_check_output([])
        result = fw_helper.save_config(big)
        self.assertFalse(result["success"])
        self.assertIn("too large", result["message"])
        self.assertIn("4096", result["message"])

    def test_oversized_message_reports_measured_bytes(self):
        big = json.dumps({"x": "a" * 6000})
        result = fw_helper.save_config(big)
        compact = json.dumps(json.loads(big), ensure_ascii=False, separators=(",", ":"))
        expected_cmd = len(
            shlex.join(["--output-format", "JSON", "set_config", compact]).encode("utf-8")
        )
        self.assertIn(str(expected_cmd), result["message"])
        self.assertIn(str(len(compact.encode("utf-8"))), result["message"])

    def test_real_default_config_is_well_under_limit(self):
        path = "/etc/fw-fanctrl/config.json"
        if not os.path.exists(path):
            self.skipTest("fw-fanctrl config not installed")
        with open(path, encoding="utf-8") as f:
            argv, error = fw_helper.build_set_config_command(f.read())
        self.assertIsNone(error)
        self.assertLess(
            len(shlex.join(argv[1:]).encode("utf-8")),
            fw_helper.COMMAND_SOCKET_MAX_BYTES,
        )


# ─── notifications ───────────────────────────────────────────────

class SendNotificationTest(SubprocessPatchMixin, unittest.TestCase):
    def run_with_result(self, returncode=0, stderr=b"", side_effect=None):
        runner = mock.Mock(
            return_value=types.SimpleNamespace(returncode=returncode, stderr=stderr),
            side_effect=side_effect,
        )
        self.patch_subprocess(run=runner)
        return fw_helper.send_notification("t", "b"), runner

    def test_success(self):
        result, runner = self.run_with_result()
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Notification sent")
        runner.assert_called_once()

    def test_nonzero_returncode_is_failure(self):
        result, _ = self.run_with_result(returncode=1, stderr=b"cannot connect to bus")
        self.assertFalse(result["success"])
        self.assertIn("cannot connect to bus", result["message"])

    def test_nonzero_returncode_without_stderr(self):
        result, _ = self.run_with_result(returncode=3)
        self.assertFalse(result["success"])
        self.assertIn("status 3", result["message"])

    def test_not_found(self):
        result, _ = self.run_with_result(side_effect=FileNotFoundError())
        self.assertFalse(result["success"])
        self.assertIn("notify-send", result["message"])

    def test_timeout(self):
        result, _ = self.run_with_result(
            side_effect=subprocess.TimeoutExpired("x", 5)
        )
        self.assertFalse(result["success"])
        self.assertIn("timed out", result["message"])

    def test_oserror(self):
        result, _ = self.run_with_result(side_effect=OSError("cannot exec"))
        self.assertFalse(result["success"])
        self.assertIn("cannot exec", result["message"])

    def test_normal_urgency_and_argument_separator(self):
        _, runner = self.run_with_result()
        args = runner.call_args[0][0]
        self.assertEqual(args[0], "notify-send")
        self.assertIn("-u", args)
        self.assertEqual(args[args.index("-u") + 1], "normal")
        self.assertIn("-a", args)
        self.assertEqual(args[args.index("-a") + 1], "fw-fanctrl")
        self.assertIn("--", args)
        self.assertLess(args.index("-a"), args.index("--"))
        self.assertLess(args.index("-i"), args.index("--"))
        self.assertLess(args.index("-u"), args.index("--"))
        self.assertEqual(args[-2:], ["t", "b"])

    def test_icon_is_an_existing_breeze_icon(self):
        self.assertNotEqual(fw_helper.NOTIFY_ICON, "computer-fan")
        args = self.run_with_result()[1].call_args[0][0]
        self.assertEqual(args[args.index("-i") + 1], fw_helper.NOTIFY_ICON)

    @unittest.skipUnless(os.path.isdir("/usr/share/icons/breeze"),
                         "Breeze icon theme not installed")
    def test_notify_icon_file_exists(self):
        pattern = os.path.join("/usr/share/icons/breeze", "**",
                               fw_helper.NOTIFY_ICON + ".svg")
        self.assertTrue(glob.glob(pattern, recursive=True))


# ─── stdout encoding ────────────────────────────────────────────

class _AsciiOnlyStream:
    """Text stream without .buffer that raises on the first non-ASCII write."""

    def __init__(self):
        self.chunks = []
        self._first = True

    def write(self, text):
        if self._first:
            self._first = False
            raise UnicodeEncodeError("ascii", text, 0, 1, "ordinal not in range(128)")
        self.chunks.append(text)

    def flush(self):
        pass


class PrintJsonTest(unittest.TestCase):
    def test_ascii_stdout_does_not_crash(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="ascii")
        with mock.patch.object(fw_helper.sys, "stdout", stream):
            fw_helper.print_json({"message": "中文错误"})
        payload = raw.getvalue().decode("utf-8")
        self.assertEqual(json.loads(payload), {"message": "中文错误"})

    def test_stringio_stdout(self):
        buf = io.StringIO()
        with mock.patch.object(fw_helper.sys, "stdout", buf):
            fw_helper.print_json({"message": "中文"})
        self.assertEqual(json.loads(buf.getvalue()), {"message": "中文"})

    def test_text_only_ascii_stream_falls_back_to_escaped_json(self):
        stream = _AsciiOnlyStream()
        with mock.patch.object(fw_helper.sys, "stdout", stream):
            fw_helper.print_json({"message": "中文"})
        self.assertEqual(len(stream.chunks), 1)
        self.assertEqual(json.loads(stream.chunks[0]), {"message": "中文"})


# ─── main dispatch ──────────────────────────────────────────────

class MainDispatchTest(unittest.TestCase):
    def run_main(self, args):
        buf = io.StringIO()
        exit_code = 0
        with mock.patch.object(sys, "argv", ["fw_helper.py"] + args), \
             mock.patch.object(sys, "stdout", buf):
            try:
                fw_helper.main()
            except SystemExit as exc:
                exit_code = exc.code
        return json.loads(buf.getvalue()), exit_code

    def test_no_command(self):
        data, code = self.run_main([])
        self.assertEqual(data, {"error": "No command specified"})
        self.assertEqual(code, 1)

    def test_unknown_command(self):
        data, code = self.run_main(["frobnicate"])
        self.assertIn("Unknown command", data["error"])
        self.assertEqual(code, 1)

    def test_get_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"defaultStrategy": "A"}, f)
            with mock.patch.object(fw_helper, "CONFIG_PATH", cfg):
                out, code = self.run_main(["get_config"])
        self.assertIn("config", out)
        self.assertEqual(code, 0)

    def test_get_status_dispatch(self):
        with mock.patch.object(fw_helper, "get_status",
                               return_value={"online": True}) as m:
            out, code = self.run_main(["get_status"])
        self.assertTrue(out["online"])
        self.assertEqual(code, 0)
        m.assert_called_once()

    def test_get_strategies_dispatch(self):
        with mock.patch.object(fw_helper, "get_strategies",
                               return_value={"strategies": ["A"]}):
            out, code = self.run_main(["get_strategies"])
        self.assertEqual(out, {"strategies": ["A"]})
        self.assertEqual(code, 0)

    def test_save_config_missing_arg(self):
        data, code = self.run_main(["save_config"])
        self.assertFalse(data["success"])
        self.assertEqual(code, 1)

    def test_save_config_dispatch(self):
        with mock.patch.object(fw_helper, "_run_json_command",
                               return_value={"success": True, "message": {}}) as m:
            out, code = self.run_main(["save_config", '{"a": 1}'])
        self.assertTrue(out["success"])
        self.assertEqual(code, 0)
        argv = m.call_args[0][0]
        self.assertEqual(argv[1:4], ["--output-format", "JSON", "set_config"])
        self.assertEqual(argv[-1], '{"a":1}')

    def test_save_config_non_object_dispatch(self):
        out, code = self.run_main(["save_config", "[]"])
        self.assertFalse(out["success"])
        self.assertIn("JSON object", out["message"])

    def test_notify_missing_arg(self):
        data, code = self.run_main(["notify", "title-only"])
        self.assertFalse(data["success"])
        self.assertEqual(code, 1)

    def test_notify_dispatch(self):
        with mock.patch.object(fw_helper, "send_notification",
                               return_value={"success": True, "message": "ok"}) as m:
            out, code = self.run_main(["notify", "title", "body words"])
        self.assertTrue(out["success"])
        self.assertEqual(code, 0)
        m.assert_called_once_with("title", "body words")

    def test_set_strategy_joins_name(self):
        with mock.patch.object(fw_helper, "set_strategy",
                               return_value={"success": True, "message": "A"}) as m:
            out, code = self.run_main(["set_strategy", "A", "B"])
            m.assert_called_once_with("A B")
        self.assertTrue(out["success"])
        self.assertEqual(code, 0)

    def test_set_strategy_missing_arg(self):
        data, code = self.run_main(["set_strategy"])
        self.assertFalse(data["success"])
        self.assertEqual(code, 1)

    def test_simple_command_dispatch(self):
        with mock.patch.object(fw_helper, "do_reload",
                               return_value={"success": True, "message": "Reloaded"}):
            self.assertTrue(self.run_main(["reload"])[0]["success"])

    def test_pause_resume_dispatch(self):
        for command, func, message in (("pause", "do_pause", "Paused"),
                                       ("resume", "do_resume", "Resumed")):
            with self.subTest(command=command):
                with mock.patch.object(fw_helper, func,
                                       return_value={"success": True,
                                                     "message": message}):
                    out, code = self.run_main([command])
                self.assertEqual(out["message"], message)
                self.assertEqual(code, 0)

    def test_crash_guard_still_prints_json(self):
        with mock.patch.object(fw_helper, "_dispatch",
                               side_effect=RuntimeError("boom")):
            data, code = self.run_main(["get_status"])
        self.assertIn("boom", data["error"])
        self.assertEqual(code, 1)


# ─── real subprocess integration via PATH shim ──────────────────

class ShimIntegrationTest(unittest.TestCase):
    """Run the real helper with a fake ``fw-fanctrl`` earlier in PATH.

    This covers the whole pipeline (argv -> subprocess -> JSON -> stdout)
    without touching the real fw-fanctrl service.
    """

    @classmethod
    def setUpClass(cls):
        try:
            os.makedirs(TMP_ROOT, exist_ok=True)
            cls.tmp_root = TMP_ROOT
        except OSError:  # read-only checkout: fall back to system temp
            cls.tmp_root = tempfile.mkdtemp(prefix="fw-helper-tmp-")
            cls._own_tmp_root = True

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_own_tmp_root", False):
            shutil.rmtree(cls.tmp_root, ignore_errors=True)

    def make_shim(self, script):
        shim_dir = tempfile.mkdtemp(prefix="shim-", dir=self.tmp_root)
        self.addCleanup(shutil.rmtree, shim_dir, ignore_errors=True)
        path = os.path.join(shim_dir, "fw-fanctrl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(path, 0o755)
        return shim_dir

    def run_helper(self, *args, shim=None, extra_env=None):
        env = os.environ.copy()
        self.last_shim_dir = None
        if shim is not None:
            shim_dir = self.make_shim(shim)
            self.last_shim_dir = shim_dir
            env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
            env["SHIM_DIR"] = shim_dir
        env.update(extra_env or {})
        return subprocess.run(
            [sys.executable, HELPER_PATH, *args],
            capture_output=True, env=env, timeout=30,
        )

    def stdout_json(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stderr, b"", proc.stderr.decode("utf-8", "replace"))
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1, proc.stdout)
        return json.loads(lines[0])

    def test_stderr_warning_does_not_break_json(self):
        shim = (
            "#!/bin/sh\n"
            "printf '%s\\n' 'warning: something odd happened' >&2\n"
            "printf '%s\\n' '{\"status\": \"success\", \"strategy\": \"Deaf\", "
            "\"temperature\": 42.5, \"speed\": 63, \"active\": true, "
            "\"configuration\": {\"data\": {\"strategies\": {\"A\": {}, \"B\": {}}}}}'\n"
        )
        data = self.stdout_json(self.run_helper("get_status", shim=shim))
        self.assertTrue(data["online"])
        self.assertEqual(data["fanSpeed"], 63)
        self.assertEqual(data["strategies"], ["A", "B"])

    def test_non_object_json_returns_error_json_not_traceback(self):
        for payload, kind in (("[]", "list"), ("null", "null"), ("42", "int")):
            with self.subTest(payload=payload):
                shim = f"#!/bin/sh\nprintf '%s\\n' '{payload}'\n"
                data = self.stdout_json(self.run_helper("get_status", shim=shim))
                self.assertFalse(data["online"])
                self.assertIn("unexpected JSON type", data["error"])
                self.assertIn(kind, data["error"])

    def test_invalid_json_returns_error_json_not_traceback(self):
        shim = "#!/bin/sh\nprintf '%s\\n' 'not json at all'\n"
        data = self.stdout_json(self.run_helper("get_status", shim=shim))
        self.assertFalse(data["online"])
        self.assertIn("not json at all", data["error"])

    def test_error_json_on_stderr_with_exit_1_is_reduced_to_reason(self):
        shim = (
            "#!/bin/sh\n"
            "printf '%s\\n' '{\"status\": \"error\", \"reason\": "
            "\"[Errno 2] No such file or directory\"}' >&2\n"
            "exit 1\n"
        )
        data = self.stdout_json(self.run_helper("get_status", shim=shim))
        self.assertFalse(data["online"])
        self.assertEqual(data["error"], "[Errno 2] No such file or directory")
        self.assertNotIn('"status"', data["error"])

    def test_ascii_stdout_with_chinese_message(self):
        shim = (
            "#!/bin/sh\n"
            "printf '%s\\n' '{\"status\": \"error\", \"reason\": "
            "\"\\u4e2d\\u6587\\u9519\\u8bef\"}' >&2\n"
            "exit 1\n"
        )
        proc = self.run_helper(
            "get_status", shim=shim, extra_env={"PYTHONIOENCODING": "ascii"}
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stderr, b"")
        data = json.loads(proc.stdout.decode("utf-8"))
        self.assertFalse(data["online"])
        self.assertIn("中文错误", data["error"])

    def test_save_config_forwards_compact_json(self):
        shim = (
            "#!/bin/sh\n"
            "printf '%s\\n' \"$@\" > \"$SHIM_DIR/argv.txt\"\n"
            "printf '%s\\n' '{\"status\": \"success\"}'\n"
        )
        pretty = json.dumps({"defaultStrategy": "A",
                             "strategies": {"A": {"fanSpeedUpdateFrequency": 5}}},
                            indent=4)
        proc = self.run_helper("save_config", pretty, shim=shim)
        data = self.stdout_json(proc)
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Configuration saved successfully")

        argv_file = os.path.join(self.last_shim_dir, "argv.txt")
        self.assertTrue(os.path.exists(argv_file))
        with open(argv_file, encoding="utf-8") as f:
            lines = f.read().splitlines()

        self.assertEqual(lines[0:3], ["--output-format", "JSON", "set_config"])
        self.assertEqual(len(lines), 4)
        forwarded = json.loads(lines[3])
        self.assertEqual(forwarded, json.loads(pretty))
        self.assertNotIn(" ", lines[3])
        self.assertNotIn("\n", lines[3])
        self.assertLessEqual(
            len(shlex.join(lines).encode("utf-8")),
            fw_helper.COMMAND_SOCKET_MAX_BYTES,
        )

    def test_oversized_config_is_not_sent_to_fw_fanctrl(self):
        shim = (
            "#!/bin/sh\n"
            "touch \"$SHIM_DIR/invoked\"\n"
            "printf '%s\\n' '{\"status\": \"success\"}'\n"
        )
        big = json.dumps({"defaultStrategy": "A",
                          "strategies": {"A": {"pad": "a" * 6000}}})
        proc = self.run_helper("save_config", big, shim=shim)
        data = self.stdout_json(proc)
        self.assertFalse(data["success"])
        self.assertIn("too large", data["message"])
        self.assertIn("4096", data["message"])
        self.assertFalse(
            os.path.exists(os.path.join(self.last_shim_dir, "invoked")),
            "oversized config must not reach fw-fanctrl",
        )

    def test_usage_error_still_prints_json(self):
        proc = self.run_helper("save_config")
        # Usage errors exit non-zero, but stdout still holds one JSON object.
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(len(proc.stdout.decode("utf-8").splitlines()), 1)
        data = json.loads(proc.stdout.decode("utf-8"))
        self.assertFalse(data["success"])

    def test_get_config_reads_file_not_cli(self):
        # get_config must not call fw-fanctrl at all; a shim that would fail
        # proves the command is purely file-based.
        shim = "#!/bin/sh\nexit 99\n"
        proc = self.run_helper(
            "get_config", shim=shim,
            extra_env={"FW_HELPER_TEST": "1"},
        )
        # The real /etc/fw-fanctrl/config.json exists on the dev machine; on
        # other machines read_config still returns a JSON object with `error`.
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout.decode("utf-8"))
        self.assertTrue("config" in data or "error" in data)


if __name__ == "__main__":
    unittest.main()

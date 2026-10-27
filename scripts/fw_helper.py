#!/usr/bin/env python3
"""
fw-fanctrl helper script for KDE Plasma 6 Plasmoid.

Wraps the fw-fanctrl CLI and always prints exactly one JSON object on stdout.
All CLI calls have timeouts, so a stuck fw-fanctrl process can never freeze the
plasmoid.

Output contract (consumed by contents/ui/FwBackend.qml and configCurves.qml):

  get_status            -> object, always these keys:
                             online: bool
                             currentStrategy: str        ("")
                             temperature: number | null
                             fanSpeed: int | null
                             active: bool
                             movingAverageTemperature: number | null
                             effectiveTemperature: number | null
                             strategies: array[str]      ([])
                           offline result additionally carries
                             error: str
  get_strategies        -> {"strategies": array[str]}
  get_config            -> {"config": object, "schema": object}
                           or {"error": str}
  save_config / set_strategy / reload / pause / resume / notify
                        -> {"success": bool, "message": str}
  usage errors / crash  -> {"error": str}

Numeric fields are either a real number of the documented type or JSON null;
they are never strings and never NaN/Infinity.  Consumers must treat null as
"unknown" (QML: `data.fanSpeed !== undefined && data.fanSpeed !== null`).
"""

import json
import math
import os
import shlex
import subprocess
import sys

CONFIG_PATH = "/etc/fw-fanctrl/config.json"
SCHEMA_PATH = "/etc/fw-fanctrl/config.schema.json"

CLI_TIMEOUT = 10       # normal status/action commands
SAVE_TIMEOUT = 60      # set_config may validate a larger payload
FALLBACK_TIMEOUT = 3   # second `print list` call if `print all` had no strategies
NOTIFY_TIMEOUT = 5

# The fw-fanctrl service reads one client command with a single
# `recv(4096)` (see fw_fanctrl/socketController/UnixSocketController.py).
# The CLI sends `shlex.join(sys.argv[1:])` through that socket, so this is the
# hard upper bound for the *whole command line*, not just the JSON payload.
# A longer command is silently truncated by the service and the client dies
# with "Connection reset by peer" (measured: 4096 B works, 4097 B fails).
COMMAND_SOCKET_MAX_BYTES = 4096

# "speedometer" ships with Breeze (actions/16|22|24/speedometer.svg and the
# -symbolic variant); verified on this machine with `find /usr/share/icons`.
# The previous "computer-fan" does not exist in any installed icon theme.
NOTIFY_ICON = "speedometer"

_MAX_ERROR_LEN = 400


# ─── Small generic helpers ─────────────────────────────────────────

def _clip_message(message, limit=_MAX_ERROR_LEN):
    message = (message or "").strip()
    if len(message) > limit:
        return message[:limit] + "…"
    return message


def _decode(raw):
    """Decode subprocess bytes to text (tolerant of undecodable bytes)."""
    if not raw:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").strip()
    return str(raw).strip()


def _parse_json_object(raw):
    """Parse raw CLI output into a dict.

    Returns (data, None) on success, (None, reason) otherwise.  If stdout is
    polluted by a warning line around an otherwise valid JSON object, the
    first-to-last brace substring is used as a fallback candidate.
    """
    text = _decode(raw)
    if not text:
        return None, "returned no output"

    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])

    saw_json = False
    last_parsed = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        saw_json = True
        if isinstance(parsed, dict):
            return parsed, None
        last_parsed = parsed

    if saw_json:
        kind = "null" if last_parsed is None else type(last_parsed).__name__
        return None, f"returned unexpected JSON type: {kind} (expected an object)"
    return None, f"returned unexpected output: {_clip_message(text, 200)}"


def _error_reason(*blobs):
    """Extract `reason`/`message` from an error JSON blob, if any."""
    for blob in blobs:
        data, _ = _parse_json_object(blob)
        if data is None:
            continue
        reason = data.get("reason") or data.get("message") or data.get("error")
        if reason:
            return _clip_message(str(reason))
    return None


def _as_string(value):
    return value if isinstance(value, str) else ""


def _as_number(value):
    """Return a finite int/float or None.  Booleans and strings are rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _as_int(value):
    number = _as_number(value)
    return None if number is None else int(number)


def _as_strategy_list(value):
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


# ─── fw-fanctrl CLI calls ──────────────────────────────────────────

def _run_json_command(args, timeout=CLI_TIMEOUT):
    """Run a fw-fanctrl command in JSON mode and normalize its result.

    stderr is captured separately: a warning on stderr must not corrupt the
    JSON on stdout.  On a non-zero exit an error JSON written by fw-fanctrl
    (upstream writes it to stderr) is reduced to its `reason`.
    """
    try:
        stdout = subprocess.check_output(
            args, stderr=subprocess.PIPE, timeout=timeout
        )
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"fw-fanctrl timed out after {timeout}s"}
    except subprocess.CalledProcessError as e:
        stdout = getattr(e, "output", None)
        stderr = getattr(e, "stderr", None)
        reason = _error_reason(stderr, stdout)
        if reason is None:
            reason = _decode(stderr) or _decode(stdout) or f"fw-fanctrl exited with status {e.returncode}"
        return {"success": False, "message": _clip_message(reason)}
    except OSError as e:
        return {"success": False, "message": _clip_message(str(e))}

    data, error = _parse_json_object(stdout)
    if data is None:
        return {"success": False, "message": f"fw-fanctrl {error}"}

    if data.get("status") != "success":
        reason = data.get("reason") or data.get("message") or data.get("error")
        return {
            "success": False,
            "message": _clip_message(str(reason)) if reason else "fw-fanctrl reported an error",
        }
    return {"success": True, "message": data}


def _offline_status(error):
    """Uniform offline status object (same keys as the online one + error)."""
    return {
        "online": False,
        "currentStrategy": "",
        "temperature": None,
        "fanSpeed": None,
        "active": False,
        "movingAverageTemperature": None,
        "effectiveTemperature": None,
        "strategies": [],
        "error": _clip_message(error) or "fw-fanctrl status error",
    }


def get_status():
    """Return current status from fw-fanctrl including temp, fan speed, strategy.

    fw-fanctrl's `print all` already contains the whole configuration, so the
    strategy list is extracted here as well; the plasmoid only needs one CLI
    call per poll instead of two.  The fallback `print list` call (only when
    `print all` has no configuration) uses a much shorter timeout so a hanging
    service cannot stall the 2 s polling loop for long.
    """
    result = _run_json_command(
        ["fw-fanctrl", "--output-format", "JSON", "print", "all"],
        timeout=CLI_TIMEOUT,
    )
    if not result["success"]:
        return _offline_status(result["message"])

    data = result["message"]

    configuration = data.get("configuration")
    if not isinstance(configuration, dict):
        configuration = {}
    config_data = configuration.get("data")
    if not isinstance(config_data, dict):
        config_data = {}
    raw_strategies = config_data.get("strategies")
    strategies = list(raw_strategies.keys()) if isinstance(raw_strategies, dict) else []
    if not strategies:
        strategies = get_strategies(timeout=FALLBACK_TIMEOUT).get("strategies", [])

    return {
        "online": True,
        "currentStrategy": _as_string(data.get("strategy")),
        "temperature": _as_number(data.get("temperature")),
        "fanSpeed": _as_int(data.get("speed")),
        "active": data.get("active") is True,
        "movingAverageTemperature": _as_number(data.get("movingAverageTemperature")),
        "effectiveTemperature": _as_number(data.get("effectiveTemperature")),
        "strategies": strategies,
    }


def get_strategies(timeout=CLI_TIMEOUT):
    """Return available strategies using fw-fanctrl's JSON output."""
    result = _run_json_command(
        ["fw-fanctrl", "--output-format", "JSON", "print", "list"],
        timeout=timeout,
    )
    if not result["success"]:
        return {"strategies": []}
    return {"strategies": _as_strategy_list(result["message"].get("strategies"))}


def set_strategy(name):
    """Set active strategy."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "use", name])
    if result["success"] and isinstance(result["message"], dict):
        result["message"] = _as_string(result["message"].get("strategy")) or name
    return result


def do_reload():
    """Reload fw-fanctrl configuration."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "reload"])
    if result["success"]:
        result["message"] = "Reloaded"
    return result


def do_pause():
    """Pause fan control."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "pause"])
    if result["success"]:
        result["message"] = "Paused"
    return result


def do_resume():
    """Resume fan control."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "resume"])
    if result["success"]:
        result["message"] = "Resumed"
    return result


# ─── Config read/save ──────────────────────────────────────────────

def read_config():
    """Read the fw-fanctrl config file. Returns config dict or error."""
    try:
        if not os.path.exists(CONFIG_PATH):
            return {"error": f"Config file not found: {CONFIG_PATH}"}

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            return {
                "error": f"Invalid config: expected a JSON object, got {type(config).__name__}"
            }

        # A broken schema file must not hide a perfectly readable config.
        schema = {}
        try:
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    schema = loaded
        except (json.JSONDecodeError, OSError):
            schema = {}

        return {"config": config, "schema": schema}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in config: {e}"}
    except PermissionError:
        return {"error": "Permission denied reading config"}
    except OSError as e:
        return {"error": _clip_message(str(e))}
    except Exception as e:
        return {"error": _clip_message(str(e))}


def build_set_config_command(config_json_str):
    """Build the argv sent to fw-fanctrl for set_config, or return an error.

    The configuration is re-serialized as compact JSON (no indentation, no
    whitespace) because the upstream socket protocol reads the command with a
    single recv(4096).  The command size is measured exactly as upstream sees
    it: `len(shlex.join(sys.argv[1:]).encode("utf-8"))`.

    Returns (argv, None) on success or (None, error_message).
    """
    try:
        config = json.loads(config_json_str)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"

    if not isinstance(config, dict):
        return None, f"Configuration must be a JSON object, got {type(config).__name__}"

    try:
        compact = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        return None, f"Invalid configuration: {e}"

    command = ["--output-format", "JSON", "set_config", compact]
    command_bytes = len(shlex.join(command).encode("utf-8"))
    payload_bytes = len(compact.encode("utf-8"))
    if command_bytes > COMMAND_SOCKET_MAX_BYTES:
        return None, (
            f"Configuration is too large for fw-fanctrl: the set_config command "
            f"would be {command_bytes} bytes ({payload_bytes} bytes of JSON), but the "
            f"service reads at most {COMMAND_SOCKET_MAX_BYTES} bytes per command. "
            f"Remove a strategy or some curve points and try again."
        )
    return ["fw-fanctrl"] + command, None


def save_config(config_json_str):
    """Validate and apply config through fw-fanctrl's official set_config.

    fw-fanctrl validates the JSON against its bundled schema and checks that
    defaultStrategy / strategyOnDischarging still exist before saving.  It
    runs as the service user, so no pkexec/temp-file dance is needed.
    """
    argv, error = build_set_config_command(config_json_str)
    if error is not None:
        return {"success": False, "message": error}

    result = _run_json_command(argv, timeout=SAVE_TIMEOUT)
    if result["success"]:
        result["message"] = "Configuration saved successfully"
    return result


# ─── Notifications ─────────────────────────────────────────────────

def send_notification(title, body):
    """Send a desktop notification via notify-send (libnotify)."""
    try:
        completed = subprocess.run(
            ["notify-send", "-a", "fw-fanctrl", "-i", NOTIFY_ICON,
             "-u", "normal", "--", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=NOTIFY_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        return {"success": False, "message": "notify-send not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"notify-send timed out after {NOTIFY_TIMEOUT}s"}
    except OSError as e:
        return {"success": False, "message": _clip_message(str(e))}

    if completed.returncode == 0:
        return {"success": True, "message": "Notification sent"}

    detail = _decode(getattr(completed, "stderr", None))
    return {
        "success": False,
        "message": _clip_message(detail) or f"notify-send exited with status {completed.returncode}",
    }


# ─── CLI entry point ───────────────────────────────────────────────

def print_json(data):
    """Print data as one JSON line, independent of the stdout encoding.

    Writing UTF-8 bytes to `sys.stdout.buffer` bypasses the text encoding, so
    `PYTHONIOENCODING=ascii` (or any non-UTF-8 locale) cannot make the helper
    crash with UnicodeEncodeError.
    """
    payload = json.dumps(data, ensure_ascii=False)
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write((payload + "\n").encode("utf-8"))
        buffer.flush()
        return
    try:
        stream.write(payload + "\n")
    except UnicodeEncodeError:
        stream.write(json.dumps(data) + "\n")
    stream.flush()


def _dispatch():
    if len(sys.argv) < 2:
        print_json({"error": "No command specified"})
        sys.exit(1)

    command = sys.argv[1]

    if command == "get_status":
        print_json(get_status())

    elif command == "get_strategies":
        print_json(get_strategies())

    elif command == "set_strategy":
        if len(sys.argv) < 3:
            print_json({"success": False, "message": "Missing strategy name"})
            sys.exit(1)
        name = " ".join(sys.argv[2:])
        print_json(set_strategy(name))

    elif command == "reload":
        print_json(do_reload())

    elif command == "pause":
        print_json(do_pause())

    elif command == "resume":
        print_json(do_resume())

    elif command == "get_config":
        print_json(read_config())

    elif command == "save_config":
        if len(sys.argv) < 3:
            print_json({"success": False, "message": "Missing JSON data"})
            sys.exit(1)
        json_str = " ".join(sys.argv[2:])
        print_json(save_config(json_str))

    elif command == "notify":
        if len(sys.argv) < 4:
            print_json({"success": False, "message": "Missing title or body"})
            sys.exit(1)
        title = sys.argv[2]
        body = " ".join(sys.argv[3:])
        print_json(send_notification(title, body))

    else:
        print_json({"error": f"Unknown command: {command}"})
        sys.exit(1)


def main():
    # Last-resort guard: the QML side assumes "stdout is always JSON".
    try:
        _dispatch()
    except Exception as e:  # noqa: BLE001 - the helper must never die silently
        print_json({"error": _clip_message(str(e)) or "Internal helper error"})
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
fw-fanctrl helper script for KDE Plasma 6 Plasmoid.

Wraps the fw-fanctrl CLI and returns JSON on stdout.  All CLI calls have
timeouts so a stuck fw-fanctrl process can never freeze the plasmoid.
"""

import json
import os
import subprocess
import sys

CONFIG_PATH = "/etc/fw-fanctrl/config.json"
SCHEMA_PATH = "/etc/fw-fanctrl/config.schema.json"

CLI_TIMEOUT = 10       # normal status/action commands
SAVE_TIMEOUT = 60      # set_config may validate a larger payload


def _clip_message(message, limit=400):
    message = (message or "").strip()
    if len(message) > limit:
        return message[:limit] + "…"
    return message


def _run_json_command(args, timeout=CLI_TIMEOUT):
    """Run a fw-fanctrl command in JSON mode and normalize its result."""
    try:
        output = subprocess.check_output(
            args, stderr=subprocess.STDOUT, timeout=timeout
        ).decode("utf-8", "replace").strip()
        data = json.loads(output)
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "fw-fanctrl command timed out"}
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": _clip_message(e.output.decode("utf-8", "replace") if e.output else "Command failed"),
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"success": False, "message": _clip_message(str(e))}

    if data.get("status") != "success":
        return {
            "success": False,
            "message": _clip_message(data.get("reason") or data.get("message") or "fw-fanctrl command failed"),
        }
    return {"success": True, "message": data}


def get_status():
    """Return current status from fw-fanctrl including temp, fan speed, strategy.

    fw-fanctrl's `print all` already contains the whole configuration, so the
    strategy list is extracted here as well; the plasmoid only needs one CLI
    call per poll instead of two.
    """
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "--output-format", "JSON", "print", "all"],
            stderr=subprocess.STDOUT,
            timeout=CLI_TIMEOUT,
        ).decode("utf-8", "replace").strip()
        data = json.loads(output)
    except FileNotFoundError:
        return {"online": False, "currentStrategy": "", "strategies": [], "error": "fw-fanctrl not found"}
    except subprocess.TimeoutExpired:
        return {"online": False, "currentStrategy": "", "strategies": [], "error": "fw-fanctrl command timed out"}
    except subprocess.CalledProcessError as e:
        return {
            "online": False,
            "currentStrategy": "",
            "strategies": [],
            "error": _clip_message(e.output.decode("utf-8", "replace") if e.output else "Command failed"),
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"online": False, "currentStrategy": "", "strategies": [], "error": _clip_message(str(e))}

    if data.get("status") != "success":
        return {
            "online": False,
            "currentStrategy": "",
            "strategies": [],
            "error": _clip_message(data.get("reason") or data.get("message") or "fw-fanctrl status error"),
        }

    configuration = data.get("configuration") or {}
    config_data = configuration.get("data") or {}
    strategies = list((config_data.get("strategies") or {}).keys())
    if not strategies:
        strategies = get_strategies().get("strategies", [])

    return {
        "online": True,
        "currentStrategy": data.get("strategy", ""),
        "temperature": data.get("temperature"),
        "fanSpeed": data.get("speed"),
        "active": data.get("active", False),
        "movingAverageTemperature": data.get("movingAverageTemperature"),
        "effectiveTemperature": data.get("effectiveTemperature"),
        "strategies": strategies,
    }


def get_strategies():
    """Return available strategies using fw-fanctrl's JSON output."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "print", "list"])
    if not result["success"]:
        return {"strategies": []}
    return {"strategies": result["message"].get("strategies", []) if isinstance(result["message"], dict) else []}


def set_strategy(name):
    """Set active strategy."""
    result = _run_json_command(["fw-fanctrl", "--output-format", "JSON", "use", name])
    if result["success"] and isinstance(result["message"], dict):
        result["message"] = result["message"].get("strategy", name)
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

        schema = {}
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)

        return {"config": config, "schema": schema}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in config: {e}"}
    except PermissionError:
        return {"error": "Permission denied reading config"}
    except Exception as e:
        return {"error": str(e)}


def save_config(config_json_str):
    """Validate and apply config through fw-fanctrl's official set_config.

    fw-fanctrl validates the JSON against its bundled schema and checks that
    defaultStrategy / strategyOnDischarging still exist before saving.  It
    runs as the service user, so no pkexec/temp-file dance is needed.
    """
    try:
        json.loads(config_json_str)
    except json.JSONDecodeError as e:
        return {"success": False, "message": f"Invalid JSON: {e}"}

    result = _run_json_command(
        ["fw-fanctrl", "--output-format", "JSON", "set_config", config_json_str],
        timeout=SAVE_TIMEOUT,
    )
    if result["success"]:
        result["message"] = "Configuration saved successfully"
    return result


# ─── CLI entry point ───────────────────────────────────────────────

def print_json(data):
    """Print data as JSON stdout."""
    print(json.dumps(data, ensure_ascii=False))
    sys.stdout.flush()


def main():
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

    else:
        print_json({"error": f"Unknown command: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()

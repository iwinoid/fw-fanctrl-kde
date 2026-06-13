#!/usr/bin/env python3
"""
fw-fanctrl helper script for KDE Plasma 6 Plasmoid.
Handles config reading/writing with JSON validation and pkexec for privileged operations.
"""

import json
import os
import subprocess
import sys
import shutil

CONFIG_PATH = "/etc/fw-fanctrl/config.json"
SCHEMA_PATH = "/etc/fw-fanctrl/config.schema.json"


# ─── fw-fanctrl CLI wrappers ───────────────────────────────────────

def get_status():
    """Return current status from fw-fanctrl including temp, fan speed, strategy."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "--output-format", "JSON", "print", "all"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        data = json.loads(output)
        if data.get("status") == "success":
            return {
                "online": True,
                "currentStrategy": data.get("strategy", ""),
                "temperature": data.get("temperature"),
                "fanSpeed": data.get("speed"),
                "active": data.get("active", False),
                "movingAverageTemperature": data.get("movingAverageTemperature"),
                "effectiveTemperature": data.get("effectiveTemperature")
            }
        return {"online": False, "currentStrategy": ""}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {"online": False, "currentStrategy": ""}


def get_strategies():
    """Return list of available strategies."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "print", "list"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        strategies = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("- "):
                strategies.append(line[2:])
        return {"strategies": strategies}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"strategies": []}


def set_strategy(name):
    """Set active strategy."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "use", name],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        return {"success": True, "message": output}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.output.decode("utf-8").strip()}
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}


def do_reload():
    """Reload fw-fanctrl configuration."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "reload"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        return {"success": True, "message": output}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.output.decode("utf-8").strip()}
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}


def do_pause():
    """Pause fan control."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "pause"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        return {"success": True, "message": output}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.output.decode("utf-8").strip()}
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}


def do_resume():
    """Resume fan control."""
    try:
        output = subprocess.check_output(
            ["fw-fanctrl", "resume"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        return {"success": True, "message": output}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.output.decode("utf-8").strip()}
    except FileNotFoundError:
        return {"success": False, "message": "fw-fanctrl not found"}


# ─── Config read/write ─────────────────────────────────────────────

def read_config():
    """Read the fw-fanctrl config file. Returns config dict or error."""
    try:
        if not os.path.exists(CONFIG_PATH):
            return {"error": f"Config file not found: {CONFIG_PATH}"}

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Also read schema for validation reference
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
    """Save config using pkexec for root privileges."""
    tmp_path = None
    try:
        # Validate JSON first
        config = json.loads(config_json_str)

        # Write to a temp file
        tmp_path = f"/tmp/fw-fanctrl-config-{os.getuid()}.json"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            f.write("\n")

        # Use pkexec to copy to /etc/
        pkexec_cmd = shutil.which("pkexec")
        cp_cmd = shutil.which("cp")
        if not pkexec_cmd:
            return {"success": False, "message": "pkexec not found. Please install polkit."}

        # Build the copy command
        result = subprocess.run(
            [pkexec_cmd, cp_cmd, tmp_path, CONFIG_PATH],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return {"success": True, "message": "Configuration saved successfully"}
        else:
            error_msg = result.stderr.strip() or f"Exit code: {result.returncode}"
            return {"success": False, "message": f"Failed to save config: {error_msg}"}
    except json.JSONDecodeError as e:
        return {"success": False, "message": f"Invalid JSON: {e}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "pkexec timed out"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─── CLI entry point ───────────────────────────────────────────────

def print_json(data):
    """Print data as JSON stdout."""
    print(json.dumps(data, ensure_ascii=False))
    sys.stdout.flush()


def main():
    if len(sys.argv) < 2:
        print_json({"error": "No command specified. Commands: get_status, get_strategies, set_strategy <name>, reload, pause, resume, get_config, save_config <json>"})
        sys.exit(1)

    command = sys.argv[1]

    if command == "get_status":
        # Combine status + strategies
        status = get_status()
        strategies_data = get_strategies()
        status.update(strategies_data)
        print_json(status)

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
        json_str = sys.argv[2]
        print_json(save_config(json_str))

    else:
        print_json({"error": f"Unknown command: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()

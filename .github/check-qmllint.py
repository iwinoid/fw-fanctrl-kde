#!/usr/bin/env python3
"""Strict qmllint gate shared by CI and `make lint`.

Why this exists
---------------
`.qmllint.ini` sets `MaxWarnings=-1`. Under Qt 6.12 that makes qmllint print
*no* warnings in its text output and always exit 0, so filtering the text
output with grep can never catch a real code problem. This script reads
qmllint's machine-readable `--json` output instead and requires the baseline to
be completely clean:

  * every linted file must report "success": true
  * no diagnostics of any severity (warning, error, info) are allowed
  * qmllint must not print anything to stdout/stderr

There is deliberately no allowlist: a diagnostic means the code (or the QML
module stub) has to be fixed, not filtered.

Why --bare and the stub module
------------------------------
CI runs in an Arch container without plasma-workspace, which provides
`org.kde.plasma.workspace.osd` (OsdWindow/OsdItem). Without that module qmllint
emits cascading import warnings for main.qml. `.github/qmllint-stubs` provides
a minimal stand-in that mirrors only the API the applet uses. `--bare` disables
qmllint's implicit import paths, and the stub directory is passed before Qt's
QML root with -I, so the stub wins over any system copy and CI lints exactly
the same way whether plasma-workspace is installed or not.

Usage: python3 .github/check-qmllint.py [files...]
Environment overrides: QMLLINT, QT_QML_ROOT
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QMLLINT = os.environ.get("QMLLINT", "/usr/lib/qt6/bin/qmllint")
QT_QML_ROOT = os.environ.get("QT_QML_ROOT", "/usr/lib/qt6/qml")
STUB_DIR = ROOT / ".github" / "qmllint-stubs"


def fail(message: str) -> int:
    print(f"qmllint-strict: {message}", file=sys.stderr)
    return 1


def find_files(argv: list[str]) -> list[str]:
    if argv:
        return argv
    files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "contents").rglob("*.qml"))
    return files


def main(argv: list[str]) -> int:
    if not Path(QMLLINT).is_file():
        return fail(
            f"{QMLLINT} not found; use Qt 6 qmllint (the qml* commands on PATH are Qt 5)"
        )
    if not STUB_DIR.is_dir():
        return fail(f"QML module stub directory missing: {STUB_DIR}")

    files = find_files(argv)
    if not files:
        return fail("no QML files to lint")

    with tempfile.TemporaryDirectory(prefix="qmllint-ci-") as tmpdir:
        json_path = Path(tmpdir) / "qmllint.json"
        command = [
            QMLLINT,
            "--bare",
            "-I",
            str(STUB_DIR),
            "-I",
            QT_QML_ROOT,
            "--json",
            str(json_path),
            *files,
        ]
        print("qmllint-strict: " + " ".join(command))
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

        text = (proc.stdout + proc.stderr).strip()
        if text:
            print(text, file=sys.stderr)
            return fail("qmllint wrote text output; the strict gate expects none with --json")

        if not json_path.is_file():
            return fail(f"qmllint produced no JSON report (exit code {proc.returncode})")
        try:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return fail(f"cannot parse qmllint JSON report: {error}")

    problems: list[str] = []
    entries = report.get("files", [])
    if not entries:
        return fail("qmllint JSON report contains no files")

    for entry in entries:
        name = entry.get("filename", "<unknown>")
        if not entry.get("success", False):
            problems.append(f"{name}: qmllint reported failure (success=false)")
        for diagnostic in entry.get("warnings", []):
            severity = diagnostic.get("type", "?")
            diagnostic_id = diagnostic.get("id", "?")
            line = diagnostic.get("line", "?")
            column = diagnostic.get("column", "?")
            message = diagnostic.get("message", "").splitlines()[0] if diagnostic.get("message") else ""
            problems.append(f"{name}:{line}:{column}: {severity} [{diagnostic_id}] {message}")

    if problems:
        print("qmllint-strict: lint is not clean:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return fail(f"{len(problems)} diagnostic(s); the baseline must stay at zero")

    if proc.returncode != 0:
        return fail(f"qmllint exited with {proc.returncode} but reported no diagnostics")

    print(f"qmllint-strict: {len(entries)} file(s) linted, 0 diagnostics — OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

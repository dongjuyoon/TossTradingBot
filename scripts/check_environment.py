#!/usr/bin/env python3
"""Non-destructive local environment diagnostics for Phase 0."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def command_version(command: str, *args: str) -> Check:
    path = shutil.which(command)
    if path is None:
        return Check(command, "WARN", "not found")
    completed = subprocess.run(
        [path, *args], capture_output=True, text=True, timeout=10, check=False
    )
    detail = (completed.stdout or completed.stderr).strip().splitlines()
    return Check(command, "PASS" if completed.returncode == 0 else "WARN", detail[0] or path)


def collect(project_root: Path) -> list[Check]:
    python_ok = sys.version_info[:2] == (3, 12)
    venv_path = project_root.joinpath(".venv").resolve()
    venv_ok = sys.prefix != sys.base_prefix and venv_path == Path(sys.prefix).resolve()
    mode = os.getenv("TRADING_MODE", "PAPER")
    return [
        Check("platform", "PASS", f"{platform.system()} {platform.machine()}"),
        Check("python", "PASS" if python_ok else "FAIL", platform.python_version()),
        Check("project_venv", "PASS" if venv_ok else "WARN", sys.prefix),
        command_version("git", "--version"),
        command_version("ollama", "--version"),
        Check("sqlite", "PASS", sqlite3.sqlite_version),
        Check("trading_mode", "PASS" if mode == "PAPER" else "FAIL", mode),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()
    checks = collect(Path(__file__).resolve().parents[1])
    if args.json:
        print(json.dumps([asdict(item) for item in checks], indent=2))
    else:
        for item in checks:
            print(f"[{item.status:4}] {item.name}: {item.detail}")
    return 1 if any(item.status == "FAIL" for item in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())

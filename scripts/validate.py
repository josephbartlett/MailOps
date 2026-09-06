"""Run the same offline validation locally and in CI, using temporary state."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with TemporaryDirectory(prefix="mailops-validation-") as directory:
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("MAILOPS_")}
        env["MAILOPS_HOME"] = str(Path(directory) / ".mailops")
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONUTF8"] = "1"
        commands = [
            ["scripts/check_repo.py"],
            ["-m", "ruff", "check", "src", "tests", "scripts"],
            ["-m", "pytest"],
            ["-m", "mailops.cli.main", "--help"],
            ["-m", "mailops.cli.main", "demo", "seed"],
            ["-m", "mailops.cli.main", "ask", "show unanswered finance threads"],
        ]
        for command in commands:
            print(f"Running: python {' '.join(command)}", flush=True)
            result = subprocess.run([sys.executable, *command], cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

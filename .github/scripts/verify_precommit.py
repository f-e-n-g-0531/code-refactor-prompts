#!/usr/bin/env python3
"""Test the installed pre-commit hook against the current Git commit."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verify(root: Path = ROOT) -> None:
    root = root.resolve()
    commit = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, check=True,
                            capture_output=True, text=True).stdout.strip()
    fixtures = root / "scripts" / "fixtures"
    # The files passed to pre-commit must be inside its Git working tree.
    with tempfile.TemporaryDirectory(prefix=".pre-commit-e2e-", dir=root) as files, tempfile.TemporaryDirectory(
        prefix="pre-commit-venv-",
    ) as environment:
        work = Path(files)
        venv.EnvBuilder(with_pip=True).create(environment)
        python = Path(environment) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "pre-commit"],
                       cwd=root, check=True)
        env = {**os.environ, "PRE_COMMIT_HOME": str(Path(environment) / "hook-cache")}
        if os.name == "nt":
            # Avoid virtualenv's app-data seed image cleanup on Windows,
            # where the temporary pip launchers can still be held open.
            env.setdefault("VIRTUALENV_SEEDER", "pip")
        cmd = [str(python), "-m", "pre_commit", "try-repo", ".", "--ref", commit, "--files"]
        for name, expected in (("good", 0), ("bad", 1)):
            dest = work / f"{name}.prompt.txt"
            shutil.copyfile(fixtures / f"{name}-prompt.txt", dest)
            result = subprocess.run([*cmd, dest.relative_to(root).as_posix()], cwd=root, env=env)
            if result.returncode != expected:
                raise RuntimeError(f"expected pre-commit exit {expected} for {name} prompt, got {result.returncode}")


def main() -> int:
    try:
        verify()
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"pre-commit end-to-end check failed: {exc}", file=sys.stderr)
        return 1
    print("pre-commit hook end-to-end OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

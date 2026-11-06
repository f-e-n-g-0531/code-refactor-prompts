#!/usr/bin/env python3
"""Build ZIP/tar.gz distributions from the current tree and verify their fast gate."""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "code-refactor-prompts"
FILES = ("SKILL.md", "README.md", "README.en.md", "CONTRIBUTING.md", "CHANGELOG.md",
         "LICENSE", ".gitignore", ".pre-commit-hooks.yaml", "pyproject.toml", "action.yml")
DIRECTORIES = ("references", "examples", "scripts", ".github/scripts")
MARKER = ".skill-package"
MARKER_CONTENT = b"code-refactor-prompts distribution v1\n"


def package_files(root: Path) -> dict[str, bytes]:
    result = {name: (root / name).read_bytes() for name in FILES}
    for directory in DIRECTORIES:
        base = root / directory
        if not base.is_dir():
            raise ValueError(f"missing package directory: {directory}")
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(root)
            if any(part in {"__pycache__", ".pytest_cache", ".venv", "build", "dist"}
                   or part.endswith(".egg-info") for part in relative.parts):
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise ValueError(f"package must not contain symlinks: {relative}")
            if path.is_file():
                result[relative.as_posix()] = path.read_bytes()
    result[MARKER] = MARKER_CONTENT
    return result


def build(root: Path, output: Path, label: str) -> list[Path]:
    # Labels become filenames; never allow path or shell syntax.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
        raise ValueError("invalid package label")
    files = package_files(root)
    output.mkdir(parents=True, exist_ok=True)
    archives = [output / f"{PREFIX}-{label}.zip", output / f"{PREFIX}-{label}.tar.gz"]
    with zipfile.ZipFile(archives[0], "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(f"{PREFIX}/{name}", data)
    with tarfile.open(archives[1], "w:gz") as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(f"{PREFIX}/{name}")
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    (output / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in archives
    ), encoding="utf-8")
    return archives


def verify(archives: list[Path], root: Path) -> None:
    expected = {f"{PREFIX}/{name}": data for name, data in package_files(root).items()}
    for path in archives:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                actual = {name: archive.read(name) for name in archive.namelist()}
        else:
            with tarfile.open(path) as archive:
                actual = {}
                for member in archive.getmembers():
                    if not member.isfile():
                        raise ValueError(f"unexpected archive entry: {member.name}")
                    actual[member.name] = archive.extractfile(member).read()
        if actual != expected:
            raise ValueError(f"package contents mismatch: {path}")
        checksum = f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        if checksum not in (path.parent / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            raise ValueError(f"checksum mismatch: {path}")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            # Names have been compared to our trusted allowlist before extraction.
            for name, data in actual.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            unpacked = destination / PREFIX
            subprocess.run([sys.executable, str(unpacked / "scripts/run_checks.py")],
                           cwd=unpacked, check=True,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8", "PACKAGE_GATE_CHILD": "1"})
    print("release artifacts OK: ZIP and tar.gz fast gates passed")


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--label", default="ci")
    parser.add_argument("--verify", action="store_true", help="run fast gates in both unpacked archives")
    args = parser.parse_args()
    archives = build(ROOT, args.output, args.label)
    if args.verify:
        verify(archives, ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

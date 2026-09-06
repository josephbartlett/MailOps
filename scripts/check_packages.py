"""Reject private/runtime files in built wheel and source distribution archives."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def forbidden_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.is_absolute()
        or ".." in path.parts
        or any(part in {".mailops", ".venv", ".git", "__pycache__"} for part in path.parts)
        or path.name == ".env"
        or (path.name.startswith(".env.") and path.name != ".env.example")
        or path.suffix in {".db", ".sqlite", ".sqlite3", ".log", ".pyc"}
        or any(path.name.endswith(extension + tail) for extension in (".db", ".sqlite", ".sqlite3")
               for tail in ("-wal", "-shm", "-journal"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    wheels = list(args.directory.glob("*.whl"))
    sources = list(args.directory.glob("*.tar.gz"))
    if not wheels or not sources:
        parser.error("provide a directory containing both wheel and sdist artifacts")
    errors = []
    for path in sorted(wheels + sources):
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        else:
            with tarfile.open(path) as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                errors.extend(f"{path.name}: archive link {member.name}" for member in members
                              if member.issym() or member.islnk())
        errors.extend(f"{path.name}: forbidden member {name}" for name in names if forbidden_member(name))
        print(f"Checked {path.name}: {len(names)} archive members")
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())

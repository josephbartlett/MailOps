"""Validate repository structure without opening private MailOps state."""

from __future__ import annotations

import ast
import re
import subprocess
from importlib.util import resolve_name
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LAYERS = {
    "core": {"core"},
    "utils": {"utils"},
    "index": {"core", "index", "utils"},
    "adapters": {"core", "index", "adapters", "utils"},
    "agent": {"core", "index", "agent", "utils"},
    "review": {"core", "index", "adapters", "review", "utils"},
    "demo": {"core", "index", "demo", "utils"},
    "cli": {"core", "index", "adapters", "agent", "review", "demo", "cli", "utils"},
}


def check_imports(root: Path) -> list[str]:
    errors = []
    source = root / "src"
    for path in sorted((source / "mailops").rglob("*.py")):
        parts = path.relative_to(source).with_suffix("").parts
        if len(parts) < 3:
            continue
        owner = parts[1]
        if owner not in LAYERS:
            errors.append(f"{path.relative_to(root)}: document the new layer in scripts/check_repo.py")
            continue
        package = ".".join(parts[:-1])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    module = resolve_name("." * node.level + module, package)
                modules = [module] + [f"{module}.{alias.name}" for alias in node.names]
            for module in modules:
                target = module.split(".")
                if len(target) >= 2 and target[0] == "mailops" and target[1] not in LAYERS[owner]:
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: {owner} cannot import {target[1]}; "
                        "move shared data into core or compose the operation in cli/review"
                    )
    return sorted(set(errors))


def check_docs(root: Path) -> list[str]:
    errors = []
    paths = list(root.glob("*.md"))
    for directory in ("docs", "skills", "examples"):
        paths.extend((root / directory).rglob("*.md"))
    for path in paths:
        content = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = target.split(' "', 1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append(f"{path.relative_to(root)}: broken local link {target}")
    agent_map = root / "AGENTS.md"
    if len(agent_map.read_text(encoding="utf-8").splitlines()) > 100:
        errors.append("AGENTS.md: keep the entry map under 100 lines; move detail into linked docs")
    for skill in sorted((root / "skills").iterdir()):
        if skill.is_dir() and not all((skill / name).is_file() for name in ("SKILL.md", "agents/openai.yaml")):
            errors.append(f"skills/{skill.name}: provide SKILL.md and agents/openai.yaml")
    return errors


def check_tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True,
    )
    errors = []
    for raw_path in result.stdout.decode("utf-8").split("\0"):
        if not raw_path:
            continue
        path = Path(raw_path)
        if (
            any(part in {".mailops", ".venv", "__pycache__"} for part in path.parts)
            or path.name == ".env"
            or (path.name.startswith(".env.") and path.name != ".env.example")
            or path.suffix in {".db", ".sqlite", ".sqlite3", ".log", ".pyc"}
            or path.name.endswith((".db-wal", ".db-shm", ".db-journal", ".sqlite-wal", ".sqlite-shm", ".sqlite-journal", ".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal"))
        ):
            errors.append(f"{raw_path}: private/runtime output is tracked; remove it from the candidate")
    return errors


def main() -> int:
    errors = check_imports(ROOT) + check_docs(ROOT) + check_tracked_paths(ROOT)
    package_version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    runtime_version = re.search(r'^__version__ = "([^"]+)"', (ROOT / "src/mailops/__init__.py").read_text(), re.M)
    if not package_version or not runtime_version or package_version[1] != runtime_version[1]:
        errors.append("Version drift: align pyproject.toml and src/mailops/__init__.py")
    for error in errors:
        print(error)
    if errors:
        return 1
    print("Repository checks passed: dependency boundaries, local doc links, skill layout, private paths, versions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Development harness

The harness helps contributors reproduce behavior and improve the product. The
repository is the source of truth: start at [AGENTS.md](../AGENTS.md), follow its
links, implement a bounded change, run checks, and record any remaining limitation.
There is no separate orchestration controller, fixed reviewer panel, task ledger,
or approval ritual for ordinary local development. MailOps' review/apply/audit
workflow is product behavior and remains in place.

This applies [OpenAI's harness-engineering guidance](https://openai.com/index/harness-engineering/)
through a concise agent map, linked local documentation, executable architecture
rules, isolated reproduction, and regression tests for actual failures. The article
describes one team's experiment; it does not override operator authority or this
product's email safety boundaries.

## One local validation command

Use a virtual environment to avoid changing dependencies used by other projects.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/validate.py
```

On Linux/macOS, use `.venv/bin/python` for the same commands.

The runner clears inherited `MAILOPS_*` settings, sets an absolute temporary
`MAILOPS_HOME`, and runs:

1. `python scripts/check_repo.py`: architecture import directions, local Markdown
   links, agent-map length, skill file layout, tracked private paths, version parity.
2. `python -m ruff check src tests scripts`: syntax, undefined names, and unused code.
3. `python -m pytest`: unit, integration, and CLI tests. Every test gets isolated
   settings and temporary state; real socket connections are blocked. Provider
   tests use explicit fakes, never a real mailbox.
4. `python -m mailops.cli.main --help` and a synthetic demo seed/follow-up query.

The runner uses the invoking Python interpreter and stops at the first failure.
It neither applies a pending batch nor reads the repository's `.mailops/` directory.
Individual test runs receive the same isolation from `tests/conftest.py`.

## CI and packaging

[CI](../.github/workflows/ci.yml) runs the validation command on Windows and Linux
at the supported Python endpoints (3.10 and 3.13). It builds wheel/sdist artifacts,
checks package metadata, and audits dependencies. Actions are pinned to immutable
commits; repository permissions are read-only and checkout credentials are not
persisted. CI performs no release or mail operations.

For local packaging verification, use a fresh output directory:

```text
python -m build --outdir dist/audit
python scripts/check_packages.py dist/audit
python -m twine check dist/audit/*
```

Inspect archive members for `.mailops`, `.env`, credentials, SQLite data, logs, and
virtual environments before any release. See [release process](release-process.md).
Dependency audits contact a public advisory service with package names/versions;
they are separate from offline validation and do not upload mailbox data.

Keep the virtual environment's pip current (`python -m pip install --upgrade pip`).
CI also upgrades its preinstalled setuptools to 83.0.0 or newer so older Python
runner images do not retain vulnerable bootstrap tooling.
The development extra requires pytest 9.0.3 or newer to include its temporary-directory
security fix; see the [upstream release notes](https://github.com/pytest-dev/pytest/releases/tag/9.0.3).
Twine 7 supports current metadata 2.5 and requires newer Rich; these compatible
versions are declared together in the project extras/runtime requirements. See
[Twine's changelog](https://twine.readthedocs.io/en/stable/changelog.html).

## Maintenance

Keep [quality.md](quality.md) current when a capability or risk changes. Put
implementation detail in the relevant provider/architecture doc, not in AGENTS.md.
Use additional review where risk warrants it; do not introduce mandatory reviewer
counts or duplicate execution controllers. Convert bugs into focused regressions.
Do not treat passing checks as evidence of live Bridge compatibility or operator
acceptance: record exactly which environments and paths were exercised.

For plugins and installed skill drift, follow [codex-skills.md](codex-skills.md).
Cached/global agent tools are not MailOps runtime dependencies.

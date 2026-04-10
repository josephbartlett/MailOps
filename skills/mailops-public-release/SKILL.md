---
name: mailops-public-release
description: Prepare or verify MailOps public alpha releases, including versioning, packaging, PyPI artifacts, docs, release checklist, security review, demo workflow, and source-control readiness. Use before tagging, pushing, or publishing MailOps v0.1.x.
---

# MailOps Public Release

Use this skill for public alpha release preparation and final release review.

## Release Boundary

MailOps v0.1.x proves the Proton operator loop:

```text
sync -> inspect -> triage -> draft -> review -> apply -> audit
```

Do not broaden release scope by adding Gmail, send, delete, bulk archive, bulk move, or provider rule application.
Do not commit, push, tag, publish, or change remotes unless the operator explicitly approves that exact source-control action.

## Checklist

1. Confirm the directory is the intended Git repository.
2. Read `docs/release-checklist.md`, `docs/public-alpha.md`, `CHANGELOG.md`, `SECURITY.md`, and `README.md`.
3. Confirm versions match in `pyproject.toml` and `src/mailops/__init__.py`.
4. Confirm project URLs point at the real remote origin before publishing.
5. Confirm `.gitignore` excludes `.mailops/`, `.env`, caches, logs, DBs, and build output.
6. Confirm `.env.example` and `examples/config.example.toml` contain no secrets.
7. Confirm release notes state that send, delete, bulk mutation, and provider rule application are not implemented.
8. Confirm `docs/release-process.md` documents SemVer, changelog, GitHub Release, PyPI, and visibility rules.
9. Confirm the GitHub Release has a clear title and markdown body, preferably from `docs/releases/<version>.md`.

## Validation

Run:

```bash
python -m pytest
PYTHONPATH=src python -m mailops.cli.main --help
PYTHONPATH=src python -m mailops.cli.main doctor
PYTHONPATH=src python -m mailops.cli.main status
```

Validate the local-only demo path in a temporary MailOps home:

```powershell
$env:MAILOPS_HOME = "$env:TEMP\mailops-demo-validation"
py -m mailops.cli.main demo seed
py -m mailops.cli.main status
py -m mailops.cli.main search invoice
py -m mailops.cli.main triage --since 0d
Remove-Item Env:MAILOPS_HOME
```

## Package Build

```bash
python -m build
python -m twine check dist/*
```

If `build` or `twine` are missing, install them deliberately and note any dependency conflicts reported by `pip`.

## Secret Scan

Search release-relevant files for temporary Bridge passwords, old versions, and placeholder persisted passwords. Do not print real secrets back to the user.

Examples:

```powershell
Select-String -Path pyproject.toml,src/**/*.py,README.md,docs/**/*.md,examples/**/*,.env.example -SimpleMatch "0.1.0a0"
Select-String -Path examples/config.example.toml -Pattern 'password\\s*=\\s*".+"'
```

## Publish Handoff

After the user provides the remote origin:

1. Initialize or reconnect Git.
2. Add the remote.
3. Update project URLs.
4. Re-run validation and package checks.
5. Commit, tag `v0.1.0`, push, and publish only after final review.

# Release checks

Use [release-process.md](release-process.md) for SemVer and publication rules.
The current release is 0.2.1; use [its notes](releases/v0.2.1.md) for upgrade details.

## Candidate

- Confirm repository, branch, remote, outstanding changes, and existing remote tags.
- Align `pyproject.toml`, `src/mailops/__init__.py`, changelog, release notes, README,
  and the supported-version table. Do not reuse or move an existing release tag.
- Inspect the exact staged file list/diff. Exclude mailbox stores, environment files,
  credentials, logs, databases and sidecars, caches, and temporary artifacts.
- Confirm MIT licensing, real project URLs, secret-free config examples, and the
  unchanged provider safety boundaries.
- Keep the GitHub About description, documentation link, topics, and package
  keywords accurate for shipped capabilities. Check README badges and demo assets;
  social previews must contain public artwork or explicitly synthetic data.
- Confirm operator authorization for the requested commit/push/tag/release actions.
  A GitHub release does not authorize PyPI publication or a visibility change.

## Automated validation

Use the repository virtual environment, following [the harness guide](harness-engineering.md).

```powershell
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit --skip-editable
.\.venv\Scripts\python.exe -m build --outdir dist/release
.\.venv\Scripts\python.exe scripts/check_packages.py dist/release
.\.venv\Scripts\python.exe -m twine check dist/release/*
```

Run commands individually and require each exit code to be zero. The shared runner
uses temporary state and clears inherited mail settings. Inspect the exact wheel
and source archive; smoke-test the wheel itself from an isolated home. Do not seed
a demo into the operational mailbox store. Do not upload old artifacts from other
versions left in `dist/`.

## Provider validation

Live acceptance is separate and optional for a release. If requested, follow the
[Windows runbook](windows-powershell-handoff.md) with an intentional account, bounded
folder/limit, and secure transient credentials. Never apply an existing real batch
as a smoke test. Provider writes require approval of that exact reviewed content.
Record whether validation used fakes, discovery, live reads, or reviewed live drafts.

## Publication

Commit the validated candidate and push its intended branch. Verify CI for that
commit before creating and pushing its annotated SemVer tag. Publish the GitHub
Release using versioned markdown notes and only the inspected matching artifacts.
Verify remote branch/tag SHAs and the release's published state/assets afterward.
GitHub publication does not change or validate an operator's mailbox database.

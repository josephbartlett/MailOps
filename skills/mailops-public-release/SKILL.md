---
name: mailops-public-release
description: Prepare or verify MailOps releases, including versioning, packaging, PyPI artifacts, docs, release checks, and source-control readiness. Use before tagging, pushing, or publishing MailOps.
---

# MailOps Public Release

Use this skill for release preparation and final release review. Read the current repository's `docs/release-process.md` and `docs/release-checklist.md`; they define the maintained procedure.

## Release Boundary

MailOps releases preserve the operator loop:

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
9. Prepare a clear GitHub Release title and markdown body for the selected version, preferably in `docs/releases/<version>.md`. Preparation does not require publishing a release.

## Validation

Run:

```bash
python scripts/validate.py
```

Validate the local-only demo path in a unique temporary MailOps home, restoring any existing environment value even on failure. Use the source tree (`$env:PYTHONPATH = "src"` on PowerShell):

```powershell
$previousMailopsHome = [Environment]::GetEnvironmentVariable("MAILOPS_HOME", "Process")
$demoHome = Join-Path ([IO.Path]::GetTempPath()) ("mailops-demo-" + [guid]::NewGuid())
try {
  $env:MAILOPS_HOME = $demoHome
  py -m mailops.cli.main demo seed
  if ($LASTEXITCODE) { throw "Demo seed failed" }
  py -m mailops.cli.main status
  if ($LASTEXITCODE) { throw "Status failed" }
  py -m mailops.cli.main search invoice
  if ($LASTEXITCODE) { throw "Search failed" }
  py -m mailops.cli.main triage --since 0d
  if ($LASTEXITCODE) { throw "Triage failed" }
} finally {
  [Environment]::SetEnvironmentVariable("MAILOPS_HOME", $previousMailopsHome, "Process")
}
```

`doctor` probes configured Bridge endpoints. Live provider checks are separate from local release validation and should run only when that access is authorized.

## Package Build

```bash
python -m build
python -m twine check dist/*
```

If `build` or `twine` are missing, install them deliberately and note any dependency conflicts reported by `pip`.

## Secret Scan

Search release-relevant files for temporary Bridge passwords, old versions, and placeholder persisted passwords. Do not print real secrets back to the user.

Inspect the actual wheel and source archive file lists as well as tracked source. Confirm private mailbox state, credentials and temporary files are excluded. Report secret findings by file and category without copying the secret. A single password regex is not evidence of a clean release.

## Publish Handoff

Use the repository's existing remote and current release state. Do not initialize Git, reconnect a repository, change remotes, or reuse an old version tag as routine preparation. Complete the changelog, version changes, release notes and artifact validation before requesting any missing permission for the exact publishing action. Honor approval already given for unchanged scope.

When publication is explicitly authorized, use an annotated SemVer tag matching the selected version and create a GitHub Release with a clear title and markdown description as required by `docs/release-process.md`. Do not infer PyPI publication or a visibility change from approval to push a commit or tag.

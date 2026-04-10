# Release Checklist

Use this checklist before tagging and publishing v0.1.0.

## Repository

- [ ] Confirm `C:\Users\decoy\MailOps` is inside the intended Git repository.
- [ ] Add the user-provided remote origin.
- [ ] Update `pyproject.toml` `[project.urls]` with the actual repository, documentation, and issue tracker URLs.
- [ ] Confirm no local-only state is staged: `.mailops/`, caches, logs, and temporary screenshots must stay out of the release.
- [ ] Confirm license ownership is still Joey Bartlett and MIT.

## Version

- [x] `pyproject.toml` version is `0.1.0`.
- [x] `src/mailops/__init__.py` version is `0.1.0`.
- [ ] Create a signed or annotated `v0.1.0` tag after final validation.

## Security

- [ ] Rotate any temporary Proton Bridge password used during development.
- [ ] Confirm no Bridge passwords are present in repo files.
- [ ] Confirm `.env.example` and `examples/config.example.toml` do not contain secrets.
- [ ] Confirm `MAILOPS_REDACT_LOGS=true` remains the default.
- [ ] Confirm release notes state that send, delete, bulk archive, and rule application are not implemented.

## Validation

Run from Windows PowerShell for live Proton checks:

```powershell
py -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
py -m pytest
py -m mailops.cli.main --help
py -m mailops.cli.main doctor
py -m mailops.cli.main status
py -m mailops.cli.main demo seed
py -m mailops.cli.main inspect thread demo-thread-finance
py -m mailops.cli.main draft --help
py -m mailops.cli.main rules propose "filter future messages from vendor.example to label Finance"
```

Optional live Proton validation:

```powershell
$env:MAILOPS_PROTON_PASSWORD = "<bridge-password>"
py -m mailops.cli.main connect proton --profile lm-main --list-folders
py -m mailops.cli.main sync --profile lm-main --folder INBOX --limit 10
py -m mailops.cli.main draft create --from-account <operator@example.com> --to <stakeholder@example.com> --subject "Release validation draft" --body "Draft body" --context-ref release:v0.1.0
py -m mailops.cli.main review batch sync-drafts batch_xxxxxxxx
Remove-Item Env:MAILOPS_PROTON_PASSWORD
```

## Package Build

```powershell
py -m pip install build twine
py -m build
py -m twine check dist/*
```

Inspect the built sdist/wheel before upload.

## Publish

- [ ] Push the release branch.
- [ ] Open a PR or review diff according to the chosen repo process.
- [ ] Merge into the release branch.
- [ ] Push tag `v0.1.0`.
- [ ] Create GitHub release notes from [public-alpha.md](public-alpha.md).
- [ ] Publish the package only after `twine check` passes and project URLs are correct.

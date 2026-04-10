# Release Checklist

Use this checklist before tagging and publishing a MailOps release. See [release-process.md](release-process.md) for SemVer, changelog, GitHub Release, PyPI, and repository visibility rules.

## Repository

- [ ] Confirm `C:\Users\decoy\MailOps` is inside the intended Git repository.
- [ ] Confirm the remote origin is `https://github.com/josephbartlett/MailOps`.
- [ ] Update `pyproject.toml` `[project.urls]` with the actual repository, documentation, and issue tracker URLs.
- [ ] Confirm no local-only state is staged: `.mailops/`, caches, logs, and temporary screenshots must stay out of the release.
- [ ] Confirm license ownership is still Joey Bartlett and MIT.
- [ ] Do not commit, push, tag, publish, or change remotes unless the operator explicitly approves that exact source-control action.

## Version

- [x] `pyproject.toml` version is `0.1.0`.
- [x] `src/mailops/__init__.py` version is `0.1.0`.
- [x] `CHANGELOG.md` includes `0.1.0` and uses SemVer release history.
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
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
py -m mailops.cli.main connect proton --profile lm-main --list-folders
py -m mailops.cli.main sync --profile lm-main --folder INBOX --limit 10
py -m mailops.cli.main draft create --from-account <operator@example.com> --to <stakeholder@example.com> --subject "Release validation draft" --body "Draft body" --context-ref release:v0.1.0
py -m mailops.cli.main review batch show batch_xxxxxxxx
py -m mailops.cli.main apply batch_xxxxxxxx
py -m mailops.cli.main review batch sync-drafts batch_xxxxxxxx
Remove-Item Env:MAILOPS_PROTON_PASSWORD
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
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
- [ ] Push tag `v0.1.0`.
- [ ] Create a GitHub Release named `MailOps v0.1.0: Public Alpha` with markdown notes from [releases/v0.1.0.md](releases/v0.1.0.md).
- [ ] Make the GitHub repository public only after security, license, changelog, and release docs are present.
- [ ] Publish the package only after `twine check` passes, project URLs are correct, and PyPI credentials or trusted publishing are configured locally.

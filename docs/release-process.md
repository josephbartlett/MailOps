# Release Process

MailOps releases follow Semantic Versioning and keep the operator loop narrow:

```text
sync -> inspect -> triage -> draft -> review -> apply -> audit
```

## Versioning

Use SemVer version numbers: `MAJOR.MINOR.PATCH`.

For `0.x` public alpha releases:

- Increment `MINOR` for new user-visible workflows, provider capabilities, schema changes, or policy behavior.
- Increment `PATCH` for compatible bug fixes, documentation fixes, packaging fixes, and test-only hardening.
- Use prerelease identifiers such as `0.2.0-rc.1` only for release candidates that should not be treated as final.
- Keep `pyproject.toml` and `src/mailops/__init__.py` on the same version.

Do not broaden release scope by adding send, delete, bulk mutation, provider rule application, or Gmail runtime behavior without explicit policy and review gates.

## Changelog

Maintain `CHANGELOG.md` for every release. Keep an `Unreleased` section at the top, then one section per version with the release date.

Use these headings when relevant:

- `Added`
- `Changed`
- `Fixed`
- `Security`
- `Safety Boundaries`

Release notes can summarize the changelog, but the changelog is the source of truth for version history.

## Release Checklist

Before tagging:

1. Confirm the working tree contains only intended release changes.
2. Confirm no `.mailops/`, `.env`, logs, local databases, credentials, or temporary screenshots are staged.
3. Confirm the version is updated in `pyproject.toml` and `src/mailops/__init__.py`.
4. Confirm `CHANGELOG.md` has an entry for the target version.
5. Run the validation commands in `docs/release-checklist.md`.
6. Build artifacts with `py -m build`.
7. Check artifacts with `py -m twine check dist\*`.

Only commit, push, tag, publish, or change repository visibility after the operator explicitly approves that exact action.

## Tagging

Use annotated tags for final releases:

```powershell
git tag -a v0.1.0 -m "MailOps v0.1.0"
git push origin v0.1.0
```

If a pushed tag must move before a public release exists, state that clearly and get operator approval first. Prefer a new patch release over retagging once a release is public.

## GitHub Release

Use a clear title and markdown description. For v0.1.0, use:

```text
MailOps v0.1.0: Public Alpha
```

The release body should include:

- a short summary of the release
- what works
- safety boundaries
- installation or validation notes
- known limitations
- links to `CHANGELOG.md`, `docs/public-alpha.md`, and `docs/release-checklist.md`

Store reusable release notes under `docs/releases/`.

## PyPI

Publish to PyPI only after:

- `py -m twine check dist\*` passes
- project URLs point to the public repository
- a PyPI token or trusted publishing configuration is already available locally
- the operator has explicitly approved package publication

Do not paste PyPI tokens into chat, docs, shell history, or logs.

## Repository Visibility

Make the GitHub repository public only after the release checklist passes and the operator approves public visibility. Confirm `SECURITY.md`, `LICENSE`, `CHANGELOG.md`, and public alpha docs are present before switching visibility.

# Codex Skills

MailOps includes repo-local Codex Skills under `skills/` so contributors can reuse the same operating guidance that shaped the project.

These skills are intentionally narrow. Operator-facing skills:

- `mailops-email-context`: find, inspect, and summarize MailOps-indexed email from any Codex repo or session.
- `mailops-contextual-draft`: draft email or reply text using current repo/session context plus optional MailOps email context, then create a review-first custom draft batch when approved.
- `mailops-draft-review`: inspect, apply, reconcile, and audit MailOps draft batches without sending mail.

Contributor-facing skills:

- `mailops-product-development`: develop MailOps code while preserving the local-first, provider-aware, review-first product boundary.
- `mailops-proton-validation`: validate Proton Bridge workflows without persisting credentials or sending mail.
- `mailops-public-release`: prepare and verify public alpha releases.

Each skill is a standard Codex skill folder with:

```text
skills/<skill-name>/
├── SKILL.md
└── agents/openai.yaml
```

## Install Locally

To make the skills available from every repository on a Windows machine, copy the skill folders into the global Codex skills directory:

```powershell
$repoSkills = Resolve-Path .\skills
$globalSkills = Join-Path $env:USERPROFILE ".codex\skills"
$skillNames = @(
  "mailops-email-context",
  "mailops-contextual-draft",
  "mailops-draft-review",
  "mailops-product-development",
  "mailops-proton-validation",
  "mailops-public-release"
)

New-Item -ItemType Directory -Force -Path $globalSkills | Out-Null
$resolvedGlobal = Resolve-Path $globalSkills

foreach ($name in $skillNames) {
  $source = Join-Path $repoSkills.Path $name
  $target = Join-Path $resolvedGlobal.Path $name
  $targetFullPath = [System.IO.Path]::GetFullPath($target)

  if (-not $targetFullPath.StartsWith($resolvedGlobal.Path)) {
    throw "Refusing to install skill outside $($resolvedGlobal.Path): $targetFullPath"
  }

  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }

  Copy-Item -LiteralPath $source -Destination $target -Recurse
}
```

On other systems, install into `$CODEX_HOME/skills` when `CODEX_HOME` is set, or `~/.codex/skills` otherwise.

## Validate

Use Codex's skill validator after editing a skill:

```powershell
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-product-development
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-proton-validation
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-public-release
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-email-context
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-contextual-draft
py $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mailops-draft-review
```

Keep skill content concise. Put essential operating rules in `SKILL.md`, and only add bundled references or scripts when they remove repeated, error-prone work.

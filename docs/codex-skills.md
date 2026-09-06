# Codex Skills

MailOps includes repo-local Codex skills under `skills/`. These checked-in files are the source of truth; global installations are copies that must be refreshed after a skill changes.

These skills are intentionally narrow. Operator-facing skills:

- `mailops-email-context`: find, inspect, and summarize MailOps-indexed email from any Codex repo or session.
- `mailops-contextual-draft`: draft email or reply text using current repo/session context plus optional MailOps email context, then create a local custom draft batch when requested.
- `mailops-draft-review`: inspect, apply, reconcile, and audit MailOps draft batches without sending mail.

Contributor-facing skills:

- `mailops-product-development`: develop MailOps code while preserving the local-first, provider-aware, review-first product boundary.
- `mailops-proton-validation`: validate Proton Bridge workflows without persisting credentials or sending mail.
- `mailops-public-release`: prepare and verify releases using the current release process.

Each skill is a standard Codex skill folder with:

```text
skills/<skill-name>/
├── SKILL.md
└── agents/openai.yaml
```

These are workflow guides, not an orchestration controller. They do not require fixed agent teams, reviewer rounds, custody packets or a separate approval framework. MailOps' draft review/apply boundary is product behavior: it keeps provider mutations attached to the operator's exact approved draft.

## Accounts, State and Plugins

`MAILOPS_HOME` defaults to `.mailops` relative to the working directory. Before using an operator skill from another repo, resolve the intended existing absolute home and verify the account. Even a local `status` command initializes a missing store, so an empty new store is not evidence of an empty mailbox. Development and demo checks should use unique temporary homes and restore the previous environment afterward.

The skills use the MailOps CLI and do not depend on a MailOps MCP server or a dedicated plugin. A separately installed Gmail connector is a separate provider workflow; it does not implement MailOps' placeholder Gmail adapter or inherit approval to read or mutate a MailOps account. GitHub and document plugins may help with explicitly requested release or writing tasks, but installing these skills grants no external-action authority.

## Install Locally

To make the skills available from every repository on a Windows machine, copy the skill folders into the global Codex skills directory:

```powershell
$repoSkills = Resolve-Path .\skills
$codexSkillsRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$globalSkills = Join-Path $codexSkillsRoot "skills"
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
  $targetAgents = Join-Path $target "agents"
  foreach ($directory in @($target, $targetAgents)) {
    if ((Test-Path -LiteralPath $directory) -and
        ((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
      throw "Inspect the linked destination before installing: $directory"
    }
  }
  New-Item -ItemType Directory -Force -Path $targetAgents | Out-Null
  foreach ($relativeFile in @("SKILL.md", "agents\openai.yaml")) {
    $destination = Join-Path $target $relativeFile
    if ((Test-Path -LiteralPath $destination) -and
        ((Get-Item -LiteralPath $destination -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
      throw "Inspect the linked file before installing: $destination"
    }
    Copy-Item -LiteralPath (Join-Path $source $relativeFile) -Destination $destination -Force
  }
}
```

This updates the two maintained files in each skill without recursively deleting an installed folder. Review any locally customized or extra installed files before replacing or removing them. On other systems, install into `$CODEX_HOME/skills` when `CODEX_HOME` is set, or `~/.codex/skills` otherwise. Codex may need a new task or restart to reload changed skills.

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

Check that command names and flags still match the current CLI using the command's `--help`. Compare repository and installed files after installation:

```powershell
foreach ($name in $skillNames) {
  foreach ($relativeFile in @("SKILL.md", "agents\openai.yaml")) {
    $sourceHash = (Get-FileHash -LiteralPath (Join-Path (Join-Path $repoSkills.Path $name) $relativeFile)).Hash
    $installedHash = (Get-FileHash -LiteralPath (Join-Path (Join-Path $resolvedGlobal.Path $name) $relativeFile)).Hash
    if ($sourceHash -ne $installedHash) { throw "Installed skill differs: $name/$relativeFile" }
  }
}
```

Keep skill content concise. Put essential operating rules in `SKILL.md`, and only add bundled references or scripts when they remove repeated, error-prone work. Validators check structure; command and scenario checks establish whether a skill is operationally useful. See [harness-engineering.md](harness-engineering.md) for repository validation and maintenance.

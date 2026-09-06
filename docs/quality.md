# Quality and audit status

Last reviewed: 2026-09-05 (America/New_York). This records the local repository and
agent-harness audit, not a release certification or a live mailbox acceptance test.

## Audit scope and disposition

Reviewed runtime code, SQLite bootstrap/migrations, provider boundaries, CLI flows,
tests, packaging, repository instructions, all six maintained skills and installed
copies, relevant local plugin configuration, Git hooks, and MailOps automation
references. No active ATTUNE, custody-first controller, fixed reviewer panel, or
legacy orchestration system was found in this scope. Default sample Git hooks were
inactive and no custom hook path or MailOps automation was found. Removed the unused
`scripts/seed_demo_data.py` placeholder; the supported demo is `mailops demo seed`.

The product's review/apply/audit controls remain active. A Codex global approval
review setting is app configuration, not a repository reviewer controller. Global
Gmail, GitHub, calendar, browser, and artifact integrations are separate capabilities;
no MailOps-specific plugin/MCP dependency was found. No unrelated global integration
or permission settings were changed.

Read-only permission inspection confirmed Gmail and GitHub inherit the app default
of allowing low-risk actions. This is the app approval setting, not an audit of
provider OAuth scopes; it does not supersede MailOps' explicit-action rules.

## Corrected findings

| Area | Finding and implemented correction |
| --- | --- |
| Account isolation | Global Message-ID uniqueness could overwrite mail across accounts. Identity is now account-scoped, with transactional migration preserving stored IDs and content. |
| Sync correctness | Cursors lacked UIDVALIDITY; FETCH identity/range handling could index wrong or repeated messages. Epoch-bound cursors, UID validation, bounded resets, and PEEK fetches now have regressions. |
| Draft review | Generated recipients were resolved later at apply. Proposals now freeze account/recipient/reply context; legacy empty envelopes require recreation and review. |
| Policy | Caller-supplied risk could understate a mutation. Action-type risk floors and per-action approval checks now enforce the boundary. |
| Draft retries | Concurrent apply, crashes, or missing receipts could duplicate provider drafts. Durable claims, per-action commits, and explicit uncertainty block unsafe retries and rollback. |
| Draft reconciliation | Old UID-only refs could match unrelated drafts after a mailbox reset. New refs bind UIDVALIDITY and Message-ID; legacy UID-only refs are explicitly unverified. |
| Account targeting | Reviewed account and selected Bridge profile are checked together before provider execution. |
| Config/logging | Handwritten TOML parsing broke quoted values; auth tails and traceback secrets could leak. Standard TOML parsing, validation, sanitized provider errors, and final-output redaction replace those paths. |
| Review display | Rich markup could conceal or restyle untrusted mail, and control characters could spoof terminal output. Literal rendering and visible control-character escapes now preserve review visibility. |
| Resource lifetime | SQLite/log handles could remain attached to prior state. Connections close on context exit and logging rebinds to the active home. |
| Tests/demo | Fixed April dates broke recent-message scenarios. Relative demo dates and time-independent fixtures repair the failures; tests clear inherited settings and block real sockets. |
| Harness | No CI or shared validation command. Added architecture/doc/private-path/version checks, focused lint, temporary-state validation, packaging checks, and Windows/Linux CI. |
| Skills | Cross-repo commands could silently open a new empty store; profiles, passwords, installation, and release guidance had drifted. All six skills now require deliberate state/account targeting and installed copies were synchronized. |
| Dependencies | The old pytest upper bound prevented its security fix. Raised the floor to 9.0.3, and upgraded pip in the isolated development environment. |
| Packaging compatibility | Current Hatchling emits metadata 2.5, rejected by Twine 6. Updated to Twine 7 and its compatible Rich requirement. |

## Evidence

Baseline: 3 failed, 77 passed on Windows Python 3.13.3. All three failures involved
old dates falling outside current lookback windows.

Final evidence on Windows Python 3.13.3, in the repository's isolated `.venv`:

- `python scripts/validate.py`: passed, including **140 tests in 14.94 seconds**,
  architecture/doc/private-path/version checks, Ruff, CLI help, demo seeding, and
  the synthetic finance follow-up query.
- `connect proton`: discovery-only smoke passed in a temporary home without
  credentials. This did not list folders, sync mail, or exercise a live login.
- `pip-audit --skip-editable`: **57 resolved packages, no known vulnerabilities**
  after updating the isolated tooling. This is a point-in-time advisory result,
  not a claim that every version permitted by dependency bounds is safe.
- `pip check`: no broken requirements. Packaging uses Twine 7 with Rich 15 and
  current metadata support; build output is local and unreleased.
- Wheel/sdist build, archive-member inspection, and `twine check`: passed.
- All six repository skills and six installed copies validated; 12 maintained
  files match. Seventeen CLI-help/flag checks and four isolated skill demo commands
  passed. No obsolete extra files were found in the installed MailOps skill folders.
- Git whitespace checks passed. Source-file scanning found no high-confidence
  private-key/GitHub/OpenAI token signatures; filenames and archives were checked
  for private runtime artifacts without opening operator mail state.
- CI YAML parsed and four OS/Python combinations are configured. Remote CI was
  not run during the initial audit; release validation is linked from the
  [v0.2.0 release notes](releases/v0.2.0.md).

The initial audit updated the source checkout and installed MailOps skill copies
locally, without changing operational mail, provider state, global plugin
configuration, or release state. The subsequent operator-authorized release is
0.2.0. Operational migration and live acceptance remain separate steps.

## Remaining limitations

| Limitation | Operational implication / next work |
| --- | --- |
| Live Bridge acceptance is untested in this audit | All mail behavior tests use fakes. Validate an intentionally selected account and bounded scope before relying on a new version operationally. |
| Operational database was not opened or migrated | Back up the established store before its first command under this schema-changing version. Tests cover synthetic legacy migrations. Already overwritten historical mail cannot be reconstructed by migration. |
| Ambiguous provider writes need recovery | `executing`/`uncertain` actions block retry and rollback. Inspect Proton Drafts and audit history; an automated verified recovery workflow remains future work. |
| Legacy UID-only draft refs | They remain stored but cannot prove draft identity. Syncback reports them unverified rather than associating unrelated provider content. |
| Threading/triage are heuristics | Headers and normalized subjects can misgroup conversations; classifications are suggestions for operator inspection. |
| Sync is an indexed snapshot | Bounded initial sync intentionally omits old mail; existing flags/deletions are not a complete continuously reconciled mirror. |
| Storage and Bridge trust | State/exports are plaintext; host permissions, encryption, and backups are external responsibilities. Bridge plaintext/local-certificate topology is not a hardened remote transport. |
| Gmail and risky mutations | Gmail runtime, send/delete, bulk mail mutation, and provider-rule application remain unimplemented. |
| Dependency resolution and supported platforms | Dependencies resolve within bounds, not a lockfile. CI matrix is defined; local checks do not prove every Python/OS combination. |

These limitations are tracked work, not reasons to add orchestration ceremonies.
Update this document when behavior or verification changes, alongside the relevant
provider doc and regression tests. Use [the harness guide](harness-engineering.md)
for repeatable checks and [the roadmap](roadmap.md) for product priorities.

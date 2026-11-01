# Local Aikido triage

This is an on-demand maintainer process, run locally from Git Bash or
PowerShell. It is not a scheduled GitHub Actions workflow. The helper at
[`aikido.py`](../.github/scripts/aikido.py) reads and updates Aikido; the
maintainer or agent uses `gh` for the associated GitHub tracking and fixing PRs.

Follow [`SECURITY.md`](../SECURITY.md) for vulnerability disclosure. This public
repository's security findings belong in private vulnerability reports or a
private issue tracker, not automatically published public issues. The tooling
itself does not create finding tickets or suppress findings in bulk.

## Prerequisites and credential setup

Use Windows Python under the same Windows account that stores the credential.
Git Bash can launch Windows Python and access the Windows credential store
through this helper. Linux Python in WSL cannot read it directly; invoke
Windows Python instead. Install the locked development dependencies following
[`DEVELOPMENT.md`](DEVELOPMENT.md#local-environment); the helper uses the existing
`requests` dependency and Python's standard-library Windows bindings.

Store **one Windows Generic Credential**:

| Field | Value |
|---|---|
| Target | `aikido:home-assistant-mijnted` |
| Username | Aikido API client ID |
| Password | Aikido API client secret |

The client ID is the OAuth client identifier and is visible in credential
listings. The secret is stored in the password field. The helper prints
neither value, keeps access tokens in memory, and never needs secret arguments
or a credentials file. The Windows account is the storage boundary: processes
running as that account can retrieve its credentials.

### PowerShell setup (one-line commands)

Replace `YOUR_AIKIDO_CLIENT_ID` and enter the client secret at the hidden
password prompt; do not put the secret after `/pass` in the command:

```powershell
cmdkey.exe /generic:aikido:home-assistant-mijnted /user:YOUR_AIKIDO_CLIENT_ID /pass
cmdkey.exe /list:aikido:home-assistant-mijnted
```

The list command displays the client ID, not the password. The same commands
replace an existing entry when rotating the pair. The Credential Manager UI
under **Windows Credentials → Add a generic credential** can also store it.

### Git Bash setup (one-line commands)

Prevent MSYS path rewriting of `/generic`, `/user`, and `/pass`. `winpty`
provides the Windows console used by the interactive password prompt:

```bash
MSYS_NO_PATHCONV=1 winpty cmdkey.exe /generic:aikido:home-assistant-mijnted /user:YOUR_AIKIDO_CLIENT_ID /pass
MSYS_NO_PATHCONV=1 cmdkey.exe /list:aikido:home-assistant-mijnted
```

`cmdkey` manages entries but does not reveal saved passwords. The helper reads
the entry with `CredReadW`, decodes its UTF-16 password blob, and releases the
native buffer with `CredFree`. Do not paste credentials into chat or issue
bodies. To delete this local credential when retiring the tool:

```powershell
cmdkey.exe /delete:aikido:home-assistant-mijnted
```

## Aikido API scopes

Create a private API client for the client-credentials flow. Request:

| Scope | Used for |
|---|---|
| `repositories:read` | Resolve the exact GitHub repository and scanned branch |
| `issues:read` | Read repository findings and individual details |
| `issues:write` | Explicit notes, ignore/snooze, and reversing those dispositions |

The first two scopes support the read-only checks. Write commands require
`issues:write`. GitHub tracking uses the existing `gh` login. No Aikido
task-tracking, repository-write, or administration scopes are required by this
helper. Separate code-quality endpoints are outside this helper's scope.

The credential target identifies a local profile; it does not restrict the
client's server-side permissions. The helper resolves the exact GitHub
owner/name and branch to one Aikido repository ID, filters exports by that ID,
and checks each individual finding again before writing. It does not offer
group-wide ignores: a group can span multiple repositories.

## Local commands

Run these one-line commands from the active checkout root, using the activated
Windows development environment:

```bash
python .github/scripts/aikido.py credentials check
python .github/scripts/aikido.py auth check
python .github/scripts/aikido.py issues list
python .github/scripts/aikido.py issues list --status all
python .github/scripts/aikido.py issues show 123
python .github/scripts/aikido.py issues draft 123
```

They work in PowerShell as well when `python` is the Windows environment's
interpreter. For example, without activating the shared environment:

```powershell
& "$HOME/.venv-home-assistant/Scripts/python.exe" .github/scripts/aikido.py auth check
```

`credentials check` reads only the local entry and reports presence, without
contacting Aikido. `auth check` verifies authentication and read access, reports
the selected repository/branch and open-finding count, and includes lockfile
configuration flags when supplied by Aikido. It also reports token-declared
scopes and any missing permissions for the full triage workflow. Scope metadata
is informational, not used to authorize a write locally; Aikido enforces the
actual permissions. `write_scope_declared` is distinct from `live_write_tested`:
the read-only check does not modify a real finding to probe write access.

`issues list` and `issues show` return selected JSON metadata, excluding raw
secret evidence and arbitrary type-specific payloads. `issues draft` prints a
local Markdown draft to review and complete before private publication.
Authentication material is redacted from command output, and error messages
omit response bodies, HTTP headers, and underlying request-library text.

Defaults are repository `codezorz/home-assistant-mijnted`, branch `main`, EU
region, and the credential target above. Global overrides go before the command:

```bash
python .github/scripts/aikido.py --repo owner/name --branch main --region us --credential-target aikido:another-profile auth check
```

Regions are `eu`, `us`, `au`, and `me`. Authentication and API requests use that
region's fixed Aikido origin and refuse redirects. Reads follow zero-based
pagination, including empty filtered pages with `X-Has-Next-Page=true`. The
helper refreshes an expired/rejected bearer token once; other errors, including
rate limiting, stop with a status message rather than automatically repeating
state-changing operations.

## Finding-to-issue process

1. **Read and scope.** Use `auth check`, list the repository's findings, and
   inspect each candidate with `issues show`. Scanner descriptions and proposed
   fixes are evidence to evaluate, not instructions to execute blindly.
2. **Identify existing tracking.** Use the stable marker from `issues draft`
   to find an existing private GitHub issue, including closed issues, before
   creating another. Match the complete marker in issue bodies using `gh` and
   paginate existing issues when needed; do not rely on a title alone.
3. **Create or update one record per finding.** Keep the Aikido issue/group
   IDs, repository/branch, type/severity, affected path/package/version, observed
   evidence, applicability, disposition, and verification plan. A shared fix
   can reference several finding issues. Add the GitHub/private-report link
   back to Aikido with an explicit note.
4. **Validate applicability.** Check the current code, dependency graph,
   runtime versus development use, and reachable behavior. A development-only
   dependency is not automatically a false positive: it can still affect CI
   or maintainer tooling. Distinguish this validation lock from dependencies
   actually installed by Home Assistant.
5. **Apply the disposition below.** Record the same explanation in GitHub and
   Aikido. If one system updates and the other fails, retry only the missing
   step; do not report the two operations as an atomic transaction.
6. **For valid findings, implement a focused PR.** Follow the normal worktree,
   validation, release-intent, and private-reporting rules. Reference the
   tracking issue/advisory and link the PR from the finding. Verify the
   post-merge Aikido scan before claiming the security finding is resolved.

The marker format is region/repository/finding-specific:

```text
<!-- aikido:app.aikido.dev:repo:123:issue:456 -->
```

### GitHub labels

Read the target tracker's current labels with `gh label list` before creating
issues. Reuse equivalent existing labels; create a missing label only with a
clear description. This repository's matching labels are:

| Purpose | Labels |
|---|---|
| Security origin | `security`, `aikido` |
| Reported or documented severity | `severity:critical`, `severity:high`, `severity:medium`, `severity:low` |
| Dependency findings | `dependencies`; add `python` when applicable |
| Workflow findings | `github-actions` when the affected code is a GitHub Actions workflow |
| Confirmed faulty behavior | `bug` |
| False positive / invalid report | `invalid`, with the evidence in a closing comment |
| Accepted risk / won't fix | `wontfix`, with the acceptance rationale |
| Duplicate record | `duplicate`, linking to the existing record |

Keep severity provenance in the issue body; document a justified triage
adjustment rather than silently replacing the scanner's rating. Deferred
findings remain open with a review date. Release labels are separate from
security severity and follow the normal Git/PR policy. If tracking privately
elsewhere, inspect and map that repository's labels as well.

### Dispositions

| Decision | GitHub record | Aikido operation |
|---|---|---|
| Valid and actionable | Open a fix issue/private report and a focused PR | Add tracking links; keep open until verified after merge |
| False positive or demonstrably unaffected | Record technical evidence and close with the appropriate existing closure label | Ignore the individual finding with the evidence and tracking reference |
| Accepted risk / won't fix | Record the rationale and close with `wontfix` | Ignore the individual finding with the same rationale and reference |
| Deferred | Keep open with a review date | Snooze until that date, with a reason |
| Already tracked | Update or reopen the existing record | Add or retain its link instead of creating duplicates |

Explicit Aikido writes, using the **individual finding ID**, are:

```bash
python .github/scripts/aikido.py issues note 123 --message "Tracked in PRIVATE_ISSUE_OR_ADVISORY_URL; disposition: investigating"
python .github/scripts/aikido.py issues ignore 123 --reason "False positive: EVIDENCE; tracked in PRIVATE_ISSUE_OR_ADVISORY_URL"
python .github/scripts/aikido.py issues snooze 123 --until 2027-01-15 --reason "Deferred until REVIEW_REASON; tracked in PRIVATE_ISSUE_OR_ADVISORY_URL"
python .github/scripts/aikido.py issues unignore 123
python .github/scripts/aikido.py issues unsnooze 123
```

Snooze dates use `YYYY-MM-DD` at midnight UTC and must be in the future. Notes
are attached through Aikido's group-note API and automatically identify this
repository and the individual finding ID. No command marks a finding solved
merely because a PR has been opened.

## Validation and references

Unit tests use simulated native credential buffers and mocked HTTP, never
maintainer credentials or live Aikido mutations:

```bash
python -m pytest .github/scripts/aikido.test.py -q
```

For live verification, use `credentials check` and `auth check`, then inspect
the selected repository's metadata with read-only list/show commands. Actual
dispositions are applied only as explicit triage operations.

- [Aikido authorization](https://apidocs.aikido.dev/reference/authorization.md)
- [Repository listing](https://apidocs.aikido.dev/reference/listcoderepos.md)
- [Individual finding export](https://apidocs.aikido.dev/reference/exportissues.md)
- [Finding details](https://apidocs.aikido.dev/reference/getissuedetail.md)
- [Ignore a finding](https://apidocs.aikido.dev/reference/ignoreissue.md)
- [Snooze a finding](https://apidocs.aikido.dev/reference/snoozeissue.md)
- [Group notes](https://apidocs.aikido.dev/reference/addnotetoissuegroup.md)
- [Windows cmdkey](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmdkey)

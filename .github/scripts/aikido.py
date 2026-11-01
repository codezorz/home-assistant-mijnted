"""Run local, repository-scoped Aikido triage using Windows Credential Manager."""

import argparse
import base64
import binascii
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
import re
import sys
import time
from urllib.parse import urlparse

import requests


DEFAULT_REPOSITORY = "codezorz/home-assistant-mijnted"
DEFAULT_CREDENTIAL = "aikido:home-assistant-mijnted"
REGIONS = {
    "eu": "https://app.aikido.dev",
    "us": "https://app.us.aikido.dev",
    "au": "https://app.au.aikido.dev",
    "me": "https://app.me.aikido.dev",
}
PAGE_SIZE = 100
TIMEOUT = 30
CRED_TYPE_GENERIC = 1
TRIAGE_SCOPES = {"repositories:read", "issues:read", "issues:write"}


class AikidoError(Exception):
    """A credential-safe error suitable for command-line output."""


@dataclass
class Credentials:
    """Keep the credential pair out of object representations."""

    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)


class _CredentialAttribute(ctypes.Structure):
    """Native CREDENTIAL_ATTRIBUTEW layout."""

    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(wintypes.BYTE)),
    ]


class _Credential(ctypes.Structure):
    """Native CREDENTIALW layout, including the byte-sized credential blob."""

    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.POINTER(_CredentialAttribute)),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def read_credentials(target: str, *, api=None) -> Credentials:
    """Read the client ID from the username and client secret from the password."""
    if api is None:
        if sys.platform != "win32":
            raise AikidoError("Use Windows Python from Git Bash or PowerShell to access Credential Manager.")
        try:
            api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        except OSError:
            raise AikidoError("Windows Credential Manager is unavailable in this process.") from None
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(_Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    credentials = _read_entry(target, api)
    if not credentials.client_id:
        raise AikidoError("The single credential entry needs the client ID in its username field.")
    return credentials


def _read_entry(target: str, api) -> Credentials:
    """Decode a native entry and always release its Credential Manager buffer."""
    pointer = ctypes.POINTER(_Credential)()
    if not api.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        raise AikidoError(f"Cannot read Generic Credential '{target}'. Check the target and Windows user; see .agents/skills/aikido-triage/references/aikido.md.")
    try:
        credential = pointer.contents
        if not credential.CredentialBlobSize or not credential.CredentialBlob:
            raise AikidoError("A Generic Credential entry has an empty password value.")
        try:
            secret = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize).decode("utf-16-le")
        except UnicodeError:
            raise AikidoError("The credential password is not valid UTF-16; recreate it using cmdkey or Credential Manager.") from None
        secret = secret.rstrip("\x00")
        if not secret:
            raise AikidoError("The Generic Credential password is empty.")
        return Credentials(credential.UserName or "", secret)
    finally:
        api.CredFree(pointer)


def positive_id(value) -> int:
    """Normalize numeric IDs without allowing path components or booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"[0-9]+", str(value)):
        raise AikidoError("Expected a positive numeric Aikido ID.")
    number = int(value)
    if number <= 0:
        raise AikidoError("Expected a positive numeric Aikido ID.")
    return number


def github_repository(record: dict) -> str | None:
    """Identify a GitHub repository from its provider URL or explicit owner/name."""
    if record.get("provider") != "github":
        return None
    if record.get("url"):
        try:
            url = urlparse(record["url"])
        except ValueError:
            return None
        path = url.path.rstrip("/").removesuffix(".git")
        if url.hostname == "api.github.com" and path.startswith("/repos/"):
            path = path[len("/repos"):]
        elif url.hostname != "github.com":
            return None
        name = path.lstrip("/")
    else:
        name = str(record.get("name", ""))
        if "/" not in name and record.get("project"):
            name = f"{record['project']}/{name}"
    return name.casefold() if re.fullmatch(r"[\w.-]+/[\w.-]+", name, re.ASCII) else None


class AikidoClient:
    """Keep authentication in-process and enforce the selected repository on writes."""

    def __init__(self, credentials: Credentials, session, *, repository=DEFAULT_REPOSITORY, branch="main", region="eu"):
        """Initialize one regional API client for an exact GitHub repository/branch."""
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository, re.ASCII):
            raise AikidoError("Repository must have the form owner/name.")
        self.credentials = credentials
        self.session = session
        self.origin = REGIONS[region]
        self.repository_name = repository
        self.branch = branch
        self._repository = None
        self._token = ""
        self._token_scope = None
        self._expires_at = 0
        basic = base64.b64encode(f"{credentials.client_id}:{credentials.client_secret}".encode()).decode()
        self._sensitive = {credentials.client_id, credentials.client_secret, basic}

    def redact(self, value):
        """Remove authentication material from the selected command output."""
        if isinstance(value, str):
            for secret in sorted(self._sensitive, key=len, reverse=True):
                if secret:
                    value = value.replace(secret, "[redacted]")
            return value
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, dict):
            return {self.redact(key): self.redact(item) for key, item in value.items()}
        return value

    def _send(self, method: str, path: str, **kwargs):
        """Send only to the selected Aikido origin and never forward redirects."""
        try:
            return self.session.request(method, self.origin + path, timeout=TIMEOUT,
                                        allow_redirects=False, **kwargs)
        except requests.RequestException as error:
            raise AikidoError(f"Aikido connection failed ({type(error).__name__}).") from None

    @staticmethod
    def _payload(response):
        """Validate status/JSON without exposing response bodies or auth errors."""
        if not 200 <= response.status_code < 300:
            hint = " Check the client's API scopes." if response.status_code == 403 else ""
            raise AikidoError(f"Aikido request failed (HTTP {response.status_code}).{hint}")
        if response.status_code == 204:
            return {}
        try:
            payload = response.json()
        except ValueError:
            raise AikidoError("Aikido returned invalid JSON.") from None
        if not isinstance(payload, (dict, list)):
            raise AikidoError("Aikido returned an unexpected response format.")
        return payload

    def _authenticate(self):
        """Exchange the stored pair for an in-memory, short-lived access token."""
        if self._token and time.monotonic() < self._expires_at:
            return
        response = self._send("POST", "/api/oauth/token",
                              auth=(self.credentials.client_id, self.credentials.client_secret),
                              data={"grant_type": "client_credentials"})
        payload = self._payload(response)
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise AikidoError("Aikido did not return an access token.")
        self._sensitive.add(token)
        self._token = token
        try:
            lifetime = int(payload.get("expires_in", 300))
        except (ValueError, TypeError):
            raise AikidoError("Aikido returned an invalid token lifetime.") from None
        self._expires_at = time.monotonic() + max(0, lifetime - 30)
        self._token_scope = payload.get("scope")

    def declared_scopes(self) -> list[str] | None:
        """Read scope metadata from the TLS-issued token, without using it to authorize writes."""
        self._authenticate()
        value = self._token_scope
        if value is None:
            parts = self._token.split(".")
            if len(parts) != 3:
                return None
            try:
                claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
            except (ValueError, UnicodeError, binascii.Error):
                return None
            if not isinstance(claims, dict):
                return None
            value = claims.get("scope", claims.get("scopes"))
        values = value.split() if isinstance(value, str) else value if isinstance(value, list) else None
        if values is None:
            return None
        return sorted({item for item in values if isinstance(item, str)
                       and re.fullmatch(r"[a-z_]+:(?:read|write)", item)})

    def request(self, method: str, path: str, **kwargs):
        """Refresh once on a 401; avoid automatically retrying other writes."""
        for attempt in range(2):
            self._authenticate()
            response = self._send(method, "/api/public/v1" + path,
                                  headers={"Authorization": f"Bearer {self._token}"}, **kwargs)
            if response.status_code != 401 or attempt:
                return self._payload(response), response.headers
            self._token = ""
            self._expires_at = 0

    def pages(self, path: str, **filters):
        """Follow zero-based pagination, including empty filtered pages with a next header."""
        for page in range(1000):
            payload, headers = self.request("GET", path, params={**filters, "page": page, "per_page": PAGE_SIZE})
            if isinstance(payload, dict):
                payload = payload.get("data")
            if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
                raise AikidoError("Aikido returned an unexpected paginated response.")
            yield from payload
            more = headers.get("X-Has-Next-Page")
            if more is not None:
                if str(more).strip().lower() == "false":
                    return
                if str(more).strip().lower() != "true":
                    raise AikidoError("Aikido returned an invalid pagination header.")
            elif len(payload) < PAGE_SIZE:
                return
        raise AikidoError("Aikido pagination exceeded 1000 pages; narrow the scope before retrying.")

    def repository(self) -> dict:
        """Resolve exactly one GitHub repository and scanned branch."""
        if self._repository is None:
            matches = [item for item in self.pages("/repositories/code", filter_branch=self.branch,
                                                   include_config_issues_info="true")
                       if github_repository(item) == self.repository_name.casefold() and item.get("branch") == self.branch]
            if len(matches) != 1:
                raise AikidoError("Expected exactly one matching GitHub repository/branch in Aikido.")
            self._repository = {**matches[0], "id": positive_id(matches[0].get("id"))}
        return self._repository

    def _check_issue(self, issue: dict) -> dict:
        """Reject findings from another repository or an explicitly different branch."""
        if positive_id(issue.get("code_repo_id")) != self.repository()["id"]:
            raise AikidoError("The finding does not belong to the selected repository.")
        if issue.get("code_repo_branch_name") and issue["code_repo_branch_name"] != self.branch:
            raise AikidoError("The finding does not belong to the selected branch.")
        positive_id(issue.get("id"))
        return issue

    def issues(self, status="open") -> list[dict]:
        """Export repository-filtered individual findings, deduplicated by stable ID."""
        found = {}
        for issue in self.pages("/issues/export", format="json", filter_status=status,
                                filter_code_repo_id=self.repository()["id"]):
            self._check_issue(issue)
            found[positive_id(issue["id"])] = issue
        return list(found.values())

    def issue(self, issue_id: int) -> dict:
        """Fetch an individual finding and verify its repository before use."""
        self.repository()
        payload, _ = self.request("GET", f"/issues/{positive_id(issue_id)}")
        if not isinstance(payload, dict) or positive_id(payload.get("id")) != issue_id:
            raise AikidoError("Aikido returned an unexpected finding.")
        return self._check_issue(payload)

    def display_issue(self, issue_id: int) -> dict:
        """Enrich AI-review display fields without replacing verified detail identity."""
        issue = self.issue(issue_id)
        if issue.get("type") not in {"ai_pentest", "agentic_review"}:
            return issue
        if issue.get("rule") and issue.get("affected_file"):
            return issue
        exported = next((item for item in self.issues("all") if item["id"] == issue_id), None)
        if exported is None:
            return issue
        issue = dict(issue)
        for field in ("rule", "affected_file"):
            if not issue.get(field) and exported.get(field):
                issue[field] = exported[field]
        if exported.get("type") and exported["type"] != issue.get("type"):
            issue["export_type"] = exported["type"]
        return issue

    def mutate(self, issue_id: int, operation: str, **payload) -> dict:
        """Apply only an explicit, repository-checked individual finding operation."""
        issue = self.issue(issue_id)
        if operation == "note":
            group_id = positive_id(issue.get("group_id"))
            note = f"[{self.repository_name}; issue {issue_id}] {payload['note']}"
            self.request("POST", f"/issues/groups/{group_id}/notes", json={"note": note})
        else:
            if operation not in {"ignore", "snooze", "unignore", "unsnooze"}:
                raise AikidoError("Unsupported finding operation.")
            self.request("PUT", f"/issues/{issue_id}/{operation}", json=payload)
        return {"issue_id": issue_id, "operation": operation, "completed": True}

    def marker(self, issue_id: int) -> str:
        """Build a stable, region/repository-specific marker for GitHub issue deduplication."""
        host = urlparse(self.origin).hostname
        return f"<!-- aikido:{host}:repo:{self.repository()['id']}:issue:{positive_id(issue_id)} -->"


def issue_view(issue: dict) -> dict:
    """Select useful finding metadata without dumping secret evidence or arbitrary payloads."""
    fields = ("id", "group_id", "type", "export_type", "rule", "status", "severity", "severity_score", "cve_id",
              "affected_package", "affected_file", "code_repo_branch_name", "installed_version",
              "patched_versions", "start_line", "end_line", "reachability_status", "snooze_until")
    selected = {key: issue[key] for key in fields if key in issue}
    metadata = issue.get("issue_type_metadata")
    if isinstance(metadata, dict):
        for kind, names in (("open_source", ("installed_version", "patched_versions")),
                            ("sast", ("start_line", "end_line"))):
            detail = metadata.get(kind)
            if isinstance(detail, dict):
                for name in names:
                    if name in detail:
                        selected.setdefault(name, detail[name])
    return selected


def finding_draft(client: AikidoClient, issue: dict) -> str:
    """Prepare a local review draft; publication follows the repository security policy."""
    metadata = json.dumps(issue_view(issue), indent=2, ensure_ascii=False)
    return (f"{client.marker(issue['id'])}\n\n# Aikido finding {issue['id']}\n\n"
            f"Repository: `{client.repository_name}` ({client.branch})\n\n"
            f"```json\n{metadata}\n```\n\n## Triage\n\n"
            "- Disposition: untriaged\n- Evidence and applicability: pending\n"
            "- Proposed remediation or acceptance reason: pending\n"
            "- Verification: pending\n\n"
            "Follow SECURITY.md for private vulnerability reporting before publishing this draft.\n")


def future_date(value: str) -> int:
    """Interpret an ISO calendar date as midnight UTC and require a future review date."""
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise AikidoError("Use --until YYYY-MM-DD (midnight UTC).") from None
    until = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    if until <= datetime.now(timezone.utc).timestamp():
        raise AikidoError("The snooze date must be in the future.")
    return until


def parser() -> argparse.ArgumentParser:
    """Define Bash/PowerShell-friendly local commands with explicit write operations."""
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--credential-target", default=DEFAULT_CREDENTIAL)
    root.add_argument("--repo", default=DEFAULT_REPOSITORY)
    root.add_argument("--branch", default="main")
    root.add_argument("--region", choices=REGIONS, default="eu")
    sections = root.add_subparsers(dest="section", required=True)
    for section in ("credentials", "auth"):
        sections.add_parser(section).add_subparsers(dest="operation", required=True).add_parser("check")
    operations = sections.add_parser("issues").add_subparsers(dest="operation", required=True)
    listing = operations.add_parser("list")
    listing.add_argument("--status", choices=("open", "ignored", "snoozed", "closed", "all"), default="open")
    for operation in ("show", "draft", "ignore", "snooze", "unignore", "unsnooze", "note"):
        command = operations.add_parser(operation)
        command.add_argument("issue_id", type=int)
        if operation in {"ignore", "snooze"}:
            command.add_argument("--reason", required=True)
        if operation == "snooze":
            command.add_argument("--until", required=True)
        if operation == "note":
            command.add_argument("--message", required=True)
    return root


def execute(client: AikidoClient, args):
    """Dispatch API operations and return only selected, credential-redacted output."""
    repository = client.repository()
    if args.section == "auth":
        findings = client.issues()
        scopes = client.declared_scopes()
        return {"authenticated": True, "repository": client.repository_name, "branch": client.branch,
                "aikido_repository_id": repository["id"], "open_findings": len(findings),
                "declared_scopes": scopes,
                "missing_triage_scopes": sorted(TRIAGE_SCOPES - set(scopes)) if scopes is not None else None,
                "write_scope_declared": "issues:write" in scopes if scopes is not None else None,
                "live_write_tested": False,
                "has_missing_lockfile": repository.get("has_missing_lockfile"),
                "has_faulty_lockfile": repository.get("has_faulty_lockfile")}
    if args.operation == "list":
        return {"repository": client.repository_name, "branch": client.branch,
                "issues": [issue_view(issue) for issue in client.issues(args.status)]}
    issue_id = positive_id(args.issue_id)
    if args.operation in {"show", "draft"}:
        issue = client.display_issue(issue_id)
        return finding_draft(client, issue) if args.operation == "draft" else issue_view(issue)
    payload = {}
    if args.operation in {"ignore", "snooze"}:
        if not args.reason.strip():
            raise AikidoError("A nonempty triage reason is required.")
        payload["reason"] = args.reason.strip()
    if args.operation == "snooze":
        payload["snooze_until"] = future_date(args.until)
    if args.operation == "note":
        if not args.message.strip():
            raise AikidoError("A nonempty note is required.")
        payload["note"] = args.message.strip()
    return client.mutate(issue_id, args.operation, **payload)


def main(argv=None) -> int:
    """Read the Windows credential and run a local command without printing auth material."""
    args = parser().parse_args(argv)
    try:
        credentials = read_credentials(args.credential_target)
        if args.section == "credentials":
            print(json.dumps({"credential_target": args.credential_target, "credential_present": True}))
            return 0
        with requests.Session() as session:
            client = AikidoClient(credentials, session, repository=args.repo, branch=args.branch, region=args.region)
            result = client.redact(execute(client, args))
        print(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except AikidoError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

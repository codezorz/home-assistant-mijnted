"""Verify local Aikido credential handling, exact scope, pagination, and explicit writes."""

import base64
import ctypes
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, Mock

import pytest
import requests


_spec = importlib.util.spec_from_file_location("mijnted_aikido_tool", Path(__file__).with_name("aikido.py"))
aikido = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aikido
_spec.loader.exec_module(aikido)

CLIENT_ID = "test-client-id"
SECRET = "test-client-secret"
TOKEN = "test-access-token"
REPOSITORY = {
    "id": 12, "provider": "github", "name": "home-assistant-mijnted", "project": "codezorz",
    "url": "https://api.github.com/repos/codezorz/home-assistant-mijnted", "branch": "main",
}
ISSUE = {"id": 21, "group_id": 31, "code_repo_id": 12, "code_repo_branch_name": "main",
         "type": "sast", "rule": "Example rule", "status": "open", "severity": "medium"}


def response(payload=None, *, status=200, more=None):
    """Return a response stand-in with real case-insensitive headers."""
    result = Mock(status_code=status)
    result.json.return_value = {} if payload is None else payload
    result.headers = requests.structures.CaseInsensitiveDict()
    if more is not None:
        result.headers["X-Has-Next-Page"] = more
    return result


def client_for(*responses):
    """Create a client with a mock-only HTTP session and one initial token response."""
    session = MagicMock()
    session.__enter__.return_value = session
    session.request.side_effect = [response({"access_token": TOKEN, "expires_in": 3600}), *responses]
    return aikido.AikidoClient(aikido.Credentials(CLIENT_ID, SECRET), session), session


def native_api(username=CLIENT_ID, password=SECRET, *, blob=None):
    """Model CredReadW's output pointer while retaining its backing allocation."""
    encoded = password.encode("utf-16-le") if blob is None else blob
    buffer = ctypes.create_string_buffer(encoded)
    credential = aikido._Credential()
    credential.UserName = username
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(aikido.wintypes.BYTE))
    credential.CredentialBlobSize = len(encoded)

    def read(target, kind, flags, output):
        """Populate the native out parameter exactly as CredReadW does."""
        ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(aikido._Credential)))[0] = ctypes.pointer(credential)
        return True

    api = Mock()
    api.CredReadW.side_effect = read
    api._allocations = (buffer, credential)
    return api


class TestCredentials:
    """Read one Generic Credential without exposing values or leaking native allocations."""

    def test_single_entry_decodes_both_values_and_frees_native_memory(self):
        """The username supplies the client ID, the UTF-16 blob supplies the secret."""
        api = native_api(password="test-secret-\u00e9\x00")
        credential = aikido.read_credentials("test-target", api=api)
        assert credential.client_id == CLIENT_ID
        assert credential.client_secret == "test-secret-\u00e9"
        assert CLIENT_ID not in repr(credential)
        assert "test-secret" not in repr(credential)
        api.CredReadW.assert_called_once()
        assert api.CredReadW.call_args.args[:3] == ("test-target", 1, 0)
        api.CredFree.assert_called_once()

    @pytest.mark.parametrize("blob", [b"", b"x"])
    def test_invalid_password_still_frees_native_memory(self, blob):
        """Missing or malformed password data fails without retaining the native buffer."""
        api = native_api(blob=blob)
        with pytest.raises(aikido.AikidoError):
            aikido.read_credentials("test-target", api=api)
        api.CredFree.assert_called_once()

    def test_missing_username_fails_after_freeing_memory(self):
        """A password-only entry is not silently interpreted as a credential pair."""
        api = native_api(username="")
        with pytest.raises(aikido.AikidoError, match="username"):
            aikido.read_credentials("test-target", api=api)
        api.CredFree.assert_called_once()

    def test_missing_entry_does_not_free_an_unallocated_pointer(self):
        """A missing Windows credential gives a setup hint without touching invalid memory."""
        api = Mock()
        api.CredReadW.return_value = False
        with pytest.raises(aikido.AikidoError, match="Cannot read Generic Credential"):
            aikido.read_credentials("test-target", api=api)
        api.CredFree.assert_not_called()

    def test_credential_check_does_not_authenticate_or_print_values(self, monkeypatch, capsys):
        """Local credential verification outputs presence only and makes no HTTP requests."""
        monkeypatch.setattr(aikido, "read_credentials", Mock(return_value=aikido.Credentials(CLIENT_ID, SECRET)))
        session = Mock()
        monkeypatch.setattr(aikido.requests, "Session", session)
        assert aikido.main(["credentials", "check"]) == 0
        output = capsys.readouterr().out
        assert json.loads(output)["credential_present"] is True
        assert CLIENT_ID not in output and SECRET not in output
        session.assert_not_called()

    def test_help_does_not_access_credentials(self, monkeypatch):
        """Help is usable on Linux CI and before storing any Windows credentials."""
        reader = Mock()
        monkeypatch.setattr(aikido, "read_credentials", reader)
        with pytest.raises(SystemExit) as error:
            aikido.main(["--help"])
        assert error.value.code == 0
        reader.assert_not_called()


class TestAuthentication:
    """Verify OAuth token handling and credential-safe failures."""

    def test_basic_auth_is_used_only_for_token_exchange(self):
        """API requests use a cached bearer token, a timeout, and no redirect forwarding."""
        client, session = client_for(response([REPOSITORY]), response([ISSUE]))
        assert client.issues() == [ISSUE]
        calls = session.request.call_args_list
        assert len(calls) == 3
        assert calls[0].kwargs["auth"] == (CLIENT_ID, SECRET)
        assert calls[0].kwargs["data"] == {"grant_type": "client_credentials"}
        for call in calls:
            assert call.kwargs["allow_redirects"] is False
            assert call.kwargs["timeout"] == aikido.TIMEOUT
        for call in calls[1:]:
            assert "auth" not in call.kwargs
            assert call.kwargs["headers"] == {"Authorization": f"Bearer {TOKEN}"}

    def test_unauthorized_refreshes_once_and_redacts_old_and_new_tokens(self):
        """A 401 gets one new token and one retry rather than an unbounded auth loop."""
        new_token = "second-test-access-token"
        client, session = client_for(response(status=401), response({"access_token": new_token}), response([]))
        assert client.request("GET", "/repositories/code")[0] == []
        assert len(session.request.call_args_list) == 4
        assert client.redact(f"{CLIENT_ID} {SECRET} {TOKEN} {new_token}") == "[redacted] [redacted] [redacted] [redacted]"

    def test_declared_scope_diagnostics_exclude_other_token_claims(self):
        """Report required permissions without revealing the bearer token or its subject."""
        claims = {"scope": "issues:read repositories:read issues:write", "sub": "test-private-subject"}
        encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        token = f"test-header.{encoded}.test-signature"
        client, session = client_for()
        session.request.side_effect = [response({"access_token": token})]
        assert client.declared_scopes() == ["issues:read", "issues:write", "repositories:read"]
        assert "test-private-subject" not in str(client.declared_scopes())
        assert session.request.call_count == 1

    @pytest.mark.parametrize("token", ["opaque-token", "header.???.signature"])
    def test_opaque_or_malformed_scope_metadata_is_unknown(self, token):
        """Missing scope metadata is not represented as proof of granted permissions."""
        client, session = client_for()
        session.request.side_effect = [response({"access_token": token})]
        assert client.declared_scopes() is None

    def test_token_response_scope_is_supported_without_decoding(self):
        """OAuth responses can report scopes directly even for opaque access tokens."""
        client, session = client_for()
        session.request.side_effect = [response({"access_token": TOKEN, "scope": "issues:read repositories:read"})]
        assert client.declared_scopes() == ["issues:read", "repositories:read"]

    def test_repeated_unauthorized_stops_after_one_refresh(self):
        """A rejected replacement token fails rather than repeatedly requesting credentials."""
        client, session = client_for(response(status=401), response({"access_token": "second-test-token"}),
                                     response(status=401))
        with pytest.raises(aikido.AikidoError, match="HTTP 401"):
            client.request("GET", "/repositories/code")
        assert len(session.request.call_args_list) == 4

    @pytest.mark.parametrize("status", [302, 400, 401, 403, 429, 500])
    def test_auth_error_never_echoes_response_payload(self, status):
        """Token failures give a status-only error, including redirects and permission failures."""
        client, session = client_for()
        session.request.side_effect = [response({"error_description": f"{CLIENT_ID} {SECRET}"}, status=status)]
        with pytest.raises(aikido.AikidoError) as error:
            client.repository()
        assert CLIENT_ID not in str(error.value) and SECRET not in str(error.value)
        assert str(status) in str(error.value)

    def test_transport_error_does_not_echo_request_credentials(self):
        """Request-library error strings cannot leak authentication headers."""
        client, session = client_for()
        session.request.side_effect = requests.ConnectionError(f"{CLIENT_ID} {SECRET}")
        with pytest.raises(aikido.AikidoError, match="ConnectionError") as error:
            client.repository()
        assert CLIENT_ID not in str(error.value) and SECRET not in str(error.value)

    def test_redaction_covers_unexpected_json_keys_too(self):
        """Even malformed API data using authentication values as keys is scrubbed."""
        client, _ = client_for()
        assert client.redact({SECRET: [CLIENT_ID]}) == {"[redacted]": ["[redacted]"]}

    def test_cli_redacts_auth_material_even_in_selected_api_fields(self, monkeypatch, capsys):
        """Unexpected authentication echoes are scrubbed before printing a finding."""
        issue = {**ISSUE, "rule": f"{CLIENT_ID} {SECRET} {TOKEN}"}
        client, session = client_for(response([REPOSITORY]), response(issue))
        monkeypatch.setattr(aikido, "read_credentials", Mock(return_value=client.credentials))
        monkeypatch.setattr(aikido.requests, "Session", Mock(return_value=session))
        assert aikido.main(["issues", "show", "21"]) == 0
        output = capsys.readouterr().out
        assert CLIENT_ID not in output and SECRET not in output and TOKEN not in output
        assert json.loads(output)["rule"] == "[redacted] [redacted] [redacted]"


class TestRepositoryScope:
    """Avoid selecting similarly named repositories or mutating another scope."""

    def test_repository_resolution_matches_owner_provider_and_branch(self):
        """Same repository basename on another owner, provider, or branch is not a match."""
        unrelated = [
            {**REPOSITORY, "id": 13, "url": "https://github.com/other/home-assistant-mijnted"},
            {**REPOSITORY, "id": 14, "provider": "gitlab"},
            {**REPOSITORY, "id": 15, "branch": "other-branch"},
        ]
        client, _ = client_for(response([*unrelated, REPOSITORY]))
        assert client.repository()["id"] == 12

    def test_ambiguous_repository_fails_before_any_finding_operation(self):
        """Two identical repository/branch matches require an explicit configuration correction."""
        client, session = client_for(response([REPOSITORY, {**REPOSITORY, "id": 13}]))
        with pytest.raises(aikido.AikidoError, match="exactly one"):
            client.mutate(21, "ignore", reason="Test")
        assert not any(call.args[0] == "PUT" for call in session.request.call_args_list)

    @pytest.mark.parametrize("change", [{"code_repo_id": 99}, {"code_repo_branch_name": "feature"}])
    def test_cross_scope_finding_is_not_mutated(self, change):
        """A foreign repository or branch from the detail API cannot receive a write."""
        client, session = client_for(response([REPOSITORY]), response({**ISSUE, **change}))
        with pytest.raises(aikido.AikidoError, match="selected"):
            client.mutate(21, "ignore", reason="Test")
        assert not any(call.args[0] == "PUT" for call in session.request.call_args_list)

    @pytest.mark.parametrize("value", ["../21", "21/ignore", "-1", 0, -1, True, 1.5])
    def test_non_numeric_or_non_positive_ids_are_rejected(self, value):
        """A finding ID cannot add endpoint path components or select a non-ID value."""
        with pytest.raises(aikido.AikidoError):
            aikido.positive_id(value)

    def test_foreign_export_row_is_rejected(self):
        """Unexpected results outside the server-requested repository do not enter the report."""
        client, _ = client_for(response([REPOSITORY]), response([{**ISSUE, "code_repo_id": 99}]))
        with pytest.raises(aikido.AikidoError):
            client.issues()


class TestPagination:
    """Read all pages and retain stable finding IDs."""

    def test_empty_filtered_page_with_next_header_does_not_stop(self):
        """An empty page with X-Has-Next-Page=true still advances to later matching records."""
        client, session = client_for(response([], more="true"), response([REPOSITORY], more="false"))
        assert client.repository()["id"] == 12
        assert [call.kwargs["params"]["page"] for call in session.request.call_args_list[1:]] == [0, 1]

    def test_export_pages_are_repo_filtered_and_deduplicated(self):
        """Repeated IDs across page boundaries produce one finding without dropping later IDs."""
        later = {**ISSUE, "id": 22}
        client, session = client_for(response([REPOSITORY]), response([ISSUE], more="true"),
                                     response([ISSUE, later], more="false"))
        assert [item["id"] for item in client.issues()] == [21, 22]
        for call in session.request.call_args_list[2:]:
            assert call.kwargs["params"]["filter_code_repo_id"] == 12

    def test_full_page_without_header_fetches_the_next_page(self):
        """Exports without pagination headers use the page size to find the end."""
        client, session = client_for(response([{}] * aikido.PAGE_SIZE), response([]))
        assert len(list(client.pages("/issues/export"))) == aikido.PAGE_SIZE
        assert len(session.request.call_args_list) == 3


class TestTriageOperations:
    """Only explicit finding-level commands update Aikido; group notes include scope."""

    def test_ignore_targets_only_verified_individual_issue(self):
        """Ignoring one finding cannot invoke the group-wide suppression endpoint."""
        client, session = client_for(response([REPOSITORY]), response(ISSUE), response({"status": "ok"}))
        assert client.mutate(21, "ignore", reason="False positive; tracked privately") == {
            "issue_id": 21, "operation": "ignore", "completed": True,
        }
        call = session.request.call_args_list[-1]
        assert call.args == ("PUT", "https://app.aikido.dev/api/public/v1/issues/21/ignore")
        assert call.kwargs["json"] == {"reason": "False positive; tracked privately"}

    def test_note_identifies_repository_and_individual_issue_in_shared_group(self):
        """Group notes identify the exact source finding without changing the group's disposition."""
        client, session = client_for(response([REPOSITORY]), response(ISSUE), response({"note_id": 42}))
        client.mutate(21, "note", note="Tracked in private issue 5")
        call = session.request.call_args_list[-1]
        assert call.args == ("POST", "https://app.aikido.dev/api/public/v1/issues/groups/31/notes")
        assert call.kwargs["json"]["note"].startswith("[codezorz/home-assistant-mijnted; issue 21]")

    def test_snooze_requires_future_review_date_before_writing(self):
        """An invalid date cannot send a state-changing API request."""
        client, session = client_for(response([REPOSITORY]))
        args = aikido.parser().parse_args(["issues", "snooze", "21", "--until", "2000-01-01", "--reason", "Test"])
        with pytest.raises(aikido.AikidoError, match="future"):
            aikido.execute(client, args)
        assert not any(call.args[0] == "PUT" for call in session.request.call_args_list)

    def test_snooze_sends_the_review_date_as_midnight_utc(self, monkeypatch):
        """A valid deferred finding carries its exact review timestamp and reason."""
        class FixedTime(datetime):
            """Keep the date independent of the test runner's calendar."""

            @classmethod
            def now(cls, tz=None):
                """Use a fixed instant before the requested review date."""
                return cls(2026, 11, 1, tzinfo=tz)

        monkeypatch.setattr(aikido, "datetime", FixedTime)
        client, session = client_for(response([REPOSITORY]), response(ISSUE), response({"status": "ok"}))
        args = aikido.parser().parse_args(["issues", "snooze", "21", "--until", "2027-01-15", "--reason", "Patch pending"])
        aikido.execute(client, args)
        call = session.request.call_args_list[-1]
        assert call.args == ("PUT", "https://app.aikido.dev/api/public/v1/issues/21/snooze")
        assert call.kwargs["json"] == {
            "snooze_until": int(datetime(2027, 1, 15, tzinfo=timezone.utc).timestamp()), "reason": "Patch pending",
        }

    @pytest.mark.parametrize("operation", ["unignore", "unsnooze"])
    def test_reopen_operations_are_individual_and_explicit(self, operation):
        """Reversing a disposition uses the verified finding's endpoint only."""
        client, session = client_for(response([REPOSITORY]), response(ISSUE), response({"status": "ok"}))
        client.mutate(21, operation)
        call = session.request.call_args_list[-1]
        assert call.args == ("PUT", f"https://app.aikido.dev/api/public/v1/issues/21/{operation}")
        assert call.kwargs["json"] == {}

    def test_failed_write_is_not_automatically_retried(self):
        """A server error cannot accidentally duplicate a finding disposition."""
        client, session = client_for(response([REPOSITORY]), response(ISSUE), response(status=500))
        with pytest.raises(aikido.AikidoError, match="HTTP 500"):
            client.mutate(21, "ignore", reason="Test")
        assert sum(call.args[0] == "PUT" for call in session.request.call_args_list) == 1

    def test_selected_nested_metadata_is_useful_without_raw_evidence(self):
        """Package versions and code lines survive the detail API's nested response shape."""
        issue = {**ISSUE, "issue_type_metadata": {
            "open_source": {"installed_version": "1.0", "patched_versions": ["1.1"], "evidence": "private-data"},
            "sast": {"start_line": 12, "end_line": 14, "code": "private-code"},
        }}
        view = aikido.issue_view(issue)
        assert view["installed_version"] == "1.0"
        assert view["start_line"] == 12
        assert "private-data" not in str(view) and "private-code" not in str(view)

    def test_draft_marker_is_stable_and_secret_evidence_is_omitted(self):
        """A local draft can be deduplicated without copying raw leaked-secret metadata."""
        client, _ = client_for(response([REPOSITORY]))
        issue = {**ISSUE, "type": "leaked_secret", "issue_type_metadata": {"secret": "test-evidence-value"}}
        draft = aikido.finding_draft(client, issue)
        assert "<!-- aikido:app.aikido.dev:repo:12:issue:21 -->" in draft
        assert "test-evidence-value" not in draft
        assert "SECURITY.md" in draft

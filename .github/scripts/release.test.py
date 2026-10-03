"""Verify version allocation, immutable packaging, and safe release retries."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
import zipfile

import pytest

_script = Path(__file__).with_name("release.py")
_spec = importlib.util.spec_from_file_location("mijnted_release", _script)
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


@pytest.fixture
def source_zip():
    """Provide a source archive with integration and unrelated repository files."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("custom_components/mijnted/manifest.json", json.dumps({
            "domain": "mijnted", "version": "0.0.0-dev.0", "requirements": ["aiohttp"]
        }))
        archive.writestr("custom_components/mijnted/sensor.py", "VALUE = 42\n")
        archive.writestr("custom_components/mijnted/translations/en.json", '{"title": "MijnTed"}')
        archive.writestr("custom_components/mijnted/__pycache__/sensor.pyc", "cache")
        archive.writestr("README.md", "Not an integration file")
    return stream.getvalue()


def release_record(draft=False, prerelease=False):
    """Build minimal GitHub release metadata for offline publisher tests."""
    return {"draft": draft, "prerelease": prerelease, "body": "Tested changes"}


class TestVersionAllocation:
    """Exercise reset, active cycles, explicit targets, and strict SemVer."""

    def test_patch_cycle_resets_after_promotion(self):
        """The next beta sorts after the stable version and starts at one."""
        tags = {"v1.0.26-beta.1": "a", "v1.0.26-beta.7": "b", "v1.0.26": "b"}
        assert release.next_beta(tags, (1, 0, 26)) == "v1.0.27-beta.1"
        assert release.next_beta(tags, (1, 0, 25)) == "v1.0.26-beta.8"

    def test_minor_cycle_survives_patch_promotion(self):
        """An already-started higher-version beta cycle remains active."""
        tags = {"v1.1.0-beta.2": "a", "v1.0.26-beta.4": "b"}
        assert release.next_beta(tags, (1, 0, 26)) == "v1.1.0-beta.3"

    def test_explicit_target_is_consumed_after_stable(self):
        """Minor and major overrides need no reset commit after promotion."""
        assert release.next_beta({}, (1, 0, 25), "2.0.0") == "v2.0.0-beta.1"
        assert release.next_beta({}, (2, 0, 0), "2.0.0") == "v2.0.1-beta.1"
        with pytest.raises(ValueError, match="backwards"):
            release.next_beta({"v2.0.0-beta.1": "a"}, (1, 0, 25), "1.1.0")

    @pytest.mark.parametrize("tag", ["v01.0.0", "v1.0.0-beta.0", "v1.0.0-beta.01",
                                     "1.0.0", "v1.0.0;echo injected", "v1.0.0-rc.1"])
    def test_rejects_noncanonical_tags(self, tag):
        """Only the agreed tag scheme can reach publishing commands."""
        with pytest.raises(ValueError, match="Invalid release tag"):
            release.parse_tag(tag)

    def test_latest_stable_ignores_drafts_and_betas(self):
        """Unpublished stable tags cannot advance the release baseline."""
        records = {"v1.0.25": release_record(), "v1.0.26": release_record(draft=True),
                   "v2.0.0-beta.1": release_record(prerelease=True)}
        assert release.latest_stable(records) == (1, 0, 25)


class TestPackaging:
    """Check HACS layout and the exact code preserved during promotion."""

    def test_beta_package_is_flat_and_deterministic(self, source_zip, tmp_path):
        """Release ZIPs contain the integration only, with an exact manifest version."""
        first, second = tmp_path / "first.zip", tmp_path / "second.zip"
        release.package_source(source_zip, "v1.0.26-beta.3", first)
        release.package_source(source_zip, "v1.0.26-beta.3", second)
        assert first.read_bytes() == second.read_bytes()
        with zipfile.ZipFile(first) as archive:
            assert set(archive.namelist()) == {"manifest.json", "sensor.py", "translations/en.json"}
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["version"] == "1.0.26-beta.3"
            assert manifest["requirements"] == ["aiohttp"]
        with zipfile.ZipFile(io.BytesIO(source_zip)) as archive:
            assert json.loads(archive.read(release.INTEGRATION + "manifest.json"))["version"] == "0.0.0-dev.0"

    def test_promotion_changes_only_manifest_version(self, source_zip, tmp_path):
        """Stable assets preserve every tested beta file and manifest field."""
        beta, stable = tmp_path / "beta.zip", tmp_path / "stable.zip"
        release.package_source(source_zip, "v1.0.26-beta.3", beta)
        release.promote_package(beta, "v1.0.26-beta.3", "v1.0.26", stable)
        with zipfile.ZipFile(beta) as before, zipfile.ZipFile(stable) as after:
            assert before.namelist() == after.namelist()
            for name in before.namelist():
                if name != "manifest.json":
                    assert before.read(name) == after.read(name)
            manifest = json.loads(before.read("manifest.json"))
            manifest["version"] = "1.0.26"
            assert json.loads(after.read("manifest.json")) == manifest

    def test_promotion_rejects_mismatched_asset(self, source_zip, tmp_path):
        """A mislabeled beta asset cannot be promoted."""
        beta = tmp_path / "beta.zip"
        release.package_source(source_zip, "v1.0.26-beta.2", beta)
        with pytest.raises(ValueError, match="does not match"):
            release.promote_package(beta, "v1.0.26-beta.3", "v1.0.26", tmp_path / "stable.zip")


class TestCandidateValidation:
    """Verify candidate tests run in a real checkout at the requested commit."""

    def test_validation_preserves_git_discovery_at_exact_commit(self, monkeypatch, tmp_path):
        """Historical candidates retain Git metadata and pass the previously failing test."""
        repository = Path(__file__).resolve().parents[2]
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
        root = tmp_path / "detached validation source"
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
                        str(repository), str(root)], check=True)
        subprocess.run(["git", "checkout", "--quiet", "--detach", commit], cwd=root, check=True)
        # Build a newer detached source tip even when CI supplied a shallow checkout.
        subprocess.run(["git", "-c", "user.name=Release test", "-c",
                        "user.email=release-test@example.invalid", "commit", "--quiet",
                        "--allow-empty", "-m", "Advance temporary validation source"],
                       cwd=root, check=True)
        source_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        assert source_head != commit
        directory = tmp_path / "candidate with spaces"
        real_run = subprocess.run
        python_commands = []

        def run_command(command, **kwargs):
            if command[0] == sys.executable:
                python_commands.append(command)
                if command[2] == "pip":
                    return subprocess.CompletedProcess(command, 0)
                if command[2] == "pytest":
                    # Exercise the real regression without recursively running release tests.
                    command = [*command, "-p", "no:cacheprovider",
                               "tests/test_agent_guidance_hook.py::TestAgentGuidanceHook::"
                               "test_current_worktree_is_discovered_from_a_subdirectory"]
            return real_run(command, **kwargs)

        monkeypatch.chdir(root)
        monkeypatch.setattr(release.subprocess, "run", run_command)
        release.validate_commit(commit, directory)
        assert (directory / ".git").is_dir()
        assert release.run("git", "rev-parse", "HEAD", cwd=directory) == commit
        assert release.run("git", "rev-parse", "--show-toplevel", cwd=directory / "doc") == directory.as_posix()
        assert release.run("git", "rev-parse", "HEAD", cwd=root) == source_head
        assert any(command[2] == "compileall" for command in python_commands)
        assert any(command[2] == "pytest" for command in python_commands)


class TestPublishing:
    """Exercise retries and failure boundaries without contacting GitHub."""

    def test_multi_commit_push_keeps_all_commits(self, monkeypatch):
        """History reconciliation processes intermediate and merged branch commits."""
        monkeypatch.setattr(release, "require_on_main", Mock())
        command = Mock(return_value="first\nbranch\nmerge")
        monkeypatch.setattr(release, "run", command)
        assert release.pending_commits("anchor") == ["first", "branch", "merge"]
        assert command.call_args.args == (
            "git", "rev-list", "--reverse", "--topo-order", "anchor..origin/main")

    def test_upload_failure_leaves_draft_for_repair(self, monkeypatch, tmp_path):
        """The release is never published before its asset upload succeeds."""
        command = Mock(side_effect=["", subprocess.CalledProcessError(1, "upload")])
        monkeypatch.setattr(release, "run", command)
        with pytest.raises(subprocess.CalledProcessError):
            release.publish("v1.0.26-beta.1", "commit", tmp_path / "mijnted.zip", {})
        assert "--draft" in command.call_args_list[0].args
        assert not any("edit" in call.args for call in command.call_args_list)

    def test_retry_repairs_draft_without_recreating_tag(self, monkeypatch, tmp_path):
        """Draft recovery uploads the package then publishes the existing release."""
        command = Mock(return_value="")
        monkeypatch.setattr(release, "run", command)
        release.publish("v1.0.26-beta.1", "commit", tmp_path / "mijnted.zip",
                        {"v1.0.26-beta.1": release_record(draft=True, prerelease=True)})
        assert [call.args[2] for call in command.call_args_list] == ["upload", "edit"]
        assert "--latest=false" in command.call_args_list[-1].args

    def test_reconciliation_skips_published_and_retries_failed_commit(self, monkeypatch, tmp_path, source_zip):
        """A rerun preserves assigned numbers and processes every remaining commit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github/release-config.json").write_text(
            json.dumps({"start_commit": "anchor", "next_version": None}))
        monkeypatch.setattr(release, "pending_commits", lambda start: ["done", "retry", "new"])
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.26-beta.1": "done", "v1.0.26-beta.2": "retry"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.25": release_record(),
            "v1.0.26-beta.1": release_record(prerelease=True),
            "v1.0.26-beta.2": release_record(draft=True, prerelease=True)})
        monkeypatch.setattr(release, "source_archive", lambda commit: source_zip)
        validate, publish = Mock(), Mock()
        monkeypatch.setattr(release, "validate_commit", validate)
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", Mock())
        release.publish_betas()
        assert [(call.args[0], call.args[1]) for call in publish.call_args_list] == [
            ("v1.0.26-beta.2", "retry"), ("v1.0.26-beta.3", "new")]
        assert validate.call_count == 2
        assert [call.args[0] for call in validate.call_args_list] == ["retry", "new"]

    def test_failed_validation_cannot_publish(self, monkeypatch, tmp_path, source_zip):
        """A failing candidate stops reconciliation before creating any release."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github/release-config.json").write_text(
            json.dumps({"start_commit": "anchor", "next_version": None}))
        monkeypatch.setattr(release, "pending_commits", lambda start: ["broken"])
        monkeypatch.setattr(release, "get_tags", lambda: {})
        monkeypatch.setattr(release, "get_releases", lambda: {"v1.0.25": release_record()})
        monkeypatch.setattr(release, "source_archive", lambda commit: source_zip)
        monkeypatch.setattr(release, "validate_commit", Mock(side_effect=RuntimeError("tests failed")))
        publish = Mock()
        monkeypatch.setattr(release, "publish", publish)
        with pytest.raises(RuntimeError, match="tests failed"):
            release.publish_betas()
        publish.assert_not_called()

    def test_promotion_rejects_conflicting_stable_tag(self, monkeypatch):
        """Promotion never moves a stable tag to a different source commit."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.26-beta.1": "tested", "v1.0.26": "different"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.25": release_record(), "v1.0.26-beta.1": release_record(prerelease=True)})
        monkeypatch.setattr(release, "require_on_main", Mock())
        with pytest.raises(ValueError, match="different commit"):
            release.promote("v1.0.26-beta.1")

    def test_default_selects_exact_main_not_newest_beta_elsewhere(self, monkeypatch):
        """An empty input releases main, never a newer beta on a different commit."""
        monkeypatch.setattr(release, "run", Mock(return_value="main-tip"))
        tags = {"v1.0.26-beta.1": "main-tip", "v2.0.0-beta.5": "other",
                "v1.0.26-beta.2": "main-tip"}
        records = {"v1.0.26-beta.1": release_record(prerelease=True),
                   "v2.0.0-beta.5": release_record(prerelease=True),
                   "v1.0.26-beta.2": release_record(draft=True, prerelease=True)}
        assert release.beta_for_main(tags, records) == "v1.0.26-beta.1"

    def test_empty_input_promotes_existing_main_beta(self, monkeypatch, tmp_path, source_zip):
        """The default promotion uses main's published beta without publishing new betas."""
        monkeypatch.setattr(release, "get_tags", lambda: {"v1.0.26-beta.3": "main-tip"})
        records = {"v1.0.25": release_record(),
                   "v1.0.26-beta.3": release_record(prerelease=True)}
        monkeypatch.setattr(release, "get_releases", lambda: records)
        reconcile, require_main, publish = Mock(), Mock(), Mock()
        monkeypatch.setattr(release, "publish_betas", reconcile)
        monkeypatch.setattr(release, "require_on_main", require_main)
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", Mock())

        def command(*args):
            if args[:3] == ("git", "rev-parse", "origin/main"):
                return "main-tip"
            if args[:3] == ("gh", "release", "download"):
                directory = Path(args[args.index("--dir") + 1])
                release.package_source(source_zip, "v1.0.26-beta.3", directory / "mijnted.zip")
            return ""

        monkeypatch.setattr(release, "run", command)
        release.promote("")
        reconcile.assert_not_called()
        require_main.assert_called_once_with("main-tip")
        assert publish.call_args.args[:2] == ("v1.0.26", "main-tip")

    def test_default_reports_missing_main_beta(self, monkeypatch):
        """A failed or unfinished beta workflow cannot silently release another commit."""
        monkeypatch.setattr(release, "run", Mock(return_value="main-tip"))
        with pytest.raises(ValueError, match="no published beta"):
            release.beta_for_main({"v1.0.26-beta.1": "older"}, {
                "v1.0.26-beta.1": release_record(prerelease=True)})

    def test_explicit_input_does_not_reconcile_newer_main(self, monkeypatch):
        """Selecting a beta leaves later main commits outside the promotion."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.26-beta.1": "tested", "v1.0.26": "tested"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.26": release_record(), "v1.0.26-beta.1": release_record(prerelease=True)})
        monkeypatch.setattr(release, "require_on_main", Mock())
        reconcile = Mock()
        monkeypatch.setattr(release, "publish_betas", reconcile)
        release.promote("v1.0.26-beta.1")
        reconcile.assert_not_called()

    def test_tag_reservation_is_immutable_and_retryable(self, monkeypatch):
        """An upload failure leaves the commit's tag reserved without force-pushing."""
        command = Mock(return_value="")
        monkeypatch.setattr(release, "run", command)
        release.reserve_tag("v1.0.26-beta.1", "tested", {})
        command.assert_called_once_with(
            "git", "push", "origin", "tested:refs/tags/v1.0.26-beta.1")
        command.reset_mock()
        release.reserve_tag("v1.0.26-beta.1", "tested", {"v1.0.26-beta.1": "tested"})
        command.assert_not_called()
        with pytest.raises(ValueError, match="different commit"):
            release.reserve_tag("v1.0.26-beta.1", "tested", {"v1.0.26-beta.1": "other"})

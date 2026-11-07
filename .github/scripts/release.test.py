"""Verify version allocation, immutable packaging, and safe release retries."""

import base64
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
    """Exercise accumulated release intent, active cycles, and strict SemVer."""

    def test_patch_cycle_resets_after_promotion(self):
        """The next beta sorts after the stable version and starts at one."""
        tags = {"v1.0.26-beta.1": "a", "v1.0.26-beta.7": "b", "v1.0.26": "b"}
        assert release.next_beta(tags, (1, 0, 26)) == "v1.0.27-beta.1"
        assert release.next_beta(tags, (1, 0, 25)) == "v1.0.26-beta.8"

    def test_existing_higher_cycle_never_moves_backwards(self):
        """Legacy higher betas and new patch requests retain the active target."""
        tags = {"v1.1.0-beta.2": "a", "v1.0.27-beta.1": "b"}
        assert release.next_beta(tags, (1, 0, 26)) == "v1.1.0-beta.3"
        assert release.next_beta(tags, (1, 0, 27)) == "v1.1.0-beta.3"
        assert release.next_beta(tags, (1, 1, 0)) == "v1.1.1-beta.1"

    def test_multiple_prs_accumulate_intent_since_stable(self):
        """Repeated minor requests and later fixes share one upcoming minor release."""
        tags = {}
        for bump, expected in [
            ("patch", "v1.0.24-beta.1"), ("minor", "v1.1.0-beta.1"),
            ("minor", "v1.1.0-beta.2"), ("patch", "v1.1.0-beta.3"),
            ("major", "v2.0.0-beta.1"), ("minor", "v2.0.0-beta.2"),
        ]:
            assert release.next_beta(tags, (1, 0, 23), bump) == expected
            tags[expected] = expected
        assert release.next_beta(tags, (2, 0, 0)) == "v2.0.1-beta.1"
        assert release.next_beta(tags, (2, 0, 0), "minor") == "v2.1.0-beta.1"

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


class TestReleaseLabels:
    """Recover merge-time release intent despite label edits and delayed workflows."""

    @pytest.fixture(autouse=True)
    def repository(self, monkeypatch):
        """Scope API lookups to the test repository."""
        monkeypatch.setenv("GH_REPO", "owner/repository")

    @pytest.mark.parametrize("label,bump", [
        ("release:patch", "patch"), ("release:minor", "minor"),
        ("release:major", "major"), ("enhancement", "patch"),
    ])
    def test_labels_at_merge_determine_the_bump(self, monkeypatch, label, bump):
        """Post-merge additions and removals cannot change release intent."""
        events = [
            {"id": 1, "event": "labeled", "label": {"name": label}},
            {"id": 2, "event": "merged", "commit_id": "merge"},
            {"id": 3, "event": "unlabeled", "label": {"name": label}},
            {"id": 4, "event": "labeled", "label": {"name": "release:major"}},
        ]
        api = Mock(return_value=list(reversed(events)))
        monkeypatch.setattr(release, "read_api_pages", api)
        assert release.merged_pr_bump(47, "merge") == bump
        api.assert_called_once_with("repos/owner/repository/issues/47/events")

    def test_replaced_label_before_merge_uses_final_choice(self, monkeypatch):
        """A pre-merge major-to-minor adjustment uses only the final label."""
        monkeypatch.setattr(release, "read_api_pages", Mock(return_value=[
            {"id": 1, "event": "labeled", "label": {"name": "release:major"}},
            {"id": 2, "event": "unlabeled", "label": {"name": "release:major"}},
            {"id": 3, "event": "labeled", "label": {"name": "release:minor"}},
            {"id": 4, "event": "merged", "commit_id": "merge"},
        ]))
        assert release.merged_pr_bump(47, "merge") == "minor"

    def test_conflicting_labels_fail_instead_of_guessing(self, monkeypatch):
        """Two release labels at merge stop publication before reserving a version."""
        monkeypatch.setattr(release, "read_api_pages", Mock(return_value=[
            {"id": 1, "event": "labeled", "label": {"name": "release:minor"}},
            {"id": 2, "event": "labeled", "label": {"name": "release:patch"}},
            {"id": 3, "event": "merged", "commit_id": "merge"},
        ]))
        with pytest.raises(ValueError, match="conflicting release labels"):
            release.merged_pr_bump(47, "merge")

    def test_missing_merge_event_does_not_silently_default(self, monkeypatch):
        """Unavailable merge metadata is retryable instead of losing a requested bump."""
        monkeypatch.setattr(release, "read_api_pages", Mock(return_value=[]))
        with pytest.raises(ValueError, match="no matching merge event"):
            release.merged_pr_bump(47, "merge")

    def test_only_main_merge_commit_applies_pr_intent(self, monkeypatch):
        """Open PRs, branch commits, and other base branches cannot advance the cycle."""
        pulls = [
            {"number": 1, "merged_at": None, "merge_commit_sha": "merge", "base": {"ref": "main"}},
            {"number": 2, "merged_at": "date", "merge_commit_sha": "other", "base": {"ref": "main"}},
            {"number": 3, "merged_at": "date", "merge_commit_sha": "merge", "base": {"ref": "other"}},
            {"number": 4, "merged_at": "date", "merge_commit_sha": "merge", "base": {"ref": "main"}},
        ]
        api = Mock(return_value=pulls)
        bump = Mock(return_value="minor")
        monkeypatch.setattr(release, "read_api_pages", api)
        monkeypatch.setattr(release, "merged_pr_bump", bump)
        assert release.commit_bump("merge") == "minor"
        bump.assert_called_once_with(4, "merge")
        api.assert_called_once_with("repos/owner/repository/commits/merge/pulls")

    def test_direct_commit_defaults_to_patch(self, monkeypatch):
        """Direct pushes without an associated merged PR retain patch intent."""
        monkeypatch.setattr(release, "read_api_pages", Mock(return_value=[]))
        assert release.commit_bump("direct") == "patch"

    def test_metadata_api_reads_all_pages_with_separate_token(self, monkeypatch):
        """PR metadata uses read-only credentials without changing publishing credentials."""
        monkeypatch.setenv("GH_TOKEN", "publisher")
        monkeypatch.setenv("GH_READ_TOKEN", "reader")
        command = Mock(return_value=json.dumps([[{"id": 1}], [{"id": 2}]]))
        monkeypatch.setattr(release, "run", command)
        assert release.read_api_pages("endpoint") == [{"id": 1}, {"id": 2}]
        assert command.call_args.args == ("gh", "api", "--paginate", "--slurp", "endpoint")
        assert command.call_args.kwargs["env"]["GH_TOKEN"] == "reader"
        assert release.os.environ["GH_TOKEN"] == "publisher"


class TestPackaging:
    """Check Marketplace layout and the exact code preserved during promotion."""

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

    @pytest.mark.parametrize("beta_tag,stable_tag", [
        ("v1.0.26-beta.3", "v1.0.26"), ("v1.1.0-beta.2", "v1.1.0"),
        ("v2.0.0-beta.1", "v2.0.0"),
    ])
    def test_promotion_changes_only_manifest_version(self, source_zip, tmp_path, beta_tag, stable_tag):
        """Stable assets preserve every tested beta file and manifest field."""
        beta, stable = tmp_path / "beta.zip", tmp_path / "stable.zip"
        release.package_source(source_zip, beta_tag, beta)
        release.promote_package(beta, beta_tag, stable_tag, stable)
        with zipfile.ZipFile(beta) as before, zipfile.ZipFile(stable) as after:
            assert before.namelist() == after.namelist()
            for name in before.namelist():
                if name != "manifest.json":
                    assert before.read(name) == after.read(name)
            manifest = json.loads(before.read("manifest.json"))
            manifest["version"] = stable_tag[1:]
            assert json.loads(after.read("manifest.json")) == manifest

    def test_promotion_rejects_mismatched_asset(self, source_zip, tmp_path):
        """A mislabeled beta asset cannot be promoted."""
        beta = tmp_path / "beta.zip"
        release.package_source(source_zip, "v1.0.26-beta.2", beta)
        with pytest.raises(ValueError, match="does not match"):
            release.promote_package(beta, "v1.0.26-beta.3", "v1.0.26", tmp_path / "stable.zip")

    def test_promotion_rejects_beta_destination(self, source_zip, tmp_path):
        """The destination must be stable even when its version differs from the beta."""
        beta = tmp_path / "beta.zip"
        release.package_source(source_zip, "v1.0.26-beta.3", beta)
        with pytest.raises(ValueError, match="stable destination"):
            release.promote_package(beta, "v1.0.26-beta.3", "v1.1.0-beta.1", tmp_path / "stable.zip")

    @pytest.mark.parametrize("target", ["v1.0.25", "v1.1.0", "v2.0.0"])
    def test_promotion_rejects_any_core_version_change(self, source_zip, tmp_path, target):
        """Promotion cannot raise or lower the tested beta's core version."""
        beta = tmp_path / "beta.zip"
        release.package_source(source_zip, "v1.0.26-beta.3", beta)
        with pytest.raises(ValueError, match="preserve the beta's core version"):
            release.promote_package(beta, "v1.0.26-beta.3", target, tmp_path / "stable.zip")


class TestPromotionHistory:
    """Check eligibility by source history rather than beta core versions."""

    @pytest.fixture
    def history(self, monkeypatch, tmp_path):
        """Build a real stable lineage plus an older divergent branch."""
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init", "--quiet"], check=True)

        def commit(message):
            subprocess.run(["git", "-c", "user.name=Release test", "-c",
                            "user.email=release-test@example.invalid", "commit", "--quiet",
                            "--allow-empty", "-m", message], check=True)
            return release.run("git", "rev-parse", "HEAD")

        older = commit("Older beta")
        stable = commit("Latest stable")
        newer = commit("Newer beta")
        subprocess.run(["git", "checkout", "--quiet", "-b", "divergent", older], check=True)
        divergent = commit("Divergent beta")
        return {"older": older, "stable": stable, "newer": newer, "divergent": divergent}

    @pytest.mark.parametrize("candidate,accepted", [
        ("newer", True), ("older", False), ("divergent", False), ("stable", False),
    ])
    def test_only_descendants_of_latest_stable_are_eligible(self, history, candidate, accepted):
        """Older and diverged commits cannot become a new stable release."""
        if accepted:
            release.require_after_stable(history[candidate], history["stable"])
        else:
            with pytest.raises(ValueError, match="newer than and descends"):
                release.require_after_stable(history[candidate], history["stable"])


class TestCandidateValidation:
    """Verify candidate tests run in a real checkout at the requested commit."""

    @pytest.mark.parametrize("has_lock", [False, True])
    def test_dependency_install_uses_each_candidates_dependency_format(self, monkeypatch, tmp_path, has_lock):
        """Locked candidates export before installation; historical requirements-only candidates still work."""
        directory = tmp_path / "candidate"
        integration = directory / release.INTEGRATION
        integration.mkdir(parents=True)
        (integration / "manifest.json").write_text(json.dumps({"requirements": []}), encoding="utf-8")
        if has_lock:
            (directory / "uv.lock").touch()
        else:
            (directory / "requirements_test.txt").write_text("pytest\n", encoding="utf-8")
        process = Mock(return_value=subprocess.CompletedProcess([], 0))
        monkeypatch.setattr(release, "run", Mock())
        monkeypatch.setattr(release.subprocess, "run", process)

        release.validate_commit("candidate-commit", directory)

        commands = [call.args[0] for call in process.call_args_list]
        install = [sys.executable, "-m", "pip", "install", "-r", "requirements_test.txt"]
        assert install in commands
        exports = [command for command in commands if command[2] == "uv"]
        assert bool(exports) == has_lock
        if has_lock:
            assert "--locked" in exports[0]
            assert exports[0][-2:] == ["--output-file", "requirements_test.txt"]
            assert commands.index(exports[0]) < commands.index(install)

    def test_candidate_processes_do_not_inherit_tokens_or_git_auth(self, monkeypatch, tmp_path):
        """Dependency builds, Git, and tests receive only the validation allowlist."""
        monkeypatch.setenv("GH_TOKEN", "publisher-secret")
        monkeypatch.setenv("GH_READ_TOKEN", "reader-secret")
        monkeypatch.setenv("ACTIONS_RUNTIME_TOKEN", "artifact-secret")
        monkeypatch.setenv("RELEASE_APP_PRIVATE_KEY", "private-key")
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "AUTHORIZATION: secret")
        monkeypatch.setenv("PYTHONPATH", "untrusted-python-path")
        directory = tmp_path / "candidate"
        integration = directory / release.INTEGRATION
        integration.mkdir(parents=True)
        (integration / "manifest.json").write_text(json.dumps({"requirements": ["example"]}))
        command, process = Mock(), Mock()
        monkeypatch.setattr(release, "run", command)
        monkeypatch.setattr(release.subprocess, "run", process)
        release.validate_commit("candidate", directory)
        for call in [*command.call_args_list, *process.call_args_list]:
            env = call.kwargs["env"]
            assert not any("secret" in value or "private-key" in value for value in env.values())
            assert "GH_TOKEN" not in env and "PYTHONPATH" not in env
            assert "GIT_CONFIG_COUNT" not in env and "GIT_CONFIG_VALUE_0" not in env
            assert env["GIT_CONFIG_GLOBAL"] == release.os.devnull
            assert env["PYTHONNOUSERSITE"] == "1"
        assert release.os.environ["GH_TOKEN"] == "publisher-secret"

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
                if command[2] in {"pip", "uv"}:
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
        assert release.run("git", "rev-parse", "--show-toplevel",
                           cwd=directory / "custom_components" / "mijnted") == directory.as_posix()
        assert release.run("git", "rev-parse", "HEAD", cwd=root) == source_head
        assert any(command[2] == "compileall" for command in python_commands)
        assert any(command[2] == "pytest" for command in python_commands)


class TestReleasePlanning:
    """Bind validation and publication to one immutable, independently planned snapshot."""

    @pytest.mark.parametrize("value", ['{}', '["short"]', '[1]', '[["nested"]]',
                                      json.dumps(["a" * 40, "a" * 40])])
    def test_invalid_or_duplicate_commit_lists_are_rejected(self, value):
        """Only unique, full immutable commit IDs can authorize a publication batch."""
        with pytest.raises(ValueError):
            release.parse_commits(value)

    def test_full_commit_ids_round_trip(self):
        """A planned ordered batch retains exact IDs, including an empty batch."""
        commits = ["a" * 40, "b" * 40]
        assert release.parse_commits(json.dumps(commits)) == commits
        assert release.parse_commits("[]") == []

    def test_snapshot_remains_the_checked_out_commit_when_main_advances(self, monkeypatch):
        """Refreshing main cannot silently add unvalidated newer commits to publication."""
        snapshot = "a" * 40
        command = Mock(side_effect=["", snapshot, ""])
        require = Mock()
        monkeypatch.setattr(release, "run", command)
        monkeypatch.setattr(release, "require_on_main", require)
        assert release.prepare_snapshot(snapshot) == snapshot
        require.assert_called_once_with(snapshot)
        assert command.call_args.args == ("git", "update-ref", "refs/remotes/origin/main", snapshot)

    def test_publisher_checkout_must_match_the_planned_snapshot(self, monkeypatch):
        """A different checkout is rejected before the reconciliation ref is changed."""
        command = Mock(side_effect=["", "b" * 40])
        monkeypatch.setattr(release, "run", command)
        with pytest.raises(ValueError, match="snapshot"):
            release.prepare_snapshot("a" * 40)
        assert command.call_count == 2

    def test_real_remote_advance_cannot_expand_the_release_snapshot(self, monkeypatch, tmp_path):
        """New remote commits remain ineligible after the workflow pins its older snapshot."""
        remote, checkout = tmp_path / "origin.git", tmp_path / "checkout"
        subprocess.run(["git", "init", "--quiet", "--bare", str(remote)], check=True)
        subprocess.run(["git", "init", "--quiet", "-b", "main", str(checkout)], check=True)

        def commit(message):
            subprocess.run(["git", "-c", "user.name=Release test", "-c",
                            "user.email=release-test@example.invalid", "commit", "--quiet",
                            "--allow-empty", "-m", message], cwd=checkout, check=True)
            return release.run("git", "rev-parse", "HEAD", cwd=checkout)

        snapshot = commit("Planned snapshot")
        newer = commit("New remote main")
        release.run("git", "remote", "add", "origin", str(remote), cwd=checkout)
        release.run("git", "push", "--quiet", "origin", "main", cwd=checkout)
        release.run("git", "checkout", "--quiet", "--detach", snapshot, cwd=checkout)
        monkeypatch.chdir(checkout)
        assert release.prepare_snapshot(snapshot) == snapshot
        assert release.run("git", "rev-parse", "origin/main") == snapshot
        assert release.run("git", "rev-parse", "FETCH_HEAD") == newer
        with pytest.raises(subprocess.CalledProcessError):
            release.require_on_main(newer)

    def test_validation_failure_stops_the_read_only_batch(self, monkeypatch):
        """A failed historical candidate prevents successful completion of validation."""
        monkeypatch.setattr(release, "require_on_main", Mock())
        validator = Mock(side_effect=RuntimeError("tests failed"))
        monkeypatch.setattr(release, "validate_commit", validator)
        with pytest.raises(RuntimeError, match="tests failed"):
            release.validate_commits(["first", "second"])
        assert [call.args[0] for call in validator.call_args_list] == ["first"]

    def test_plan_outputs_only_snapshot_and_unpublished_commit_ids(self, monkeypatch, capsys):
        """The read-only planning command emits values consumable by GitHub job outputs."""
        snapshot, candidate = "a" * 40, "b" * 40
        monkeypatch.setattr(sys, "argv", ["release.py", "plan"])
        monkeypatch.setattr(release, "prepare_snapshot", Mock(return_value=snapshot))
        monkeypatch.setattr(release, "get_tags", Mock(return_value={}))
        monkeypatch.setattr(release, "get_releases", Mock(return_value={}))
        monkeypatch.setattr(release, "beta_candidates", Mock(return_value=[candidate]))
        release.main()
        values = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
        assert values == {"snapshot": snapshot, "commits": json.dumps([candidate])}


class TestPublishing:
    """Exercise retries and failure boundaries without contacting GitHub."""

    @pytest.fixture(autouse=True)
    def mock_promotion_history(self, monkeypatch):
        """Keep publisher tests independent of local Git history."""
        check = Mock()
        monkeypatch.setattr(release, "require_after_stable", check)
        return check

    @pytest.fixture(autouse=True)
    def mock_commit_bump(self, monkeypatch):
        """Isolate publishing tests from GitHub PR lookups."""
        bump = Mock(return_value="patch")
        monkeypatch.setattr(release, "commit_bump", bump)
        return bump

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

    def test_stable_draft_retry_replaces_old_beta_notes(self, monkeypatch, tmp_path):
        """Recovered stable drafts publish fresh notes instead of stale beta provenance."""
        command = Mock(return_value="")
        monkeypatch.setattr(release, "run", command)
        notes = "## What's Changed\nAll changes since v1.0.25"
        release.publish("v1.0.26", "commit", tmp_path / "mijnted.zip",
                        {"v1.0.26": release_record(draft=True)}, notes)
        assert [call.args[2] for call in command.call_args_list] == ["upload", "edit"]
        edit = command.call_args_list[-1].args
        assert edit[edit.index("--notes") + 1] == notes
        assert "--latest=true" in edit

    @pytest.mark.parametrize("retry_tag,new_tag", [
        ("v1.0.26-beta.2", "v1.0.26-beta.3"),
        ("v1.1.0-beta.2", "v1.1.0-beta.3"),
    ])
    def test_reconciliation_skips_published_and_retries_failed_commit(self, monkeypatch, tmp_path,
                                                                     source_zip, retry_tag, new_tag,
                                                                     mock_commit_bump):
        """A rerun preserves assigned numbers and processes every remaining commit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github/release-config.json").write_text(
            json.dumps({"start_commit": "anchor"}))
        monkeypatch.setattr(release, "pending_commits", lambda start: ["done", "retry", "new"])
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.26-beta.1": "done", retry_tag: "retry"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.25": release_record(),
            "v1.0.26-beta.1": release_record(prerelease=True),
            retry_tag: release_record(draft=True, prerelease=True)})
        monkeypatch.setattr(release, "source_archive", lambda commit: source_zip)
        validate, publish = Mock(), Mock()
        monkeypatch.setattr(release, "validate_commit", validate)
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", Mock())
        release.publish_betas(["retry", "new"])
        assert [(call.args[0], call.args[1]) for call in publish.call_args_list] == [
            (retry_tag, "retry"), (new_tag, "new")]
        validate.assert_not_called()
        mock_commit_bump.assert_called_once_with("new")

    def test_unvalidated_candidate_cannot_publish_any_part_of_batch(self, monkeypatch, tmp_path, source_zip):
        """The publisher rejects an incomplete validation set before reserving any tag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github/release-config.json").write_text(
            json.dumps({"start_commit": "anchor"}))
        monkeypatch.setattr(release, "pending_commits", lambda start: ["validated", "unvalidated"])
        monkeypatch.setattr(release, "get_tags", lambda: {})
        monkeypatch.setattr(release, "get_releases", lambda: {"v1.0.25": release_record()})
        monkeypatch.setattr(release, "source_archive", lambda commit: source_zip)
        publish, reserve = Mock(), Mock()
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", reserve)
        with pytest.raises(ValueError, match="separate validation job"):
            release.publish_betas(["validated"])
        publish.assert_not_called()
        reserve.assert_not_called()

    def test_beta_publisher_accumulates_labels_and_resets_after_stable(self, monkeypatch,
                                                                     tmp_path, source_zip,
                                                                     mock_commit_bump):
        """Mixed merged PRs share a target until publication establishes a new baseline."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github/release-config.json").write_text(json.dumps({"start_commit": "anchor"}))
        commits = ["fix", "feature", "second-feature", "followup-fix", "breaking"]
        bumps = dict(zip(commits, ["patch", "minor", "minor", "patch", "major"]))
        mock_commit_bump.side_effect = lambda commit: bumps.get(commit, "patch")
        tags, records = {}, {"v1.0.23": release_record()}
        monkeypatch.setattr(release, "pending_commits", lambda start: commits)
        monkeypatch.setattr(release, "get_tags", lambda: tags)
        monkeypatch.setattr(release, "get_releases", lambda: records)
        monkeypatch.setattr(release, "source_archive", lambda commit: source_zip)
        monkeypatch.setattr(release, "validate_commit", Mock())
        monkeypatch.setattr(release, "reserve_tag", Mock())
        published = []

        def capture(tag, commit, asset, releases):
            with zipfile.ZipFile(asset) as archive:
                assert json.loads(archive.read("manifest.json"))["version"] == tag[1:]
            published.append((tag, commit))

        monkeypatch.setattr(release, "publish", capture)
        release.publish_betas(commits)
        assert published == list(zip([
            "v1.0.24-beta.1", "v1.1.0-beta.1", "v1.1.0-beta.2",
            "v1.1.0-beta.3", "v2.0.0-beta.1",
        ], commits))
        tags["v2.0.0"] = "breaking"
        records["v2.0.0"] = release_record()
        commits.append("next-fix")
        release.publish_betas(commits)
        assert published[-1] == ("v2.0.1-beta.1", "next-fix")
        assert len(published) == 6

    def test_promotion_rejects_conflicting_stable_tag(self, monkeypatch):
        """Promotion never moves a stable tag to a different source commit."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.25": "baseline", "v1.0.26-beta.1": "tested", "v1.0.26": "different"})
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

    @pytest.mark.parametrize("draft_reserved", [False, True])
    @pytest.mark.parametrize("beta_tag,stable_tag,next_beta", [
        ("v1.0.26-beta.3", "v1.0.26", "v1.0.27-beta.1"),
        ("v1.1.0-beta.2", "v1.1.0", "v1.1.1-beta.1"),
        ("v2.0.0-beta.1", "v2.0.0", "v2.0.1-beta.1"),
    ])
    def test_empty_input_promotes_existing_main_beta(self, monkeypatch, tmp_path, source_zip,
                                                    stable_tag, next_beta, draft_reserved,
                                                    beta_tag, mock_promotion_history):
        """Fresh and resumed promotions stamp the chosen version and drive the next beta cycle."""
        baseline_tag = "v1.0.25"
        tags = {baseline_tag: "baseline", beta_tag: "main-tip"}
        monkeypatch.setattr(release, "get_tags", lambda: tags)
        records = {baseline_tag: release_record(),
                   beta_tag: release_record(prerelease=True)}
        if draft_reserved:
            tags[stable_tag] = "main-tip"
            records[stable_tag] = release_record(draft=True)
        monkeypatch.setattr(release, "get_releases", lambda: records)
        monkeypatch.setenv("GH_REPO", "owner/repository")
        stable_notes = (f"## What's Changed\nAll changes since {baseline_tag}\n\n"
                        f"**Full Changelog**: {baseline_tag}...{stable_tag}")
        stamped = {}

        def capture_package(tag, commit, asset, releases, notes):
            with zipfile.ZipFile(asset) as archive:
                stamped["version"] = json.loads(archive.read("manifest.json"))["version"]
                assert archive.read("sensor.py") == b"VALUE = 42\n"

        reconcile, require_main = Mock(), Mock()
        publish = Mock(side_effect=capture_package)
        monkeypatch.setattr(release, "publish_betas", reconcile)
        monkeypatch.setattr(release, "require_on_main", require_main)
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", Mock())

        def command(*args):
            if args[:3] == ("git", "rev-parse", "origin/main"):
                return "main-tip"
            if args[:3] == ("gh", "release", "download"):
                directory = Path(args[args.index("--dir") + 1])
                assert args[3] == beta_tag
                release.package_source(source_zip, beta_tag, directory / "mijnted.zip")
            if args[:2] == ("gh", "api"):
                assert "repos/owner/repository/releases/generate-notes" in args
                assert f"tag_name={stable_tag}" in args
                assert "target_commitish=main-tip" in args
                assert f"previous_tag_name={baseline_tag}" in args
                return json.dumps({"body": stable_notes})
            return ""

        monkeypatch.setattr(release, "run", command)
        release.promote("")
        reconcile.assert_not_called()
        require_main.assert_called_once_with("main-tip")
        mock_promotion_history.assert_called_once_with("main-tip", "baseline")
        assert publish.call_args.args[:2] == (stable_tag, "main-tip")
        assert stamped["version"] == stable_tag[1:]
        assert publish.call_args.args[4] == stable_notes
        tags[stable_tag] = "main-tip"
        records[stable_tag] = release_record()
        assert release.next_beta(tags, release.latest_stable(records)) == next_beta

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

    @pytest.mark.parametrize("beta_tag,stable_tag", [
        ("v1.0.26-beta.1", "v1.0.26"), ("v1.1.0-beta.1", "v1.1.0"),
        ("v2.0.0-beta.1", "v2.0.0"),
    ])
    def test_completed_promotion_does_not_bump_again(self, monkeypatch, beta_tag, stable_tag):
        """Repeating a completed promotion cannot release the same code a second time."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            beta_tag: "tested", stable_tag: "tested"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            stable_tag: release_record(), beta_tag: release_record(prerelease=True)})
        monkeypatch.setattr(release, "require_on_main", Mock())
        publish, reserve = Mock(), Mock()
        monkeypatch.setattr(release, "publish", publish)
        monkeypatch.setattr(release, "reserve_tag", reserve)
        command = Mock()
        monkeypatch.setattr(release, "run", command)
        release.promote(beta_tag)
        publish.assert_not_called()
        reserve.assert_not_called()
        command.assert_not_called()

    def test_released_cycle_cannot_reserve_a_new_stable_tag(self, monkeypatch):
        """A later beta of an already-stable core cannot overwrite that stable release."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.26-beta.1": "tested", "v1.0.26": "other"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.26": release_record(), "v1.0.26-beta.1": release_record(prerelease=True)})
        monkeypatch.setattr(release, "require_on_main", Mock())
        reserve, publish = Mock(), Mock()
        monkeypatch.setattr(release, "reserve_tag", reserve)
        monkeypatch.setattr(release, "publish", publish)
        with pytest.raises(ValueError, match="newer version cycle"):
            release.promote("v1.0.26-beta.1")
        reserve.assert_not_called()
        publish.assert_not_called()

    def test_old_beta_cannot_reserve_a_tag(self, monkeypatch, mock_promotion_history):
        """A higher-numbered legacy beta cannot bypass the source-history check."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.1.0-beta.2": "older", "v1.0.27": "stable"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.1.0-beta.2": release_record(prerelease=True), "v1.0.27": release_record()})
        monkeypatch.setattr(release, "require_on_main", Mock())
        mock_promotion_history.side_effect = ValueError("Select a beta whose commit is newer")
        reserve, publish = Mock(), Mock()
        monkeypatch.setattr(release, "reserve_tag", reserve)
        monkeypatch.setattr(release, "publish", publish)
        with pytest.raises(ValueError, match="commit is newer"):
            release.promote("v1.1.0-beta.2")
        mock_promotion_history.assert_called_once_with("older", "stable")
        reserve.assert_not_called()
        publish.assert_not_called()

    def test_retry_cannot_change_an_unfinished_promotion_target(self, monkeypatch):
        """A historical unfinished promotion with a different target cannot be replaced."""
        monkeypatch.setattr(release, "get_tags", lambda: {
            "v1.0.25": "baseline", "v1.0.26-beta.1": "tested", "v2.0.0": "tested"})
        monkeypatch.setattr(release, "get_releases", lambda: {
            "v1.0.25": release_record(), "v2.0.0": release_record(draft=True),
            "v1.0.26-beta.1": release_record(prerelease=True)})
        monkeypatch.setattr(release, "require_on_main", Mock())
        reserve = Mock()
        monkeypatch.setattr(release, "reserve_tag", reserve)
        with pytest.raises(ValueError, match="unfinished promotion"):
            release.promote("v1.0.26-beta.1")
        reserve.assert_not_called()

    def test_tag_reservation_is_immutable_and_retryable(self, monkeypatch):
        """An upload failure leaves the commit's tag reserved without force-pushing."""
        monkeypatch.setenv("GH_TOKEN", "test-publisher-token")
        original = dict(release.os.environ)
        command = Mock(return_value="")
        monkeypatch.setattr(release, "run", command)
        release.reserve_tag("v1.0.26-beta.1", "tested", {})
        assert command.call_args.args == ("git", "push", "origin", "tested:refs/tags/v1.0.26-beta.1")
        env = command.call_args.kwargs["env"]
        assert env["GIT_CONFIG_COUNT"] == "1"
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        encoded = env["GIT_CONFIG_VALUE_0"].removeprefix("AUTHORIZATION: basic ")
        assert base64.b64decode(encoded).decode() == "x-access-token:test-publisher-token"
        assert dict(release.os.environ) == original
        command.reset_mock()
        release.reserve_tag("v1.0.26-beta.1", "tested", {"v1.0.26-beta.1": "tested"})
        command.assert_not_called()
        with pytest.raises(ValueError, match="different commit"):
            release.reserve_tag("v1.0.26-beta.1", "tested", {"v1.0.26-beta.1": "other"})

    def test_new_tag_requires_explicit_transient_authentication(self, monkeypatch):
        """Missing publisher authentication cannot fall back to persisted checkout credentials."""
        monkeypatch.delenv("GH_TOKEN", raising=False)
        command = Mock()
        monkeypatch.setattr(release, "run", command)
        with pytest.raises(ValueError, match="GH_TOKEN"):
            release.reserve_tag("v1.0.26-beta.1", "tested", {})
        command.assert_not_called()

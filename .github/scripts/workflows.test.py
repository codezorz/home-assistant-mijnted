"""Protect credential boundaries between executable candidates and trusted CI jobs."""

from pathlib import Path
import re

import yaml


WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"


def workflow(name):
    """Read workflow structure without YAML 1.1 converting the on key to a boolean."""
    return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


class TestValidationPermissions:
    """Only a fresh, non-executing report job can write repository checks."""

    def test_pr_test_execution_has_read_only_permissions_and_no_persisted_git_auth(self):
        """Dependency and test execution cannot obtain a write-capable checkout token."""
        config = workflow("validate-code.yml")
        job = config["jobs"]["test"]
        assert job["name"] == "Validate code"
        assert config["permissions"] == {"contents": "read"}
        assert job.get("permissions", config["permissions"]) == {"contents": "read"}
        checkouts = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
        assert checkouts and all(step["with"]["persist-credentials"] == "false" for step in checkouts)
        assert not any("dorny/test-reporter@" in step.get("uses", "") for step in job["steps"])

    def test_report_writes_are_isolated_from_pr_execution(self):
        """A separate runner consumes only JUnit data with a pinned reporter implementation."""
        jobs = workflow("validate-code.yml")["jobs"]
        report = jobs["report"]
        assert report["needs"] == "test"
        assert report["permissions"] == {"contents": "read", "actions": "read", "checks": "write"}
        assert "head.repo.fork == false" in report["if"]
        assert "always()" in report["if"]
        assert len(report["steps"]) == 1
        step = report["steps"][0]
        assert re.fullmatch(r"dorny/test-reporter@[0-9a-f]{40}", step["uses"])
        assert "run" not in step
        uploads = [item for item in jobs["test"]["steps"]
                   if item.get("uses", "").startswith("actions/upload-artifact@")]
        assert len(uploads) == 1
        assert step["with"]["artifact"] == uploads[0]["with"]["name"]


class TestReleasePermissions:
    """No dependency/candidate execution shares a runner with release credentials."""

    def test_planning_and_validation_have_no_app_secrets(self):
        """Read-only jobs produce the immutable plan and execute all candidate tests."""
        config = workflow("beta-release.yml")
        assert all(value == "read" for value in config["permissions"].values())
        jobs = config["jobs"]
        assert jobs["validate"]["needs"] == "plan"
        assert jobs["validate"]["permissions"] == {"contents": "read"}
        for name in ("plan", "validate"):
            job = jobs[name]
            assert "secrets." not in str(job)
            assert "create-github-app-token@" not in str(job)
            assert "release-app.outputs.token" not in str(job)
        commands = [step.get("run", "") for step in jobs["validate"]["steps"]]
        assert any("release.py validate" in command for command in commands)
        assert not any("release.py beta" in command for command in commands)

    def test_publisher_only_runs_after_the_planned_batch_passes_validation(self):
        """The fresh publisher receives the trusted plan and executes no candidate code."""
        jobs = workflow("beta-release.yml")["jobs"]
        publisher = jobs["publish"]
        assert set(publisher["needs"]) == {"plan", "validate"}
        assert "always()" not in publisher.get("if", "")
        steps = publisher["steps"]
        token_index = next(index for index, step in enumerate(steps)
                           if step.get("uses", "").startswith("actions/create-github-app-token@"))
        assert all("uses" not in step for step in steps[token_index + 1:])
        commands = [step.get("run", "") for step in steps]
        assert not any(re.search(r"\b(pip|pytest|validate)\b", command) for command in commands)
        publishing = steps[-1]
        assert "--validated-commits" in publishing["run"]
        assert publishing["env"]["VALIDATED_COMMITS"] == "${{ needs.plan.outputs.commits }}"
        assert publishing["env"]["RELEASE_SNAPSHOT"] == "${{ needs.plan.outputs.snapshot }}"

    def test_release_checkouts_never_persist_auth_and_all_actions_are_immutable(self):
        """Git write authentication is transient and never stored by checkout."""
        for name in ("beta-release.yml", "promote-release.yml"):
            for job in workflow(name)["jobs"].values():
                for step in job["steps"]:
                    if "uses" not in step:
                        continue
                    assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"])
                    if step["uses"].startswith("actions/checkout@"):
                        assert step["with"]["persist-credentials"] == "false"
                        assert "token" not in step["with"]

    def test_verify_only_never_checks_out_or_executes_repository_code(self):
        """Credential verification can run on a topic branch without candidate execution."""
        job = workflow("beta-release.yml")["jobs"]["verify"]
        assert "inputs.verify_only" in job["if"]
        assert "actions/checkout@" not in str(job)
        assert "release.py" not in str(job)
        assert "pip install" not in str(job)

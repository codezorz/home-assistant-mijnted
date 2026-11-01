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

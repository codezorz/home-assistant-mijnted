"""Verify Claude's shared-guidance index without loading guidance bodies.

Exercises the configured command, worktree-root discovery, quoted metadata,
and absent/invalid guidance handling using local Git repositories only.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "list-guidance.sh"


@pytest.fixture
def bash():
    """Locate Git Bash on Windows or the native Bash executable elsewhere."""
    git = shutil.which("git")
    if not git:
        pytest.skip("Git is required for guidance-hook tests")
    if os.name == "nt":
        # Git can be on PATH from cmd/, bin/, or mingw64/bin/.
        for parent in Path(git).resolve().parents:
            candidate = parent / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
        pytest.skip("Git Bash is required on Windows (not the WSL launcher)")
    executable = shutil.which("bash")
    if not executable:
        pytest.skip("Bash is required for guidance-hook tests")
    return executable


@pytest.fixture
def repository(tmp_path):
    """Create an uncommitted temporary repository with spaces in its path."""
    root = tmp_path / "repo with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _run(bash, root, *, cwd=None, command=None):
    """Run the hook with a project-root environment and capture its index."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": root.as_posix()}
    args = [bash, "-c", command] if command else [bash, HOOK.as_posix()]
    return subprocess.run(
        args, cwd=cwd or root, env=env, capture_output=True,
        text=True, encoding="utf-8", check=True,
    )


class TestAgentGuidanceHook:
    """Verify portable invocation and metadata-only discovery."""

    def test_quoted_headers_and_crlf_only_emit_metadata(self, bash, repository):
        """Quoted CRLF headers -> readable index without body content."""
        skill = repository / ".agents/skills/example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_bytes(
            b"---\r\nname: 'example'\r\ndescription: \"Use for example tasks.\"\r\n"
            b"---\r\nPRIVATE BODY SENTINEL\r\ndescription: body must not load\r\n"
        )
        instruction = repository / ".github/instructions/example.instructions.md"
        instruction.parent.mkdir(parents=True)
        instruction.write_text(
            '---\napplyTo: "src/**,tests/**"\ndescription: Example scope.\n'
            '---\nPRIVATE INSTRUCTION SENTINEL\n', encoding="utf-8",
        )
        result = _run(bash, repository)
        assert ".agents/skills/example/SKILL.md" in result.stdout
        assert "Use for example tasks." in result.stdout
        assert "applyTo: src/**,tests/**" in result.stdout
        assert "PRIVATE" not in result.stdout
        assert "body must not load" not in result.stdout
        assert repository.as_posix() not in result.stdout
        assert not result.stderr

    def test_configured_command_handles_spaces_from_another_directory(self, bash, repository, tmp_path):
        """Configured command + spaced project root -> correct script executes."""
        destination = repository / ".claude/hooks/list-guidance.sh"
        destination.parent.mkdir(parents=True)
        shutil.copyfile(HOOK, destination)
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        event = settings["hooks"]["SessionStart"][0]
        assert set(event["matcher"].split("|")) == {"startup", "resume", "clear", "compact"}
        result = _run(bash, repository, cwd=tmp_path, command=event["hooks"][0]["command"])
        assert "## Repository guidance" in result.stdout
        assert "### Shared skills" not in result.stdout
        assert "### Scoped instructions" not in result.stdout
        assert not result.stderr

    def test_invalid_headers_are_reported_not_advertised(self, bash, repository):
        """Missing frontmatter/description -> warning and no false skill entry."""
        skill = repository / ".agents/skills/broken/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("name: broken\ndescription: Not a header.\n", encoding="utf-8")
        instruction = repository / ".github/instructions/broken.instructions.md"
        instruction.parent.mkdir(parents=True)
        instruction.write_text('---\napplyTo: "**"\n---\nBODY\n', encoding="utf-8")
        result = _run(bash, repository)
        assert "Not a header." not in result.stdout
        assert "BODY" not in result.stdout
        assert "Invalid skill metadata" in result.stderr
        assert "Invalid instruction metadata" in result.stderr

    def test_current_worktree_is_discovered_from_a_subdirectory(self, bash):
        """Nested cwd without project env -> current worktree guidance loads."""
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        result = subprocess.run(
            [bash, HOOK.as_posix()], cwd=ROOT / "doc", env=env,
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        for name in ("git-worktrees", "doc-sync", "pr-workflow", "validation"):
            assert f".agents/skills/{name}/SKILL.md" in result.stdout
        assert ".github/instructions/agent-tooling.instructions.md" in result.stdout
        assert not result.stderr

    def test_outside_git_is_a_noop(self, bash, tmp_path):
        """Non-repository project directory -> quiet successful hook."""
        result = _run(bash, tmp_path)
        assert not result.stdout
        assert not result.stderr

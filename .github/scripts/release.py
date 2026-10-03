"""Publish validated beta packages and promote their exact contents to stable."""

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


TAG_PATTERN = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-beta\.([1-9]\d*))?")
ASSET_NAME = "mijnted.zip"
INTEGRATION = "custom_components/mijnted/"


def run(*args: str, cwd: Path | None = None) -> str:
    """Run a checked command without a shell."""
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def parse_tag(tag: str) -> tuple[tuple[int, int, int], int | None]:
    """Accept only canonical stable and numbered beta SemVer tags."""
    match = TAG_PATTERN.fullmatch(tag)
    if not match:
        raise ValueError(f"Invalid release tag: {tag}")
    return tuple(int(match[index]) for index in (1, 2, 3)), (
        int(match[4]) if match[4] else None
    )


def format_version(version: tuple[int, int, int]) -> str:
    """Render the core SemVer version."""
    return ".".join(map(str, version))


def next_beta(tags: dict[str, str], stable: tuple[int, int, int],
              requested: str | None = None) -> str:
    """Continue the active cycle or start the next patch after stable."""
    parsed = [(tag, *parse_tag(tag)) for tag in tags if TAG_PATTERN.fullmatch(tag)]
    active = [version for _, version, beta in parsed if beta is not None and version > stable]
    target = max(active, default=(stable[0], stable[1], stable[2] + 1))
    if requested:
        requested_version, beta = parse_tag(f"v{requested}")
        if beta is not None:
            raise ValueError("next_version must be a stable core version")
        # A released override is consumed automatically; no bookkeeping commit is needed.
        if requested_version > stable:
            if requested_version < target:
                raise ValueError("next_version cannot move an active beta cycle backwards")
            target = requested_version
    number = max((beta for _, version, beta in parsed
                  if version == target and beta is not None), default=0) + 1
    return f"v{format_version(target)}-beta.{number}"


def get_tags() -> dict[str, str]:
    """Resolve annotated and lightweight tags to immutable commit IDs."""
    return {tag: run("git", "rev-parse", f"refs/tags/{tag}^{{commit}}")
            for tag in run("git", "tag", "--list", "v*").splitlines()
            if TAG_PATTERN.fullmatch(tag)}


def get_releases() -> dict[str, dict]:
    """Read every release, including draft state needed for retry recovery."""
    pages = json.loads(run("gh", "api", "--paginate", "--slurp",
                           f"repos/{os.environ['GH_REPO']}/releases"))
    return {release["tag_name"]: release for page in pages for release in page}


def latest_stable(releases: dict[str, dict]) -> tuple[int, int, int]:
    """Use published stable releases rather than development manifest metadata."""
    versions = [parse_tag(tag)[0] for tag, release in releases.items()
                if TAG_PATTERN.fullmatch(tag) and parse_tag(tag)[1] is None
                and not release["draft"] and not release["prerelease"]]
    if not versions:
        raise ValueError("A published stable release is required to seed version allocation")
    return max(versions)


def require_on_main(commit: str) -> None:
    """Reject commits outside the fetched main history."""
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"], check=True)


def pending_commits(start: str) -> list[str]:
    """Include every newly reachable commit, not only each push's tip."""
    require_on_main(start)
    return run("git", "rev-list", "--reverse", "--topo-order",
               f"{start}..origin/main").splitlines()


def source_archive(commit: str) -> bytes:
    """Export only tracked source from the exact commit being released."""
    return subprocess.check_output(["git", "archive", "--format=zip", commit])


def validate_commit(commit: str, directory: Path) -> None:
    """Run syntax checks and the existing suite against each candidate commit."""
    # Repository-discovery tests need Git metadata, which an archive export omits.
    run("git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
        str(Path.cwd()), str(directory))
    run("git", "checkout", "--quiet", "--detach", commit, cwd=directory)
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_test.txt"],
                   cwd=directory, check=True)
    manifest = json.loads((directory / INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    if manifest["requirements"]:
        subprocess.run([sys.executable, "-m", "pip", "install", *manifest["requirements"]],
                       cwd=directory, check=True)
    subprocess.run([sys.executable, "-m", "compileall", INTEGRATION], cwd=directory, check=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=directory, check=True)


def write_package(files: dict[str, bytes], tag: str, destination: Path) -> None:
    """Write a reproducible flat HACS ZIP with only the version metadata changed."""
    parse_tag(tag)
    manifest = json.loads(files["manifest.json"])
    if manifest["domain"] != "mijnted":
        raise ValueError("Unexpected integration domain")
    files = dict(files)
    manifest["version"] = tag[1:]
    files["manifest.json"] = (json.dumps(manifest, indent=4) + "\n").encode()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            if name.startswith("/") or "\\" in name or ".." in Path(name).parts:
                raise ValueError(f"Unsafe package path: {name}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def package_source(source: bytes, tag: str, destination: Path) -> None:
    """Package the integration at the ZIP root, as required by HACS."""
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        files = {name[len(INTEGRATION):]: archive.read(name) for name in archive.namelist()
                 if name.startswith(INTEGRATION) and not name.endswith("/")
                 and "__pycache__" not in Path(name).parts and not name.endswith(".pyc")}
    write_package(files, tag, destination)


def promote_package(source: Path, beta_tag: str, stable_tag: str, destination: Path) -> None:
    """Preserve the tested beta asset's files while changing its manifest version."""
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    if json.loads(files["manifest.json"])["version"] != beta_tag[1:]:
        raise ValueError("Beta asset manifest does not match its release tag")
    if parse_tag(beta_tag)[0] != parse_tag(stable_tag)[0]:
        raise ValueError("Promotion must retain the beta's core version")
    write_package(files, stable_tag, destination)


def publish(tag: str, commit: str, asset: Path, releases: dict[str, dict],
            notes: str | None = None) -> None:
    """Create a draft, attach the package, then publish; retries repair drafts."""
    existing = releases.get(tag)
    if existing and not existing["draft"]:
        return
    beta = parse_tag(tag)[1] is not None
    if not existing:
        args = ["gh", "release", "create", tag, "--target", commit, "--draft", "--title", tag]
        args += ["--notes", notes] if notes is not None else ["--generate-notes"]
        if beta:
            args += ["--prerelease"]
        run(*args)
    run("gh", "release", "upload", tag, str(asset), "--clobber")
    run("gh", "release", "edit", tag, "--draft=false",
        f"--prerelease={'true' if beta else 'false'}",
        f"--latest={'false' if beta else 'true'}")
    print(f"Published {tag} at {commit}", flush=True)


def reserve_tag(tag: str, commit: str, tags: dict[str, str]) -> None:
    """Reserve an immutable tag before drafting so failed uploads retain allocation."""
    if tag in tags:
        if tags[tag] != commit:
            raise ValueError(f"{tag} already points to a different commit")
        return
    # A draft release need not create its tag until publication. Reserve it explicitly.
    run("git", "push", "origin", f"{commit}:refs/tags/{tag}")


def publish_betas() -> None:
    """Reconcile the complete post-bootstrap main history with beta releases."""
    config = json.loads(Path(".github/release-config.json").read_text(encoding="utf-8"))
    tags, releases = get_tags(), get_releases()
    stable = latest_stable(releases)
    for commit in pending_commits(config["start_commit"]):
        candidates = [tag for tag, target in tags.items()
                      if target == commit and parse_tag(tag)[1] is not None]
        if any(tag in releases and not releases[tag]["draft"] for tag in candidates):
            continue
        tag = candidates[0] if candidates else next_beta(tags, stable, config["next_version"])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = source_archive(commit)
            checkout = directory / "source"
            validate_commit(commit, checkout)
            asset = directory / ASSET_NAME
            package_source(source, tag, asset)
            reserve_tag(tag, commit, tags)
            publish(tag, commit, asset, releases)
        tags[tag] = commit
        releases[tag] = {"draft": False, "prerelease": True}


def beta_for_main(tags: dict[str, str], releases: dict[str, dict]) -> str:
    """Find the published beta for the exact current main commit."""
    commit = run("git", "rev-parse", "origin/main")
    candidates = [tag for tag, target in tags.items() if target == commit
                  and parse_tag(tag)[1] is not None and tag in releases
                  and not releases[tag]["draft"] and releases[tag]["prerelease"]]
    if not candidates:
        raise ValueError("Current main has no published beta to promote")
    return max(candidates, key=parse_tag)


def promote(beta_tag: str = "") -> None:
    """Promote only an existing published beta from main, without rebuilding code."""
    beta_tag = beta_tag.strip()
    if not beta_tag:
        beta_tag = beta_for_main(get_tags(), get_releases())
    version, beta = parse_tag(beta_tag)
    if beta is None:
        raise ValueError("Select a beta tag, not a stable release")
    tags, releases = get_tags(), get_releases()
    release = releases.get(beta_tag)
    if not release or release["draft"] or not release["prerelease"]:
        raise ValueError("Select a published GitHub prerelease")
    commit = tags[beta_tag]
    require_on_main(commit)
    stable_tag = f"v{format_version(version)}"
    if stable_tag in tags and tags[stable_tag] != commit:
        raise ValueError("Stable tag already points to a different commit")
    if stable_tag in releases and not releases[stable_tag]["draft"]:
        print(f"{stable_tag} is already published", flush=True)
        return
    if version <= latest_stable(releases):
        raise ValueError("Cannot publish a version older than or equal to the latest stable")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        run("gh", "release", "download", beta_tag, "--pattern", ASSET_NAME,
            "--dir", str(directory))
        asset = directory / "stable" / ASSET_NAME
        asset.parent.mkdir()
        promote_package(directory / ASSET_NAME, beta_tag, stable_tag, asset)
        notes = f"Promoted from {beta_tag}; source commit `{commit}`.\n\n" + (release["body"] or "")
        reserve_tag(stable_tag, commit, tags)
        publish(stable_tag, commit, asset, releases, notes)


def main() -> None:
    """Dispatch the two publishing operations with fresh main and tag refs."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("beta")
    commands.add_parser("promote").add_argument("beta_tag", nargs="?", default="")
    args = parser.parse_args()
    run("git", "fetch", "origin", "main", "--tags")
    if args.command == "beta":
        publish_betas()
    else:
        promote(args.beta_tag)


if __name__ == "__main__":
    main()

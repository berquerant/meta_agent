#!/usr/bin/env python3
"""Release script to bump version, create git tag, and push to remote."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SEMVER_REGEX = re.compile(
    r"^v?(?P<version>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?)$"
)


def validate_semver(version_str: str) -> str:
    """Validate that version_str is a valid SemVer string and return normalized version."""
    match = SEMVER_REGEX.match(version_str)
    if not match:
        raise ValueError(f"Invalid SemVer version string: '{version_str}'")
    return match.group("version")


def get_existing_tags() -> set[str]:
    """Get existing git tags from local repository and remote if reachable."""
    tags = set()
    # Local tags
    res = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True, check=True)
    for tag in res.stdout.splitlines():
        tag = tag.strip()
        if tag:
            tags.add(tag)

    # Remote tags
    try:
        remote_res = subprocess.run(
            ["git", "ls-remote", "--tags", "origin"], capture_output=True, text=True, timeout=10
        )
        if remote_res.returncode == 0:
            for line in remote_res.stdout.splitlines():
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    ref = parts[1]
                    tag_name = ref.removeprefix("refs/tags/").removesuffix("^{}")
                    if tag_name:
                        tags.add(tag_name)
    except Exception as e:
        print(f"Warning: Failed to fetch remote tags: {e}", file=sys.stderr)

    return tags


def update_pyproject_version(pyproject_path: Path, new_version: str, dry_run: bool = False) -> None:
    """Update version in pyproject.toml."""
    content = pyproject_path.read_text(encoding="utf-8")
    updated_content, count = re.subn(
        r'(^version\s*=\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise RuntimeError(f"Could not find version field in {pyproject_path}")

    if dry_run:
        print(f"[DRY-RUN] Updated {pyproject_path} version to '{new_version}'")
    else:
        pyproject_path.write_text(updated_content, encoding="utf-8")
        print(f"Updated {pyproject_path} version to '{new_version}'")


def update_uv_lock(dry_run: bool = False) -> None:
    """Run `uv lock` to update uv.lock."""
    if dry_run:
        print("[DRY-RUN] Would run `uv lock`")
    else:
        print("Updating uv.lock...")
        subprocess.run(["uv", "lock"], check=True)


def commit_tag_push(version: str, dry_run: bool = False, no_push: bool = False) -> None:
    """Stage, commit, tag, and push changes."""
    cmd_stage = ["git", "add", "pyproject.toml", "uv.lock"]
    cmd_commit = ["git", "commit", "-m", f"bump version to {version}"]
    cmd_tag = ["git", "tag", "-a", version, "-m", f"Release {version}"]
    cmd_push_head = ["git", "push", "origin", "HEAD"]
    cmd_push_tag = ["git", "push", "origin", version]

    if dry_run:
        print("[DRY-RUN] Executing git operations:")
        print(f"  {' '.join(cmd_stage)}")
        print(f"  {' '.join(cmd_commit)}")
        print(f"  {' '.join(cmd_tag)}")
        if not no_push:
            print(f"  {' '.join(cmd_push_head)}")
            print(f"  {' '.join(cmd_push_tag)}")
        return

    print("Staging modified version files...")
    subprocess.run(cmd_stage, check=True)

    print(f"Creating commit for version {version}...")
    subprocess.run(cmd_commit, check=True)

    print(f"Creating git tag {version}...")
    subprocess.run(cmd_tag, check=True)

    if no_push:
        print("Skipping push as --no-push was set.")
    else:
        print("Pushing commit to remote...")
        subprocess.run(cmd_push_head, check=True)
        print(f"Pushing tag {version} to remote...")
        subprocess.run(cmd_push_tag, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump project version, tag, and push.")
    parser.add_argument("version", help="New version string (e.g. 0.5.0)")
    parser.add_argument("--dry-run", action="store_true", help="Perform validation and show changes without committing/pushing.")
    parser.add_argument("--no-push", action="store_true", help="Commit and tag locally, but do not push to remote.")
    args = parser.parse_args()

    # 1. Validate SemVer
    try:
        version = validate_semver(args.version)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Target version: {version}")

    # 2. Check if version tag already exists
    existing_tags = get_existing_tags()
    if version in existing_tags or f"v{version}" in existing_tags:
        print(f"Error: Version tag '{version}' (or 'v{version}') already exists in git history!", file=sys.stderr)
        sys.exit(1)

    # 3. Locate pyproject.toml
    root_dir = Path(__file__).resolve().parent.parent
    pyproject_path = root_dir / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}", file=sys.stderr)
        sys.exit(1)

    # 4. Update files
    try:
        update_pyproject_version(pyproject_path, version, dry_run=args.dry_run)
        update_uv_lock(dry_run=args.dry_run)
    except Exception as e:
        print(f"Error updating project version: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Git operations
    try:
        commit_tag_push(version, dry_run=args.dry_run, no_push=args.no_push)
    except Exception as e:
        print(f"Error executing git operations: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully released version {version}!")


if __name__ == "__main__":
    main()

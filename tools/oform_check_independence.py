#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Lightweight repository-independence checks for O-Form.

Fails on Blender *source* remotes and on automation that clearly synchronizes
Blender upstream into this tree. Does not ban copyright notices, license
texts, API names, or historical comments that mention Blender.

Usage:
  python tools/oform_check_independence.py
  python tools/oform_check_independence.py --root D:\\o-form
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Source remotes that must not be configured for routine O-Form development.
BLENDER_SOURCE_REMOTE = re.compile(
    r"(github\.com[/:]blender/blender|"
    r"projects\.blender\.org[/:]blender/blender|"
    r"git\.blender\.org[/:]blender/blender)",
    re.IGNORECASE,
)

# Patterns that indicate active upstream *synchronization* (not mere mentions).
SYNC_DOC_PATTERNS = [
    re.compile(r"git\s+remote\s+add\s+.*blender/blender", re.IGNORECASE),
    re.compile(r"git\s+fetch\s+(upstream|blender)\b", re.IGNORECASE),
    re.compile(r"git\s+merge\s+(upstream|blender)/", re.IGNORECASE),
    re.compile(r"git\s+rebase\s+(upstream|blender)/", re.IGNORECASE),
    re.compile(r"track\s+Blender\s+upstream", re.IGNORECASE),
    re.compile(r"synchronize?\s+with\s+Blender\s+upstream", re.IGNORECASE),
    re.compile(r"pull\s+from\s+projects\.blender\.org/blender/blender", re.IGNORECASE),
]

WORKFLOW_SYNC = re.compile(
    r"(blender/blender|projects\.blender\.org).{0,80}(git\s+fetch|git\s+merge|git\s+rebase|sync)",
    re.IGNORECASE | re.DOTALL,
)

DOC_ROOTS = ("docs", "CONTRIBUTING.md", "README.md", ".github")
SKIP_DIR_NAMES = {
    ".git",
    "lib",
    "extern",
    "__pycache__",
    "node_modules",
    "tests",
    "intern",
    "source",
}


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git failed")
    return result.stdout


def check_remotes(root: Path, errors: list[str], warnings: list[str]) -> None:
    try:
        out = run_git(root, "remote", "-v")
    except RuntimeError as exc:
        errors.append(f"git remote -v failed: {exc}")
        return
    if not out.strip():
        warnings.append("No git remotes configured (unexpected for a clone).")
        return
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if not BLENDER_SOURCE_REMOTE.search(url):
            continue
        # LFS helper remotes historically used for assets — warn, do not treat as OK.
        if name in {"lfs-fallback", "lfs"} or "lfs" in name.lower():
            warnings.append(
                f"Remote {name!r} points at Blender infrastructure ({url}). "
                "Remove it after LFS fetch; it must not be used as source upstream."
            )
        else:
            errors.append(
                f"Blender source remote configured: {name} -> {url}. "
                "O-Form development must not depend on Blender upstream. "
                f"After confirming the name, run: git remote remove {name}"
            )


def iter_text_files(root: Path):
    # Explicit product docs / github / contributing.
    for rel in DOC_ROOTS:
        path = root / rel
        if path.is_file() and path.suffix.lower() in {".md", ".yml", ".yaml", ".txt"}:
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in {".md", ".yml", ".yaml", ".txt"}:
                    yield child
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for child in workflows.rglob("*"):
            if child.is_file() and child.suffix.lower() in {".yml", ".yaml"}:
                yield child
    # Focused script locations (avoid scanning all of source/).
    for rel in ("tools", "build_files/utils", "release/release_notes"):
        base = root / rel
        if not base.exists():
            continue
        for child in base.rglob("*"):
            if not child.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in child.parts):
                continue
            if child.suffix.lower() in {".py", ".sh", ".cmd", ".bat", ".ps1", ".yml", ".yaml", ".md"}:
                yield child


def check_docs_and_automation(root: Path, errors: list[str], warnings: list[str]) -> None:
    seen: set[Path] = set()
    for path in iter_text_files(root):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"Could not read {path}: {exc}")
            continue
        rel = path.relative_to(root).as_posix()
        # Skip this checker and audit reports that *document* forbidden patterns.
        if rel.endswith("oform_check_independence.py"):
            continue
        if rel.startswith("docs/maintenance/") and "upstream" in rel:
            continue
        if path.suffix.lower() in {".yml", ".yaml"} and ".github/workflows" in rel.replace("\\", "/"):
            if WORKFLOW_SYNC.search(text):
                errors.append(f"Workflow may synchronize Blender upstream: {rel}")
            if BLENDER_SOURCE_REMOTE.search(text) and re.search(
                r"\b(fetch|merge|rebase|sync)\b", text, re.IGNORECASE
            ):
                errors.append(f"Workflow references Blender source with sync verbs: {rel}")
            continue
        for pattern in SYNC_DOC_PATTERNS:
            if pattern.search(text):
                # Allow explicit "do not" / "must not" policy sentences.
                window = text[max(0, pattern.search(text).start() - 40) : pattern.search(text).end() + 40]
                if re.search(r"\b(do not|must not|never|forbidden|no blender upstream)\b", window, re.IGNORECASE):
                    continue
                errors.append(f"Upstream sync instruction in {rel}: /{pattern.pattern}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of tools/)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not (root / ".git").exists():
        errors.append(f"Not a git repository: {root}")
    else:
        check_remotes(root, errors, warnings)
    check_docs_and_automation(root, errors, warnings)

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"oform_check_independence: FAILED ({len(errors)} error(s))")
        return 1
    print("oform_check_independence: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

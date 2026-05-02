"""Regression test: prevent the deprecated `gpt-5.5` model id from re-entering
the docs / examples / source.

`openai.gpt-5.5` is not a real model in OCI's catalogue (the actual id is
`openai.gpt-5`). This test scans the codebase and fails if the deprecated
form reappears, so a future copy-paste can't quietly reintroduce a bad
quickstart.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Files / directories scanned for the deprecated identifier.
SCAN_ROOTS = [
    REPO_ROOT / "src" / "locus",
    REPO_ROOT / "examples",
    REPO_ROOT / "docs",
    REPO_ROOT / "README.md",
]

# Files we cannot easily change (binary, third-party). Empty for now.
ALLOWLIST: set[Path] = set()

# Regex that matches the deprecated identifier in any context.
DEPRECATED_PATTERN = re.compile(r"\bgpt-5\.5\b")


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return [
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".md", ".rst", ".svg", ".yaml", ".yml", ".toml"}
        and "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and "site" not in p.parts
    ]


def test_no_deprecated_gpt_5_5_anywhere():
    """Fail fast if `gpt-5.5` reappears in any documented surface."""
    offenders: list[tuple[Path, int, str]] = []

    for root in SCAN_ROOTS:
        for path in _iter_files(root):
            if path in ALLOWLIST:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(lines, start=1):
                if DEPRECATED_PATTERN.search(line):
                    offenders.append((path.relative_to(REPO_ROOT), lineno, line.strip()))

    assert not offenders, (
        "Deprecated model id `gpt-5.5` found in:\n"
        + "\n".join(f"  {p}:{lineno}  {line}" for p, lineno, line in offenders[:20])
        + (f"\n  ... and {len(offenders) - 20} more" if len(offenders) > 20 else "")
        + "\n\nUse `openai.gpt-5` (or a specific successor like `openai.gpt-5.1`) instead."
    )

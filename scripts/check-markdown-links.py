#!/usr/bin/env python3
"""Validate repository-local links and anchors in tracked or new Markdown files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\(\s*(?P<target><[^>]+>|[^)\s]+)"
    r"(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
NON_SLUG_CHARACTER = re.compile(r"[^\w\- ]", re.UNICODE)
WHITESPACE = re.compile(r"\s+")


def markdown_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "*.md",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        REPOSITORY_ROOT / line for line in result.stdout.splitlines() if line.strip()
    )


def github_slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[`*_~]", "", text)
    text = NON_SLUG_CHARACTER.sub("", text.casefold())
    return WHITESPACE.sub("-", text.strip())


def anchors_for(markdown_file: Path) -> set[str]:
    anchors: set[str] = set()
    duplicate_counts: dict[str, int] = {}
    in_fence = False

    for line in markdown_file.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        base = github_slug(match.group("text"))
        count = duplicate_counts.get(base, 0)
        duplicate_counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")

    return anchors


def main() -> int:
    errors: list[str] = []
    local_link_count = 0
    anchor_cache: dict[Path, set[str]] = {}
    files = markdown_files()

    for source in files:
        in_fence = False
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            for match in MARKDOWN_LINK.finditer(line):
                raw_target = match.group("target").strip("<>")
                parsed = urlsplit(raw_target)
                if parsed.scheme or raw_target.startswith("//"):
                    continue

                local_link_count += 1
                target_path = unquote(parsed.path)
                destination = (
                    source
                    if not target_path
                    else (source.parent / target_path).resolve()
                )
                try:
                    destination.relative_to(REPOSITORY_ROOT)
                except ValueError:
                    errors.append(
                        f"{source.relative_to(REPOSITORY_ROOT)}:{line_number}: "
                        f"link escapes repository: {raw_target}"
                    )
                    continue

                if not destination.exists():
                    errors.append(
                        f"{source.relative_to(REPOSITORY_ROOT)}:{line_number}: "
                        f"missing target: {raw_target}"
                    )
                    continue

                if parsed.fragment and destination.suffix.casefold() == ".md":
                    anchors = anchor_cache.setdefault(
                        destination, anchors_for(destination)
                    )
                    expected_anchor = unquote(parsed.fragment).casefold()
                    if expected_anchor not in anchors:
                        errors.append(
                            f"{source.relative_to(REPOSITORY_ROOT)}:{line_number}: "
                            f"missing anchor #{parsed.fragment} in "
                            f"{destination.relative_to(REPOSITORY_ROOT)}"
                        )

    if errors:
        print("Markdown link validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Markdown link validation passed "
        f"({len(files)} files; {local_link_count} local links)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

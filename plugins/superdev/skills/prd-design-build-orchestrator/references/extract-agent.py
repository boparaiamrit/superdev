#!/usr/bin/env python3
"""
extract-agent.py — extract a single agent's definition from an agent-source markdown file.

Usage:
  python3 extract-agent.py <source-file> <agent-name>

Writes the agent's body (the contents of the ```markdown ... ``` block under
"## <agent-name>") to stdout. Returns non-zero if the agent isn't found.

Strategy:
  1. Section boundary detection: a "## <name>" heading is a real agent
     boundary iff <name> is kebab-case (e.g. "security-inventory"). Agent
     prompt bodies contain their own subheadings like "## Your inputs" and
     "## Strict rules" which contain spaces and DON'T match kebab-case, so
     they are correctly ignored.

  2. Within the agent's section: take the body between the FIRST column-0
     ```markdown line and the LAST column-0 ``` line. This handles nested
     ```bash / ```ts / plain ``` fences correctly because well-formed markdown
     pairs every opener with a closer, so the outer markdown fence's matching
     closer is always the last fence in the section.

  --- lines (YAML frontmatter delimiters inside the body, visual dividers
  between agents in the source) are ignored.
"""

import re
import sys
from pathlib import Path

_HEADING_RE = re.compile(r"^##\s+(\S.*)$")
_AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_MARKDOWN_OPEN_RE = re.compile(r"^```markdown\s*$")
_FENCE_RE = re.compile(r"^```")


def find_section(lines, agent):
    """Return (start_idx, end_idx_exclusive) of the named agent's section."""
    start = -1
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.rstrip("\n"))
        if not m:
            continue
        name = m.group(1).strip()
        if not _AGENT_NAME_RE.match(name):
            # subheading inside an agent body (e.g. "Your inputs"); skip
            continue
        if start < 0:
            if name == agent:
                start = i
            continue
        # Past the agent's heading and just hit another agent's heading
        return (start, i)
    if start < 0:
        return (-1, -1)
    return (start, len(lines))


def extract_body(section_lines):
    """Body inside the outer ```markdown ... ``` fence.

    First column-0 ```markdown opens; last column-0 ``` closes. Everything
    between (exclusive) is the body.
    """
    open_idx = -1
    last_fence_idx = -1
    for i, line in enumerate(section_lines):
        stripped = line.rstrip("\n")
        if open_idx < 0:
            if _MARKDOWN_OPEN_RE.match(stripped):
                open_idx = i
        else:
            if _FENCE_RE.match(stripped):
                last_fence_idx = i
    if open_idx < 0 or last_fence_idx <= open_idx:
        return []
    return [ln.rstrip("\n") for ln in section_lines[open_idx + 1 : last_fence_idx]]


def main():
    if len(sys.argv) != 3:
        print("Usage: {} <source-file> <agent-name>".format(sys.argv[0]), file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    agent = sys.argv[2]
    if not src.is_file():
        print("Source file not found: {}".format(src), file=sys.stderr)
        return 2
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = find_section(lines, agent)
    if start < 0:
        print("Agent '{}' not found in {}".format(agent, src), file=sys.stderr)
        return 1
    body = extract_body(lines[start:end])
    if not body:
        print("No body extracted for '{}' - missing ```markdown fence?".format(agent), file=sys.stderr)
        return 1
    sys.stdout.write("\n".join(body) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

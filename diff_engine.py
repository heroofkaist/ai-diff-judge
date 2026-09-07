import difflib
import re
import subprocess
from pathlib import Path


HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@"
)


def _newline_only_change_end(lines: list[str], i: int) -> int | None:
    """Detect a '-content'/'+content' pair that differs only by a trailing
    newline (git shows a '\\ No newline at end of file' marker around it).

    Returns the index right after the matched block, or None if the line
    at `i` isn't the start of such a pair.
    """
    removed_content = lines[i][1:]
    j = i + 1

    if j < len(lines) and lines[j].startswith("\\"):
        j += 1

    if j < len(lines) and lines[j].startswith("+") and lines[j][1:] == removed_content:
        end = j + 1

        if end < len(lines) and lines[end].startswith("\\"):
            end += 1

        return end

    return None


def parse_diff(diff: str) -> dict:
    """Parse unified diff and return changed lines with coordinates."""
    added_lines = []
    removed_lines = []

    old_line_number = None
    new_line_number = None

    lines = diff.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        match = HUNK_RE.match(line)

        if match:
            old_line_number = int(match.group(1))
            new_line_number = int(match.group(2))
            i += 1
            continue

        if line.startswith("+++ ") or line.startswith("--- "):
            i += 1
            continue

        if old_line_number is None or new_line_number is None:
            i += 1
            continue

        if line.startswith("-"):
            end = _newline_only_change_end(lines, i)

            if end is not None:
                old_line_number += 1
                new_line_number += 1
                i = end
                continue

            removed_lines.append(
                {
                    "line": old_line_number,
                    "content": line[1:],
                }
            )
            old_line_number += 1
            i += 1
            continue

        if line.startswith("+"):
            added_lines.append(
                {
                    "line": new_line_number,
                    "content": line[1:],
                }
            )
            new_line_number += 1
            i += 1
            continue

        if line.startswith(" "):
            old_line_number += 1
            new_line_number += 1

        i += 1

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }


MAX_DIFF_CONTEXT_CHARS = 200_000


def build_diff_context(file_sources: dict[str, str]) -> str:
    """Format every touched file's full new-version source into one block.

    Passed to the LLM judge alongside an isolated function so it can check
    whether a symbol the function calls (a helper added elsewhere in the
    same diff) actually exists, instead of judging the function as a fully
    self-contained snippet with no view of the rest of the change.
    """
    blocks = [
        f"# File: {path}\n{source}"
        for path, source in file_sources.items()
    ]

    context = "\n\n".join(blocks)

    if len(context) > MAX_DIFF_CONTEXT_CHARS:
        context = (
            context[:MAX_DIFF_CONTEXT_CHARS]
            + "\n\n... (truncated, diff too large to fit in full context)"
        )

    return context


def diff_from_contents(old_content: str, new_content: str) -> str:
    """Build a unified diff from two in-memory file contents.

    Needed for renamed files: their path differs between old and new
    version, so a plain `git diff <ref1> <ref2> -- path` cannot compare
    them directly.
    """
    diff_lines = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        lineterm="",
    )
    return "\n".join(diff_lines)


def get_git_diff(
    old_ref: str,
    new_ref: str,
    file_path: str,
    repo_path: str | Path = ".",
) -> str:
    """Return unified diff for one file in a specific repository."""
    result = subprocess.run(
        [
            "git",
            "diff",
            old_ref,
            new_ref,
            "--",
            file_path,
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def get_git_diff_name_status(
    old_ref: str,
    new_ref: str,
    repo_path: str | Path = ".",
) -> list[tuple[str, str, str]]:
    """Return changed files as (status, old_path, new_path).

    For non-renamed files, old_path and new_path are identical.
    """
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            old_ref,
            new_ref,
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )

    changes = []

    for line in result.stdout.splitlines():
        parts = line.split("\t")

        if not parts or not parts[0]:
            continue

        status = parts[0]

        if status.startswith("R") and len(parts) == 3:
            changes.append((status, parts[1], parts[2]))
        elif len(parts) >= 2:
            changes.append((status, parts[1], parts[1]))

    return changes


def get_file_at_ref(
    ref: str,
    file_path: str,
    repo_path: str | Path = ".",
) -> str:
    """Return file contents at a specific git ref."""
    result = subprocess.run(
        [
            "git",
            "show",
            f"{ref}:{file_path}",
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise FileNotFoundError(
            f"File '{file_path}' does not exist at ref '{ref}'."
        )

    return result.stdout


def find_changed_functions(
    old_source: str,
    new_source: str,
    diff: str,
) -> list[dict]:
    """Find new-version functions touched by a diff."""
    from chunker import extract_functions

    parsed = parse_diff(diff)

    changed_new_lines = {
        item["line"]
        for item in parsed["added_lines"]
    }

    changed_old_lines = {
        item["line"]
        for item in parsed["removed_lines"]
    }

    old_functions = extract_functions(old_source)
    new_functions = extract_functions(new_source)

    old_by_name = {
        function["qualified_name"]: function
        for function in old_functions
    }

    changed_functions = []

    for new_function in new_functions:
        new_start = new_function["start_line"]
        new_end = new_function["end_line"]

        touched_new_lines = sorted(
            line
            for line in changed_new_lines
            if new_start <= line <= new_end
        )

        if not touched_new_lines:
            continue

        old_function = old_by_name.get(
            new_function["qualified_name"]
        )

        touched_old_lines = []

        if old_function is not None:
            old_start = old_function["start_line"]
            old_end = old_function["end_line"]

            touched_old_lines = sorted(
                line
                for line in changed_old_lines
                if old_start <= line <= old_end
            )

        changed_functions.append(
            {
                "name": new_function["name"],
                "old": old_function,
                "new": new_function,
                "changed_new_lines": touched_new_lines,
                "changed_old_lines": touched_old_lines,
            }
        )

    return changed_functions
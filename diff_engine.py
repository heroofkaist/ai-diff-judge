import re
import subprocess
from pathlib import Path


HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@"
)


def parse_diff(diff: str) -> dict:
    """Parse unified diff and return changed lines with coordinates."""
    added_lines = []
    removed_lines = []

    old_line_number = None
    new_line_number = None

    for line in diff.splitlines():
        match = HUNK_RE.match(line)

        if match:
            old_line_number = int(match.group(1))
            new_line_number = int(match.group(2))
            continue

        if line.startswith("+++ ") or line.startswith("--- "):
            continue

        if old_line_number is None or new_line_number is None:
            continue

        if line.startswith("+"):
            added_lines.append(
                {
                    "line": new_line_number,
                    "content": line[1:],
                }
            )
            new_line_number += 1

        elif line.startswith("-"):
            removed_lines.append(
                {
                    "line": old_line_number,
                    "content": line[1:],
                }
            )
            old_line_number += 1

        elif line.startswith(" "):
            old_line_number += 1
            new_line_number += 1

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }


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
) -> list[tuple[str, str]]:
    """Return changed files as (status, path)."""
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

        if len(parts) >= 2:
            changes.append(
                (parts[0], parts[-1])
            )

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
        function["name"]: function
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
            new_function["name"]
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
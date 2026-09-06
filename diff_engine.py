import re


HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@"
)


def parse_diff(diff: str) -> dict:
    """Извлекает добавленные и удалённые строки с номерами строк."""
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

        # Заголовки файлов unified diff
        if line.startswith("+++") or line.startswith("---"):
            continue

        # До первого hunk полезных строк нет
        if old_line_number is None or new_line_number is None:
            continue

        if line.startswith("+"):
            added_lines.append({
                "line": new_line_number,
                "content": line[1:],
            })
            new_line_number += 1

        elif line.startswith("-"):
            removed_lines.append({
                "line": old_line_number,
                "content": line[1:],
            })
            old_line_number += 1

        elif line.startswith(" "):
            old_line_number += 1
            new_line_number += 1

        # "\ No newline at end of file" намеренно игнорируем

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }
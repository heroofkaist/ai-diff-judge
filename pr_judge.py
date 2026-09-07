import os
import sys

from dotenv import load_dotenv
from github import Github, Auth

from chunker import extract_functions
from diff_engine import build_diff_context, find_changed_functions
from judge import score_code


def get_file_source(repo, filename: str, ref: str) -> str:
    """Download a file from GitHub at a specific ref."""
    file_data = repo.get_contents(filename, ref=ref)
    return file_data.decoded_content.decode("utf-8")


def analyze_pr(repo_name: str, pr_number: int):
    load_dotenv()

    gh_token = os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        print("Ошибка: GITHUB_TOKEN не найден в .env")
        sys.exit(1)

    auth = Auth.Token(gh_token)
    github = Github(auth=auth)

    print(
        f"Подключаемся к {repo_name}, "
        f"Pull Request #{pr_number}..."
    )

    repo = github.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    final_review = (
        "## 🤖 AI Diff Judge\n\n"
        f"Comparing `{pr.base.ref}` → `{pr.head.ref}`\n\n"
    )

    total_delta = 0.0
    all_bugs = []

    analyzed_functions = 0
    changed_python_files = 0

    file_sources = {}
    pending_files = []

    for file in pr.get_files():
        if not file.filename.endswith(".py"):
            continue

        patch = getattr(file, "patch", None)

        if not patch:
            continue

        changed_python_files += 1

        try:
            old_source = get_file_source(
                repo,
                file.filename,
                pr.base.sha,
            )
            new_source = get_file_source(
                repo,
                file.filename,
                pr.head.sha,
            )
        except Exception as exc:
            print(
                f"Не удалось получить `{file.filename}`: {exc}"
            )
            continue

        file_sources[file.filename] = new_source

        changed_functions = find_changed_functions(
            old_source,
            new_source,
            patch,
        )

        if not changed_functions:
            print(
                f"[{file.filename}] "
                "изменения есть, но изменённые функции не найдены."
            )
            continue

        pending_files.append((file.filename, changed_functions))

    diff_context = build_diff_context(file_sources)

    for filename, changed_functions in pending_files:
        print(f"\n[Файл: {filename}]")

        for item in changed_functions:
            name = item["name"]
            old_function = item["old"]
            new_function = item["new"]

            analyzed_functions += 1

            changed_lines = ", ".join(
                str(line)
                for line in item["changed_new_lines"]
            )

            final_review += (
                f"### 🔍 `{filename}::{name}`\n\n"
                f"Changed lines: `{changed_lines}`\n\n"
            )

            print(
                f"  ↳ {name} "
                f"(new lines: {changed_lines})"
            )

            if old_function is None:
                final_review += (
                    "🆕 **New function**\n\n"
                    "This function did not exist in the base version.\n\n"
                    "---\n\n"
                )
                continue

            verdict = score_code(
                name,
                old_function["code"],
                new_function["code"],
                diff_context=diff_context,
            )

            total_delta += verdict.get("weighted_delta", 0)
            all_bugs.extend(verdict.get("bugs_found", []))

            criteria_rows = "\n".join(
                f"| {criterion.capitalize()} | "
                f"{verdict.get(criterion, {}).get('old', '?')} | "
                f"{verdict.get(criterion, {}).get('new', '?')} | "
                f"{verdict.get(criterion, {}).get('reason', '')} |"
                for criterion in ("correctness", "security", "performance", "readability")
            )

            final_review += (
                f"**Winner:** `{verdict.get('winner', 'tie')}` "
                f"(confidence: {verdict.get('confidence', 0.0):.2f})\n\n"
                f"| Criterion | Old | New | Notes |\n"
                f"|---|---|---|---|\n"
                f"{criteria_rows}\n\n"
                "---\n\n"
            )

    if changed_python_files == 0:
        print("Изменённых Python-файлов в PR нет.")
        return

    if analyzed_functions == 0:
        print(
            "Python-файлы изменены, "
            "но изменённых функций для AI review не найдено."
        )
        return

    final_review += (
        "## 📊 Summary\n\n"
        f"Python files changed: **{changed_python_files}**\n\n"
        f"Functions analyzed: **{analyzed_functions}**\n\n"
        f"Total weighted delta: **{total_delta:+.1f}**\n\n"
    )

    if total_delta > 0:
        final_review += "**Overall: NEW is better.** ✅\n"
    elif total_delta < 0:
        final_review += "**Overall: OLD is better.** ⚠️\n"
    else:
        final_review += "**Overall: No clear winner.**\n"

    if all_bugs:
        final_review += "\n## 🐛 Bugs found\n\n"
        for bug in all_bugs:
            final_review += f"- {bug}\n"

    print("\nОтправляем комментарий в Pull Request...")
    pr.create_issue_comment(final_review)
    print("✅ Готово!")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Использование: "
            "python3 pr_judge.py "
            "<владелец/репозиторий> <номер_PR>"
        )
        sys.exit(1)

    analyze_pr(
        sys.argv[1],
        int(sys.argv[2]),
    )
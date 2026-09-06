import os
import sys

from dotenv import load_dotenv
from github import Github, Auth

from chunker import extract_functions
from diff_engine import find_changed_functions
from judge import compare_code


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

    votes = {
        "old": 0,
        "new": 0,
        "tie": 0,
    }

    analyzed_functions = 0
    changed_python_files = 0

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

        print(f"\n[Файл: {file.filename}]")

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
                f"### 🔍 `{file.filename}::{name}`\n\n"
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

            verdict = compare_code(
                name,
                old_function["code"],
                new_function["code"],
            )

            winner = verdict.get("winner", "tie")

            if winner not in votes:
                winner = "tie"

            votes[winner] += 1

            final_review += (
                f"**Winner:** `{winner}`\n\n"
                f"{verdict.get('reason', '')}\n\n"
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
        f"- Old: **{votes['old']}**\n"
        f"- New: **{votes['new']}**\n"
        f"- Tie: **{votes['tie']}**\n\n"
    )

    if votes["new"] > votes["old"]:
        final_review += "**Overall: NEW is better.** ✅\n"
    elif votes["old"] > votes["new"]:
        final_review += "**Overall: OLD is better.** ⚠️\n"
    else:
        final_review += "**Overall: No clear winner.**\n"

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
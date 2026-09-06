import os
import sys
from dotenv import load_dotenv
from github import Github, Auth
from chunker import extract_functions
from judge import compare_code

load_dotenv()

gh_token = os.environ.get("GITHUB_TOKEN")
if not gh_token:
    print("Ошибка: GITHUB_TOKEN не найден в .env")
    sys.exit(1)

auth = Auth.Token(gh_token)
g = Github(auth=auth)


def get_functions_dict(repo, filename: str, ref: str) -> dict:
    """Скачивает файл на указанном ref и возвращает {имя_функции: код}."""
    try:
        file_data = repo.get_contents(filename, ref=ref)
        source_code = file_data.decoded_content.decode("utf-8")
    except Exception:
        return {}  # файла может не быть на этом ref (например, новый файл в PR)

    functions = extract_functions(source_code)
    return {fn["name"]: fn["code"] for fn in functions}


def analyze_pr(repo_name: str, pr_number: int):
    print(f"Подключаемся к {repo_name}, Pull Request #{pr_number}...")
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    files = pr.get_files()
    final_review = "## 🤖 Ревью от AI Judge (старая vs новая версия)\n\n"
    found_functions = False
    votes = {"old": 0, "new": 0, "tie": 0}

    for file in files:
        if not file.filename.endswith(".py"):
            continue

        print(f"\n[Файл: {file.filename}] Скачиваем старую и новую версии...")

        old_funcs = get_functions_dict(repo, file.filename, pr.base.sha)
        new_funcs = get_functions_dict(repo, file.filename, pr.head.sha)

        if not new_funcs:
            continue

        for name, new_code in new_funcs.items():
            old_code = old_funcs.get(name)

            if old_code is None:
                final_review += f"### 🆕 Новая функция: `{name}` (Файл: `{file.filename}`)\n"
                final_review += "Функция появилась впервые в этом PR.\n\n---\n"
                found_functions = True
                continue

            if old_code.strip() == new_code.strip():
                continue  # функция не менялась

            print(f"Сравниваем функцию: {name}...")
            verdict = compare_code(name, old_code, new_code)

            final_review += f"### 🔍 Функция: `{name}` (Файл: `{file.filename}`)\n"
            final_review += f"**Победитель:** `{verdict['winner']}`\n\n"
            final_review += f"{verdict['reason']}\n\n---\n"

            votes[verdict["winner"]] = votes.get(verdict["winner"], 0) + 1
            found_functions = True

    if found_functions:
        total = sum(votes.values())
        if total > 0:
            final_review += (
                f"\n## 📊 Итоговый вердикт\n"
                f"Old: {votes['old']} | New: {votes['new']} | Tie: {votes['tie']}\n\n"
            )
            if votes["new"] > votes["old"]:
                final_review += "**Новая версия в целом лучше.** ✅\n"
            elif votes["old"] > votes["new"]:
                final_review += "**Старая версия была лучше — стоит пересмотреть изменения.** ⚠️\n"
            else:
                final_review += "**Ничья — явного улучшения не видно.**\n"

        print("\nОтправляем комментарий в Pull Request...")
        pr.create_issue_comment(final_review)
        print("✅ Готово!")
    else:
        print("Не найдено изменённых Python-функций для ревью.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python3 pr_judge.py <владелец/репозиторий> <номер_PR>")
        sys.exit(1)

    analyze_pr(sys.argv[1], int(sys.argv[2]))
import os
import sys
from dotenv import load_dotenv
from github import Github, Auth
from chunker import extract_functions
from judge import evaluate_code

load_dotenv()

gh_token = os.environ.get("GITHUB_TOKEN")
if not gh_token:
    print("Ошибка: GITHUB_TOKEN не найден в .env")
    sys.exit(1)

auth = Auth.Token(gh_token)
g = Github(auth=auth)

def analyze_pr(repo_name: str, pr_number: int):
    print(f"Подключаемся к {repo_name}, Pull Request #{pr_number}...")
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    files = pr.get_files()
    
    # Сюда мы будем собирать весь текст ревью
    final_review = "## 🤖 Ревью от AI Judge\n\n"
    found_functions = False
    
    for file in files:
        if not file.filename.endswith(".py"):
            continue
            
        print(f"\n[Файл: {file.filename}] Скачиваем обновления...")
        
        try:
            file_data = repo.get_contents(file.filename, ref=pr.head.sha)
            source_code = file_data.decoded_content.decode("utf-8")
        except Exception as e:
            print(f"Не удалось прочитать {file.filename}: {e}")
            continue

        functions = extract_functions(source_code)
        if not functions:
            continue

        for fn in functions:
            print(f"Анализируем: {fn['name']}...")
            verdict = evaluate_code(fn["name"], fn["code"])
            
            # Добавляем вердикт по функции в общий текст комментария
            final_review += f"### 🔍 Функция: `{fn['name']}` (Файл: `{file.filename}`)\n"
            final_review += f"{verdict}\n\n---\n"
            found_functions = True

    # Если нашли хоть одну функцию, отправляем комментарий
    if found_functions:
        print("\nОтправляем комментарий в Pull Request...")
        pr.create_issue_comment(final_review)
        print("✅ Готово! Проверь страницу PR на GitHub.")
    else:
        print("Не найдено Python-функций для ревью.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python3 pr_judge.py <владелец/репозиторий> <номер_PR>")
        sys.exit(1)
    
    target_repo = sys.argv[1]
    target_pr = int(sys.argv[2])
    
    analyze_pr(target_repo, target_pr)
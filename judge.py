import os
import sys
import json
from dotenv import load_dotenv
from openai import OpenAI
from chunker import extract_functions

load_dotenv()
client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

def evaluate_code(function_name: str, function_code: str) -> str:
    prompt = f"""
    Ты строгий, но справедливый проверяющий кода (Code Judge).
    Проанализируй эту функцию на Python и коротко ответь на 2 пункта:
    1. Что делает эта функция?
    2. Есть ли в ней потенциальные ошибки или что можно улучшить?
    
    Имя функции: '{function_name}'
    Код:
    ```python
    {function_code}
    ```
    """
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 judge.py <имя_файла.py>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Ошибка: Файл '{file_path}' не найден.")
        sys.exit(1)
        
    print(f"Анализируем файл: {file_path}...")
    functions = extract_functions(source_code)
    
    if not functions:
        print("Функции в файле не найдены.")
        sys.exit(0)
        
    for fn in functions:
        print(f"\n" + "="*40)
        print(f"=== Ревью функции: {fn['name']} ===")
        print("="*40)
        print(evaluate_code(fn["name"], fn["code"]))

def compare_code(function_name: str, old_code: str, new_code: str) -> dict:
    """Сравнивает старую и новую версию функции, возвращает {'winner': ..., 'reason': ...}."""
    prompt = f"""
Ты строгий, но справедливый проверяющий кода (Code Judge).
Сравни СТАРУЮ и НОВУЮ версии одной и той же функции по критериям:
читаемость, риск ошибок, эффективность.

Ответь СТРОГО в формате JSON, без markdown и лишнего текста:
{{"winner": "old" | "new" | "tie", "reason": "краткое объяснение на русском"}}

Имя функции: '{function_name}'

СТАРАЯ версия:
```python
{old_code}
```

НОВАЯ версия:
```python
{new_code}
```
"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"winner": "tie", "reason": f"Не удалось распарсить ответ модели: {raw[:200]}"}

    if result.get("winner") not in ("old", "new", "tie"):
        result["winner"] = "tie"

    return result
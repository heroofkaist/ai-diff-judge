import os
import sys
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
    # Проверяем, передал ли пользователь имя файла в терминале
    if len(sys.argv) < 2:
        print("Использование: python3 judge.py <имя_файла.py>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    # Пытаемся прочитать файл
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
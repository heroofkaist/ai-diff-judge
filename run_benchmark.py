import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

def check_for_bugs(function_code: str) -> bool:
    prompt = f"""
    Does this Python function have potential bugs, vulnerabilities, or missing critical logic (like division by zero)?
    Answer ONLY with 'YES' or 'NO'. No explanations.

    Code:
    ```python
    {function_code}
    ```
    """
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0, # 0.0 делает ответы максимально стабильными
    )
    answer = response.choices[0].message.content.strip().upper()
    return "YES" in answer

if __name__ == "__main__":
    try:
        with open("benchmark/dataset.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Ошибка: Не найден файл benchmark/dataset.json")
        exit(1)

    correct = 0
    total = len(dataset)

    print("Запуск бенчмарка...\n" + "-"*30)

    for item in dataset:
        print(f"Анализ {item['name']}...")
        ai_says_bug = check_for_bugs(item["code"])
        
        if ai_says_bug == item["has_bug"]:
            print("✅ Совпадает")
            correct += 1
        else:
            print(f"❌ Расхождение (Истина: {item['has_bug']}, ИИ: {ai_says_bug})")

    print("-" * 30)
    print(f"Точность (Accuracy): {correct}/{total} ({(correct/total)*100:.1f}%)")
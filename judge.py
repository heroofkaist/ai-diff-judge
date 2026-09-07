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
    You are a strict but fair code reviewer.
    Analyze this Python function and briefly answer 2 questions:
    1. What does this function do?
    2. Are there any potential bugs or improvements?
    Function name: '{function_name}'
    Code:
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


def compare_code(function_name: str, old_code: str, new_code: str) -> dict:
    prompt = f"""
    You are a strict but fair code reviewer.
    Compare the OLD and NEW versions of the same function on:
    readability, risk of bugs, efficiency.

    If the difference between versions is negligible or purely stylistic
    (e.g. an added comment, a trivial rename, string formatting with no
    real functional or performance impact), respond with "tie" instead
    of picking a winner.

    Respond "tie" only when there is truly no difference in behavior, 
    readability, or efficiency (e.g. variable renaming, added comments,
    whitespace changes). If one version is measurably more efficient 
    or more idiomatic (even slightly), pick that version as the winner.

    Respond STRICTLY as JSON, no markdown, no extra text:
    {{"winner": "old" | "new" | "tie", "reason": "brief explanation"}}

    Function name: '{function_name}'

    OLD version:
```python
{old_code}
```

    NEW version:
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
        result = {"winner": "tie", "reason": f"Could not parse model response: {raw[:200]}"}

    if result.get("winner") not in ("old", "new", "tie"):
        result["winner"] = "tie"

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 judge.py <file_name.py>")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: file '{file_path}' not found.")
        sys.exit(1)

    print(f"Analyzing file: {file_path}...")
    functions = extract_functions(source_code)

    if not functions:
        print("No functions found in file.")
        sys.exit(0)

    for fn in functions:
        print("\n" + "=" * 40)
        print(f"=== Review: {fn['name']} ===")
        print("=" * 40)
        print(evaluate_code(fn["name"], fn["code"]))
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

CRITERIA_WEIGHTS = {
    "correctness": 5,
    "security": 5,
    "performance": 3,
    "readability": 1,
}


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


def score_code(function_name: str, old_code: str, new_code: str) -> dict:
    """Compares two versions of a function with per-criterion scores and confidence."""
    prompt = f"""
    You are a strict but fair code reviewer.
    Compare the OLD and NEW versions of the same function.

    Score each version from 1 to 10 on these criteria:
    correctness (does it work as intended, any bugs?)
    security (any vulnerabilities or unsafe patterns?)
    performance (efficiency, time/space complexity)
    readability (clarity, naming, structure)

    Respond STRICTLY as JSON, no markdown, no extra text:
    {{
      "confidence": 0.0 to 1.0,
      "correctness": {{"old": 1-10, "new": 1-10, "reason": "brief"}},
      "security": {{"old": 1-10, "new": 1-10, "reason": "brief"}},
      "performance": {{"old": 1-10, "new": 1-10, "reason": "brief"}},
      "readability": {{"old": 1-10, "new": 1-10, "reason": "brief"}},
      "bugs_found": ["list of specific bugs, empty if none"]
    }}

    If the difference between versions is negligible or purely stylistic,
    give both versions nearly identical scores on all criteria.

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
        return _empty_score(f"Could not parse model response: {raw[:200]}")

    for criterion in CRITERIA_WEIGHTS:
        if criterion not in result or "old" not in result[criterion] or "new" not in result[criterion]:
            return _empty_score(f"Missing criterion '{criterion}' in model response")

    weighted_delta = sum(
        (result[criterion]["new"] - result[criterion]["old"]) * weight
        for criterion, weight in CRITERIA_WEIGHTS.items()
    )

    if weighted_delta > 0:
        winner = "new"
    elif weighted_delta < 0:
        winner = "old"
    else:
        winner = "tie"

    result["winner"] = winner
    result["weighted_delta"] = weighted_delta
    result.setdefault("bugs_found", [])
    result.setdefault("confidence", 0.5)

    return result


def _empty_score(error_message: str) -> dict:
    empty_criterion = {"old": 5, "new": 5, "reason": error_message}
    return {
        "winner": "tie",
        "confidence": 0.0,
        "weighted_delta": 0,
        "bugs_found": [],
        "correctness": empty_criterion,
        "security": empty_criterion,
        "performance": empty_criterion,
        "readability": empty_criterion,
    }


def validate_score(score: dict) -> bool:
    """Validate that a score dict has all required fields with correct types."""
    required_fields = ["winner", "confidence", "weighted_delta", "bugs_found"]
    required_criteria = ["correctness", "security", "performance", "readability"]

    for field in required_fields:
        if field not in score:
            return False

    for criterion in required_criteria:
        if criterion not in score or not isinstance(score[criterion], dict):
            return False
        if "old" not in score[criterion] or "new" not in score[criterion]:
            return False

    if not isinstance(score.get("winner"), str) or score["winner"] not in ("old", "new", "tie"):
        return False

    if not isinstance(score.get("confidence"), (int, float)) or not (0 <= score["confidence"] <= 1):
        return False

    return True


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
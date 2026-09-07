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

# Groq's free/on-demand tier enforces an 8000 tokens-per-minute cap per
# request for this model — much smaller than the model's actual context
# window. This budget is enforced per call, not just as a sanity cap.
GROQ_TPM_LIMIT = 8000
RESPONSE_TOKEN_RESERVE = 800
CHARS_PER_TOKEN_ESTIMATE = 4
PROMPT_BOILERPLATE_CHARS = 1500


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


def _truncate_context_to_budget(diff_context: str, old_code: str, new_code: str, function_name: str) -> str:
    """Shrink diff_context so the whole request fits Groq's per-call token cap.

    Uses a rough chars-per-token estimate since we don't tokenize locally;
    a real 413 is still handled as a fallback by the caller if this
    estimate runs a little hot.
    """
    if not diff_context:
        return diff_context

    fixed_chars = len(old_code) + len(new_code) + len(function_name) + PROMPT_BOILERPLATE_CHARS
    budget_tokens = GROQ_TPM_LIMIT - RESPONSE_TOKEN_RESERVE
    budget_chars = budget_tokens * CHARS_PER_TOKEN_ESTIMATE - fixed_chars

    if budget_chars <= 0:
        return ""

    if len(diff_context) <= budget_chars:
        return diff_context

    return diff_context[:budget_chars] + "\n\n... (truncated to fit the model's token budget)"


def _is_request_too_large(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status_code in (413, 429) or "too large" in message or "rate_limit_exceeded" in message


def _request_score(function_name: str, old_code: str, new_code: str, diff_context: str):
    context_section = ""

    if diff_context:
        context_section = f"""
    For reference only, here is the full content of every file touched by
    this same diff. Use it ONLY to check whether a name the function calls
    (a function, class, or import added or changed elsewhere in this diff)
    actually exists somewhere in this change. Do not review or score this
    reference material itself — only the OLD/NEW function below.

    DIFF CONTEXT:
```python
{diff_context}
```
"""

    prompt = f"""
    You are a strict but fair code reviewer.
    Compare the OLD and NEW versions of the same function.
    {context_section}
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
    return client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )


def score_code(function_name: str, old_code: str, new_code: str, diff_context: str = "") -> dict:
    """Compares two versions of a function with per-criterion scores and confidence.

    diff_context, when provided, is the full source of every file touched by
    the surrounding diff (see diff_engine.build_diff_context). It lets the
    model verify that a symbol the function calls (a helper added elsewhere
    in the same change) actually exists, instead of judging the function as
    a fully isolated snippet with no view of the rest of the diff.
    """
    diff_context = _truncate_context_to_budget(diff_context, old_code, new_code, function_name)

    try:
        response = _request_score(function_name, old_code, new_code, diff_context)
    except Exception as exc:
        if diff_context and _is_request_too_large(exc):
            try:
                response = _request_score(function_name, old_code, new_code, "")
            except Exception as retry_exc:
                return _empty_score(f"Groq API error even without diff context: {retry_exc}")
        else:
            return _empty_score(f"Groq API error: {exc}")

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
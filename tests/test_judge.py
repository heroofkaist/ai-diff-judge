import json

from judge import compare_code, score_code, validate_score


class FakeScoreResponse:
    def __init__(self, content):
        self._content = content

    class Choice:
        def __init__(self, content):
            self.message = type("Message", (), {"content": content})()

    @property
    def choices(self):
        return [FakeScoreResponse.Choice(self._content)]


_VALID_SCORE_JSON = json.dumps(
    {
        "confidence": 0.9,
        "correctness": {"old": 7, "new": 9, "reason": "fixed a bug"},
        "security": {"old": 8, "new": 8, "reason": "no change"},
        "performance": {"old": 6, "new": 6, "reason": "no change"},
        "readability": {"old": 7, "new": 8, "reason": "clearer"},
        "bugs_found": [],
    }
)


class FakeResponse:
    class Choice:
        class Message:
            content = '{"winner": "new", "reason": "Новая версия читаемее"}'

        message = Message()

    choices = [Choice()]


def test_compare_code_parses_json(monkeypatch):
    def fake_create(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(
        "judge.client.chat.completions.create",
        fake_create,
    )

    result = compare_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return sum((a, b))",
    )

    assert result["winner"] == "new"
    assert result["reason"] == "Новая версия читаемее"


def test_compare_code_invalid_json_returns_tie(monkeypatch):
    class BadResponse:
        class Choice:
            class Message:
                content = "это вообще не JSON"

            message = Message()

        choices = [Choice()]

    def fake_create(*args, **kwargs):
        return BadResponse()

    monkeypatch.setattr(
        "judge.client.chat.completions.create",
        fake_create,
    )

    result = compare_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a - b",
    )

    assert result["winner"] == "tie"
    assert "Could not parse model response" in result["reason"]

def test_compare_code_invalid_winner_returns_tie(monkeypatch):
    class BadWinnerResponse:
        class Choice:
            class Message:
                content = '{"winner": "banana", "reason": "Странный ответ"}'

            message = Message()

        choices = [Choice()]

    def fake_create(*args, **kwargs):
        return BadWinnerResponse()

    monkeypatch.setattr(
        "judge.client.chat.completions.create",
        fake_create,
    )

    result = compare_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a - b",
    )

    assert result["winner"] == "tie"
    assert result["reason"] == "Странный ответ"


def test_validate_score_valid():
    valid_score = {
        "winner": "new",
        "confidence": 0.95,
        "weighted_delta": 5.0,
        "bugs_found": [],
        "correctness": {"old": 7, "new": 9, "reason": "Fixed bug"},
        "security": {"old": 8, "new": 8, "reason": "No change"},
        "performance": {"old": 6, "new": 7, "reason": "Improved"},
        "readability": {"old": 7, "new": 8, "reason": "Better names"},
    }
    assert validate_score(valid_score) is True


def test_validate_score_missing_winner():
    invalid_score = {
        "confidence": 0.95,
        "weighted_delta": 5.0,
        "bugs_found": [],
        "correctness": {"old": 7, "new": 9, "reason": "test"},
        "security": {"old": 8, "new": 8, "reason": "test"},
        "performance": {"old": 6, "new": 7, "reason": "test"},
        "readability": {"old": 7, "new": 8, "reason": "test"},
    }
    assert validate_score(invalid_score) is False


def test_validate_score_invalid_winner():
    invalid_score = {
        "winner": "maybe",
        "confidence": 0.95,
        "weighted_delta": 5.0,
        "bugs_found": [],
        "correctness": {"old": 7, "new": 9, "reason": "test"},
        "security": {"old": 8, "new": 8, "reason": "test"},
        "performance": {"old": 6, "new": 7, "reason": "test"},
        "readability": {"old": 7, "new": 8, "reason": "test"},
    }
    assert validate_score(invalid_score) is False


def test_score_code_includes_diff_context_in_prompt(monkeypatch):
    captured = {}

    def fake_create(*args, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return FakeScoreResponse(_VALID_SCORE_JSON)

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    score_code(
        "process_item",
        "def process_item(x):\n    return old_helper(x)",
        "def process_item(x):\n    return new_helper(x)",
        diff_context="# File: helpers.py\ndef new_helper(x):\n    return x * 2",
    )

    assert "new_helper" in captured["prompt"]
    assert "DIFF CONTEXT" in captured["prompt"]


def test_score_code_omits_context_section_when_not_given(monkeypatch):
    captured = {}

    def fake_create(*args, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return FakeScoreResponse(_VALID_SCORE_JSON)

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    score_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a + b  # noop comment",
    )

    assert "DIFF CONTEXT" not in captured["prompt"]


def test_score_code_truncates_huge_diff_context_to_fit_token_budget(monkeypatch):
    from diff_engine import build_diff_context

    captured = {}

    def fake_create(*args, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        captured["prompt"] = prompt
        return FakeScoreResponse(_VALID_SCORE_JSON)

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    # Several complete files, each individually small but far too many
    # combined to fit any single request's token budget.
    huge_context = build_diff_context(
        {f"file_{i}.py": f"def fn_{i}():\n    return {i}\n" * 200 for i in range(50)}
    )

    score_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a + b",
        diff_context=huge_context,
    )

    # The full blob must never reach the API call.
    assert len(captured["prompt"]) < len(huge_context)
    assert "omitted" in captured["prompt"]
    # Whatever files did make it in must be complete, never cut mid-function.
    assert "# File: file_0.py" in captured["prompt"]
    assert captured["prompt"].count("def fn_0():") == 200


def test_score_code_retries_without_context_on_request_too_large(monkeypatch):
    calls = []

    class TooLargeError(Exception):
        status_code = 413

    def fake_create(*args, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        calls.append(prompt)

        if "DIFF CONTEXT" in prompt:
            raise TooLargeError("Error code: 413 - Request too large for model, rate_limit_exceeded")

        return FakeScoreResponse(_VALID_SCORE_JSON)

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    result = score_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a + b + 0",
        diff_context="# File: helper.py\ndef helper():\n    pass",
    )

    assert len(calls) == 2
    assert "DIFF CONTEXT" in calls[0]
    assert "DIFF CONTEXT" not in calls[1]
    assert result["winner"] == "new"
    assert result["confidence"] == 0.9


def test_score_code_falls_back_to_empty_score_if_retry_also_fails(monkeypatch):
    class TooLargeError(Exception):
        status_code = 413

    def fake_create(*args, **kwargs):
        raise TooLargeError("Error code: 413 - Request too large, rate_limit_exceeded")

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    result = score_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a + b + 0",
        diff_context="# File: helper.py\ndef helper():\n    pass",
    )

    assert result["winner"] == "tie"
    assert result["confidence"] == 0.0
    assert "Groq API error" in result["correctness"]["reason"]


def test_score_code_retries_on_json_validation_error_not_just_size_errors(monkeypatch):
    """Regression test for a real CI failure: Groq's JSON-mode validator can
    reject a response outright (400 json_validate_failed) when a large
    diff_context confuses the model into producing invalid JSON. This must
    be retried without context too, not just size/rate-limit errors."""
    calls = []

    class JsonValidateFailedError(Exception):
        status_code = 400

    def fake_create(*args, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        calls.append(prompt)

        if "DIFF CONTEXT" in prompt:
            raise JsonValidateFailedError(
                "Error code: 400 - {'error': {'message': \"Failed to validate JSON.\", "
                "'code': 'json_validate_failed'}}"
            )

        return FakeScoreResponse(_VALID_SCORE_JSON)

    monkeypatch.setattr("judge.client.chat.completions.create", fake_create)

    result = score_code(
        "add",
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return a + b + 0",
        diff_context="# File: helper.py\ndef helper():\n    pass",
    )

    assert len(calls) == 2
    assert "DIFF CONTEXT" in calls[0]
    assert "DIFF CONTEXT" not in calls[1]
    assert result["winner"] == "new"


def test_validate_score_invalid_confidence():
    invalid_score = {
        "winner": "new",
        "confidence": 1.5,
        "weighted_delta": 5.0,
        "bugs_found": [],
        "correctness": {"old": 7, "new": 9, "reason": "test"},
        "security": {"old": 8, "new": 8, "reason": "test"},
        "performance": {"old": 6, "new": 7, "reason": "test"},
        "readability": {"old": 7, "new": 8, "reason": "test"},
    }
    assert validate_score(invalid_score) is False
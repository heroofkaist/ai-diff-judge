from judge import compare_code, validate_score


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
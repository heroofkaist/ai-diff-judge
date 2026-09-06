from judge import compare_code


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
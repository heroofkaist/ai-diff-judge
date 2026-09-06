import pytest

from chunker import extract_functions


def test_invalid_python_raises_syntax_error():
    source = """
def broken(
    return 123
"""

    with pytest.raises(SyntaxError):
        extract_functions(source)

def test_extract_functions():
    source = """
def add(a, b):
    return a + b


def greet(name):
    return f"Hello, {name}!"
"""

    functions = extract_functions(source)

    assert len(functions) == 2

    assert functions[0]["name"] == "add"
    assert "return a + b" in functions[0]["code"]

    assert functions[1]["name"] == "greet"
    assert 'return f"Hello, {name}!"' in functions[1]["code"]


def test_extract_async_function():
    source = """
async def fetch_data():
    return "data"
"""

    functions = extract_functions(source)

    assert len(functions) == 1
    assert functions[0]["name"] == "fetch_data"
    assert functions[0]["start_line"] == 2
    assert functions[0]["end_line"] == 3


def test_extract_function_line_numbers():
    source = """def first():
    return 1


def second():
    return 2
"""

    functions = extract_functions(source)

    assert functions[0]["start_line"] == 1
    assert functions[0]["end_line"] == 2

    assert functions[1]["start_line"] == 5
    assert functions[1]["end_line"] == 6


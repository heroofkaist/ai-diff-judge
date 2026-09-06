import ast


def extract_functions(source_code: str) -> list[dict]:
    """Разбирает Python-код и возвращает список функций с их названиями и содержимым."""
    tree = ast.parse(source_code)
    lines = source_code.splitlines(keepends=True)
    functions = []
    ##rewrwrewrwrw
    
    

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Определяем номера строк начала и конца функции
            start_line = node.lineno - 1
            end_line = node.end_lineno

            # Вырезаем исходный код функции
            func_code = "".join(lines[start_line:end_line])

            functions.append(
                {
                    "name": node.name,
                    "code": func_code,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                }
            )

    return functions


if __name__ == "__main__":
    # Тестовый пример для проверки работы чанкера
    sample_code = """
def add(a, b):
    return a + b

def greet(name: str):
    message = f"Hello, {name}!"
    print(message)
    return message
"""

    extracted = extract_functions(sample_code)
    for fn in extracted:
        print(f"=== Функция: {fn['name']} (строки {fn['start_line']}-{fn['end_line']}) ===")
        print(fn["code"].strip())
        print()
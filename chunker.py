import ast


def extract_functions(source_code: str) -> list[dict]:
    """Extract functions from Python source, including class methods."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"Skipping file due to syntax error: {e}")
        return []

    lines = source_code.splitlines(keepends=True)
    functions = []

    def visit(node, class_stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_stack + [child.name])

            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = ".".join(class_stack + [child.name])
                start_line = child.lineno - 1
                end_line = child.end_lineno
                func_code = "".join(lines[start_line:end_line])

                functions.append(
                    {
                        "name": child.name,
                        "qualified_name": qualified_name,
                        "code": func_code,
                        "start_line": child.lineno,
                        "end_line": child.end_lineno,
                    }
                )
                visit(child, class_stack)

            else:
                visit(child, class_stack)

    visit(tree, [])
    return functions


if __name__ == "__main__":
    sample_code = """
class Storage:
    def save(self, item):
        return True

class Cache:
    def save(self, item):
        return False

def add(a, b):
    return a + b
"""

##test.checking my project

    extracted = extract_functions(sample_code)
    for fn in extracted:
        print(f"=== {fn['qualified_name']} (lines {fn['start_line']}-{fn['end_line']}) ===")
        print(fn["code"].strip())
        print()
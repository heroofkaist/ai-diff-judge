import subprocess

from branch_judge import analyze_branch_pair


def run_git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def write_file(repo, name, content):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_analyze_branch_pair_detects_modified_function(tmp_path):
    run_git(tmp_path, "init")
    run_git(
        tmp_path,
        "config",
        "user.name",
        "Test User",
    )
    run_git(
        tmp_path,
        "config",
        "user.email",
        "test@example.com",
    )

    write_file(
        tmp_path,
        "app.py",
        """def calculate():
    return 10


def untouched():
    return 1
""",
    )

    run_git(tmp_path, "add", "app.py")
    run_git(
        tmp_path,
        "commit",
        "-m",
        "base",
    )

    run_git(
        tmp_path,
        "branch",
        "-M",
        "main",
    )

    run_git(
        tmp_path,
        "checkout",
        "-b",
        "feature",
    )

    write_file(
        tmp_path,
        "app.py",
        """def calculate():
    return 20


def untouched():
    return 1
""",
    )

    run_git(tmp_path, "add", "app.py")
    run_git(
        tmp_path,
        "commit",
        "-m",
        "change",
    )

    result = analyze_branch_pair(
        "main",
        "feature",
        repo_path=tmp_path,
    )

    assert result["base"] == "main"
    assert result["head"] == "feature"

    assert result["files"] == [
        {
            "status": "M",
            "path": "app.py",
            "changed_functions": 1,
        }
    ]

    assert result["functions"] == [
        {
            "path": "app.py",
            "name": "calculate",
            "type": "modified",
            "changed_new_lines": [2],
            "changed_old_lines": [2],
        }
    ]


def test_analyze_branch_pair_detects_new_python_file(tmp_path):
    run_git(tmp_path, "init")
    run_git(
        tmp_path,
        "config",
        "user.name",
        "Test User",
    )
    run_git(
        tmp_path,
        "config",
        "user.email",
        "test@example.com",
    )

    write_file(
        tmp_path,
        "main.py",
        """def main():
    return 1
""",
    )

    run_git(tmp_path, "add", "main.py")
    run_git(
        tmp_path,
        "commit",
        "-m",
        "base",
    )

    run_git(
        tmp_path,
        "branch",
        "-M",
        "main",
    )

    run_git(
        tmp_path,
        "checkout",
        "-b",
        "feature",
    )

    write_file(
        tmp_path,
        "new_module.py",
        """def hello():
    return "hello"
""",
    )

    run_git(
        tmp_path,
        "add",
        "new_module.py",
    )
    run_git(
        tmp_path,
        "commit",
        "-m",
        "add module",
    )

    result = analyze_branch_pair(
        "main",
        "feature",
        repo_path=tmp_path,
    )

    assert {
        "status": "A",
        "path": "new_module.py",
    } in result["files"]

    assert {
        "path": "new_module.py",
        "name": None,
        "type": "added_file",
        "changed_new_lines": [],
        "changed_old_lines": [],
    } in result["functions"]


def test_analyze_branch_pair_detects_deleted_python_file(tmp_path):
    run_git(tmp_path, "init")
    run_git(
        tmp_path,
        "config",
        "user.name",
        "Test User",
    )
    run_git(
        tmp_path,
        "config",
        "user.email",
        "test@example.com",
    )

    write_file(
        tmp_path,
        "old_module.py",
        """def old():
    return 1
""",
    )

    run_git(tmp_path, "add", "old_module.py")
    run_git(
        tmp_path,
        "commit",
        "-m",
        "base",
    )

    run_git(
        tmp_path,
        "branch",
        "-M",
        "main",
    )

    run_git(
        tmp_path,
        "checkout",
        "-b",
        "feature",
    )

    run_git(
        tmp_path,
        "rm",
        "old_module.py",
    )
    run_git(
        tmp_path,
        "commit",
        "-m",
        "delete module",
    )

    result = analyze_branch_pair(
        "main",
        "feature",
        repo_path=tmp_path,
    )

    assert {
        "status": "D",
        "path": "old_module.py",
    } in result["files"]

    assert {
        "path": "old_module.py",
        "name": None,
        "type": "deleted_file",
        "changed_new_lines": [],
        "changed_old_lines": [],
    } in result["functions"]
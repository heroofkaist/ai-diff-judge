import subprocess
import tempfile
from pathlib import Path
from diff_engine import (
    build_diff_context,
    find_changed_functions,
    get_git_diff,
    parse_diff,
)


def _init_repo(repo):
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def test_get_git_diff_returns_unified_diff():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)

        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

        file_path = repo / "sample.py"

        file_path.write_text("def foo():\n    return 1\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=repo, check=True, capture_output=True)

        file_path.write_text("def foo():\n    return 2\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "second"], cwd=repo, check=True, capture_output=True)

        diff = get_git_diff("HEAD~1", "HEAD", "sample.py", repo_path=repo)

        assert "@@" in diff
        assert "-    return 1" in diff
        assert "+    return 2" in diff


def test_parse_diff_ignores_trailing_newline_only_change():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_repo(repo)

        file_path = repo / "sample.py"

        file_path.write_text("def foo():\n    return 1")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=repo, check=True, capture_output=True)

        file_path.write_text("def foo():\n    return 1\n\n\ndef bar():\n    return 2\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "second"], cwd=repo, check=True, capture_output=True)

        diff = get_git_diff("HEAD~1", "HEAD", "sample.py", repo_path=repo)

        assert "No newline at end of file" in diff

        parsed = parse_diff(diff)

        assert not any(item["content"] == "    return 1" for item in parsed["added_lines"])
        assert not any(item["content"] == "    return 1" for item in parsed["removed_lines"])
        assert any(item["content"] == "def bar():" for item in parsed["added_lines"])


def test_build_diff_context_includes_every_file():
    context = build_diff_context(
        {
            "judge.py": "def score_code():\n    pass\n",
            "pr_judge.py": "def analyze_pr():\n    pass\n",
        }
    )

    assert "# File: judge.py" in context
    assert "def score_code" in context
    assert "# File: pr_judge.py" in context
    assert "def analyze_pr" in context


def test_build_diff_context_truncates_oversized_input():
    huge_source = "x = 1\n" * 100_000
    context = build_diff_context({"big.py": huge_source})

    assert len(context) < len(huge_source)
    assert "truncated" in context
import subprocess
import tempfile
from pathlib import Path
from diff_engine import (
    find_changed_functions,
    get_git_diff,
    parse_diff,
)

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
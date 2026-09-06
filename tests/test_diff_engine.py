from diff_engine import parse_diff


def test_parse_diff_detects_changed_lines():
    diff = """@@ -10,3 +10,3 @@
 def calculate():
-    return 10
+    return 20
 """

    result = parse_diff(diff)

    assert result["added_lines"] == [
        {"line": 11, "content": "    return 20"},
    ]

    assert result["removed_lines"] == [
        {"line": 11, "content": "    return 10"},
    ]


def test_parse_diff_tracks_line_numbers():
    diff = """@@ -10,3 +10,4 @@
 def calculate():
-    return 10
+    value = 20
+    return value
 """

    result = parse_diff(diff)

    assert result["added_lines"] == [
        {"line": 11, "content": "    value = 20"},
        {"line": 12, "content": "    return value"},
    ]

    assert result["removed_lines"] == [
        {"line": 11, "content": "    return 10"},
    ]

def test_parse_diff_handles_multiple_hunks():
    diff = """--- a/example.py
+++ b/example.py
@@ -10,2 +10,2 @@
 def first():
-    return 1
+    return 2
@@ -30,2 +30,3 @@
 def second():
     value = 10
+    value += 1
     return value
"""

    result = parse_diff(diff)

    assert result["removed_lines"] == [
        {"line": 11, "content": "    return 1"},
    ]

    assert result["added_lines"] == [
        {"line": 11, "content": "    return 2"},
        {"line": 32, "content": "    value += 1"},
    ]


def test_parse_diff_handles_multiple_removed_lines():
    diff = """@@ -10,5 +10,3 @@
 def calculate():
-    old_value = 1
-    old_value = 2
     return 3
"""

    result = parse_diff(diff)

    assert result["removed_lines"] == [
        {"line": 11, "content": "    old_value = 1"},
        {"line": 12, "content": "    old_value = 2"},
    ]

    assert result["added_lines"] == []


def test_parse_diff_ignores_file_headers():
    diff = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def test():
-    return 1
+    return 2
"""

    result = parse_diff(diff)

    assert result["added_lines"] == [
        {"line": 2, "content": "    return 2"},
    ]

    assert result["removed_lines"] == [
        {"line": 2, "content": "    return 1"},
    ]

def test_parse_diff_ignores_no_newline_marker():
    diff = """@@ -1,2 +1,2 @@
 def test():
-    return 1
+    return 2
\\ No newline at end of file
"""

    result = parse_diff(diff)

    assert result["added_lines"] == [
        {"line": 2, "content": "    return 2"},
    ]

    assert result["removed_lines"] == [
        {"line": 2, "content": "    return 1"},
    ]

def test_get_git_diff_returns_unified_diff():
    from diff_engine import get_git_diff

    diff = get_git_diff("be56c3a", "HEAD", "diff_engine.py")

    assert "diff --git" in diff
    assert "@@" in diff
    assert "+import re" in diff

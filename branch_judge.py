import argparse

from diff_engine import (
    find_changed_functions,
    get_file_at_ref,
    get_git_diff,
    get_git_diff_name_status,
)


def analyze_branch_pair(
    base_ref: str,
    head_ref: str,
    use_ai: bool = False,
    repo_path: str = ".",
) -> dict:
    """Compare two local git refs inside a specific repository."""

    changes = get_git_diff_name_status(
        base_ref,
        head_ref,
        repo_path=repo_path,
    )

    report = {
        "base": base_ref,
        "head": head_ref,
        "files": [],
        "functions": [],
    }

    for status, path in changes:
        if not path.endswith(".py"):
            continue

        file_result = {
            "status": status,
            "path": path,
        }

        if status.startswith("A"):
            report["files"].append(file_result)
            report["functions"].append(
                {
                    "path": path,
                    "name": None,
                    "type": "added_file",
                    "changed_new_lines": [],
                    "changed_old_lines": [],
                }
            )
            continue

        if status.startswith("D"):
            report["files"].append(file_result)
            report["functions"].append(
                {
                    "path": path,
                    "name": None,
                    "type": "deleted_file",
                    "changed_new_lines": [],
                    "changed_old_lines": [],
                }
            )
            continue

        if status.startswith("R"):
            report["files"].append(file_result)
            report["functions"].append(
                {
                    "path": path,
                    "name": None,
                    "type": "renamed_file",
                    "changed_new_lines": [],
                    "changed_old_lines": [],
                }
            )
            continue

        diff = get_git_diff(
            base_ref,
            head_ref,
            path,
            repo_path=repo_path,
        )

        if not diff:
            continue

        old_source = get_file_at_ref(
            base_ref,
            path,
            repo_path=repo_path,
        )

        new_source = get_file_at_ref(
            head_ref,
            path,
            repo_path=repo_path,
        )

        changed_functions = find_changed_functions(
            old_source,
            new_source,
            diff,
        )

        report["files"].append(
            {
                **file_result,
                "changed_functions": len(changed_functions),
            }
        )

        for function in changed_functions:
            item = {
                "path": path,
                "name": function["name"],
                "type": (
                    "new"
                    if function["old"] is None
                    else "modified"
                ),
                "changed_new_lines": function["changed_new_lines"],
                "changed_old_lines": function["changed_old_lines"],
            }

            if use_ai and function["old"] is not None:
                from judge import score_code

                item["verdict"] = score_code(
                    function["name"],
                    function["old"]["code"],
                    function["new"]["code"],
                )

            report["functions"].append(item)

    return report


def print_report(report: dict) -> None:
    print()
    print("=" * 60)
    print("AI DIFF JUDGE")
    print("=" * 60)
    print()
    print(f"BASE: {report['base']}")
    print(f"HEAD: {report['head']}")
    print()

    if not report["files"]:
        print("No changed Python files.")
        return

    print("CHANGED FILES")
    print("-" * 60)

    for file in report["files"]:
        print(
            f"{file['status']:>4}  {file['path']}"
        )

    print()
    print("CHANGED FUNCTIONS")
    print("-" * 60)

    if not report["functions"]:
        print("No changed functions.")
        return

    for function in report["functions"]:
        function_type = function["type"]

        if function_type == "added_file":
            print(f"NEW FILE     {function['path']}")
            continue

        if function_type == "deleted_file":
            print(f"DELETED FILE {function['path']}")
            continue

        if function_type == "renamed_file":
            print(f"RENAMED FILE {function['path']}")
            continue

        lines = ", ".join(
            str(line)
            for line in function["changed_new_lines"]
        )

        print(
            f"{function['path']}::"
            f"{function['name']} "
            f"[lines: {lines}]"
        )

        if "verdict" in function:
            verdict = function["verdict"]

            print(f"   Winner: {verdict.get('winner', 'tie')} (confidence: {verdict.get('confidence', 0.0):.2f})")

            for criterion in ("correctness", "security", "performance", "readability"):
                c = verdict.get(criterion, {})
                print(f"   {criterion:<12} old={c.get('old', '?')} new={c.get('new', '?')}  {c.get('reason', 'no data')}")

    total_delta = sum(
        function["verdict"].get("weighted_delta", 0)
        for function in report["functions"]
        if "verdict" in function
    )

    all_bugs = [
        bug
        for function in report["functions"]
        if "verdict" in function
        for bug in function["verdict"].get("bugs_found", [])
    ]

    print()
    print("WEIGHTED SUMMARY")
    print("-" * 60)
    print(f"Total weighted delta: {total_delta:+.1f}")

    if total_delta > 0:
        print("Overall: NEW is better")
    elif total_delta < 0:
        print("Overall: OLD is better")
    else:
        print("Overall: TIE")

    if all_bugs:
        print()
        print("BUGS FOUND")
        print("-" * 60)
        for bug in all_bugs:
            print(f"- {bug}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two local git refs."
    )

    parser.add_argument(
        "--base",
        required=True,
        help="Base git branch or ref.",
    )

    parser.add_argument(
        "--head",
        required=True,
        help="Head git branch or ref.",
    )

    parser.add_argument(
        "--judge",
        action="store_true",
        help="Run the LLM judge.",
    )

    args = parser.parse_args()

    report = analyze_branch_pair(
        args.base,
        args.head,
        use_ai=args.judge,
    )

    print_report(report)


if __name__ == "__main__":
    main()
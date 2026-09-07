import json
from collections import defaultdict
from judge import compare_code


def run_benchmark(dataset_path: str = "benchmark/pairwise_dataset.json") -> None:
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    correct = 0
    total = len(dataset)
    results = []

    category_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for item in dataset:
        print(f"Evaluating: {item['function_name']} ({item['category']})...")

        verdict = compare_code(
            item["function_name"],
            item["old_code"],
            item["new_code"],
        )

        ai_label = verdict.get("winner", "tie")
        human_label = item["human_label"]
        is_correct = ai_label == human_label
        category = item["category"]

        if is_correct:
            correct += 1
            category_stats[category]["correct"] += 1

        category_stats[category]["total"] += 1

        results.append(
            {
                "function_name": item["function_name"],
                "category": category,
                "human_label": human_label,
                "ai_label": ai_label,
                "correct": is_correct,
                "reason": verdict.get("reason", ""),
            }
        )

    print()
    print("=" * 60)
    print("RESULTS BY EXAMPLE")
    print("=" * 60)

    for r in results:
        mark = "PASS" if r["correct"] else "FAIL"
        print(f"[{mark}] ({r['category']}) {r['function_name']}: human={r['human_label']}, ai={r['ai_label']}")
        if not r["correct"]:
            print(f"       reason: {r['reason']}")

    print()
    print("=" * 60)
    print("RESULTS BY CATEGORY")
    print("=" * 60)

    for category, stats in sorted(category_stats.items()):
        pct = stats["correct"] / stats["total"] * 100
        print(f"{category:<20} {stats['correct']}/{stats['total']} ({pct:.1f}%)")

    print()
    accuracy = correct / total * 100
    print(f"OVERALL: {correct}/{total} ({accuracy:.1f}%)")


if __name__ == "__main__":
    run_benchmark()
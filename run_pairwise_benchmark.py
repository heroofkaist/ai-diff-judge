import json
from pathlib import Path
from judge import compare_code


def run_benchmark(dataset_path: str = "benchmark/pairwise_dataset.json") -> None:
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    correct = 0
    total = len(dataset)
    results = []

    for item in dataset:
        print(f"Оцениваем: {item['function_name']}...")

        verdict = compare_code(
            item["function_name"],
            item["old_code"],
            item["new_code"],
        )

        ai_label = verdict.get("winner", "tie")
        human_label = item["human_label"]
        is_correct = ai_label == human_label

        if is_correct:
            correct += 1

        results.append(
            {
                "function_name": item["function_name"],
                "human_label": human_label,
                "ai_label": ai_label,
                "correct": is_correct,
                "reason": verdict.get("reason", ""),
            }
        )

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ БЕНЧМАРКА")
    print("=" * 60)

    for r in results:
        mark = "✅" if r["correct"] else "❌"
        print(f"{mark} {r['function_name']}: человек={r['human_label']}, ИИ={r['ai_label']}")
        if not r["correct"]:
            print(f"   Причина ИИ: {r['reason']}")

    accuracy = correct / total * 100
    print()
    print(f"Совпадение с человеком: {correct}/{total} ({accuracy:.1f}%)")


if __name__ == "__main__":
    run_benchmark()
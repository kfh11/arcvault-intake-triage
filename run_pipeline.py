#!/usr/bin/env python3
"""CLI entry point: process all sample inputs and write structured output."""

import json
import sys
from pathlib import Path

from pipeline.pipeline import process


def main() -> None:
    inputs_path = Path("data/sample_inputs.json")
    output_path = Path("data/classification_results.json")

    with open(inputs_path) as f:
        samples = json.load(f)

    results = []

    for sample in samples:
        print(f"\n{'='*60}")
        print(f"Processing input #{sample['id']} ({sample['source']})")
        print(f"Message: {sample['message'][:80]}...")
        print(f"{'='*60}")

        try:
            result = process(source=sample["source"], message=sample["message"])
            result_dict = result.model_dump()
            result_dict["input_id"] = sample["id"]
            results.append(result_dict)

            print(f"  Category:    {result.category}")
            print(f"  Priority:    {result.priority}")
            print(f"  Confidence:  {result.confidence:.2f}")
            print(f"  Queue:       {result.destination_queue}")
            print(f"  Escalation:  {result.escalation_needed}")
            if result.escalation_reason:
                print(f"  Reason:      {result.escalation_reason}")
            print(f"  Summary:     {result.summary[:100]}...")
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            results.append({"input_id": sample["id"], "error": str(e)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Results written to {output_path}")
    print(f"Total: {len(results)} records processed")

    escalated = sum(1 for r in results if r.get("escalation_needed"))
    print(f"Escalated: {escalated}/{len(results)}")


if __name__ == "__main__":
    main()

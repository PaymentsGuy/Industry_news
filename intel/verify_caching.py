"""Run after a workflow completes to verify caching is actually working."""
import json
import sys
from pathlib import Path

PRICE_INPUT_NORMAL = 3.00
PRICE_INPUT_CACHE_WRITE = 3.75
PRICE_INPUT_CACHE_READ = 0.30
PRICE_OUTPUT = 15.00


def main(path: str) -> None:
    items = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    items_with_stats = [i for i in items if "_cache_stats" in i]

    if not items_with_stats:
        print("No cache stats found in this file - was the run made before caching was enabled?")
        return

    total_writes = sum(i["_cache_stats"]["cache_creation_input_tokens"] for i in items_with_stats)
    total_reads = sum(i["_cache_stats"]["cache_read_input_tokens"] for i in items_with_stats)
    total_uncached_input = sum(i["_cache_stats"]["input_tokens"] for i in items_with_stats)
    total_output = sum(i["_cache_stats"]["output_tokens"] for i in items_with_stats)

    cost_writes = total_writes * PRICE_INPUT_CACHE_WRITE / 1_000_000
    cost_reads = total_reads * PRICE_INPUT_CACHE_READ / 1_000_000
    cost_uncached = total_uncached_input * PRICE_INPUT_NORMAL / 1_000_000
    cost_output = total_output * PRICE_OUTPUT / 1_000_000
    total_cost = cost_writes + cost_reads + cost_uncached + cost_output

    counterfactual_input = (total_writes + total_reads + total_uncached_input)
    counterfactual_cost = (counterfactual_input * PRICE_INPUT_NORMAL / 1_000_000) + cost_output

    savings = counterfactual_cost - total_cost
    pct = 100 * savings / counterfactual_cost if counterfactual_cost else 0

    print(f"Triage items processed:        {len(items_with_stats)}")
    print(f"Cache write tokens (1st call): {total_writes:>10,}")
    print(f"Cache read tokens (subsequent):{total_reads:>10,}")
    print(f"Uncached input tokens:         {total_uncached_input:>10,}")
    print(f"Output tokens:                 {total_output:>10,}")
    print()
    print(f"Cache hit ratio:               {100 * total_reads / max(total_reads + total_writes, 1):>5.1f}%")
    print(f"Actual cost this run:          ${total_cost:>6.4f}")
    print(f"Cost without caching:          ${counterfactual_cost:>6.4f}")
    print(f"Savings:                       ${savings:>6.4f} ({pct:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python verify_caching.py <path-to-triaged.jsonl>")
        sys.exit(1)
    main(sys.argv[1])

"""Print basic stats about data/issues.jsonl."""
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "issues.jsonl"
issues = [json.loads(line) for line in path.open()]
labels = Counter(label for i in issues for label in i["labels"])
dups = [i for i in issues if i["state_reason"] == "duplicate" or any("dup" in l.lower() for l in i["labels"])]

print(f"Total issues: {len(issues)}")
print(f"Duplicates (state_reason or label containing 'dup'): {len(dups)}")
print("Top 20 labels:")
for name, count in labels.most_common(20):
    print(f"  {count:5d}  {name}")

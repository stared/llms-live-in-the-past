"""Find all answered model IDs that don't match any model in models.json.
Group by answered_id to see frequency and suggest alias mappings."""
import json
from collections import Counter

data = json.load(open("results/queries_20260416_124134.json"))
models = json.load(open("config/models.json"))
model_index = {m["model_id"]: m for m in models}

# Find latest per family
latest = {}
for m in models:
    if m["family"] not in latest or m["release_date"] > latest[m["family"]]["release_date"]:
        latest[m["family"]] = m

unresolved = Counter()
resolved_wrong = Counter()
exact = 0

for q in data:
    aid = q["answered_model_id"]
    if not aid:
        continue
    fam = q["subject_family"]
    expected = latest.get(fam, {}).get("model_id")

    if aid == expected:
        exact += 1
    elif aid in model_index:
        # Known model but not the latest
        resolved_wrong[(aid, fam)] += 1
    else:
        # Unknown model ID - needs alias or addition to models.json
        unresolved[(aid, fam)] += 1

print(f"Exact matches: {exact}")
print(f"Known-but-wrong: {sum(resolved_wrong.values())}")
print(f"Unresolved (need alias): {sum(unresolved.values())}")

# Show unresolved grouped by answered_id
print(f"\n=== Unresolved IDs (need alias mapping) ===")
by_id = {}
for (aid, fam), count in unresolved.items():
    if aid not in by_id:
        by_id[aid] = []
    by_id[aid].append((fam, count))

for aid in sorted(by_id.keys()):
    families = by_id[aid]
    total = sum(c for _, c in families)
    # Try to guess what it should map to
    print(f"\n  \"{aid}\" ({total}x)")
    for fam, count in sorted(families):
        expected = latest.get(fam, {}).get("model_id", "?")
        print(f"    asked about {fam} → expected {expected}")

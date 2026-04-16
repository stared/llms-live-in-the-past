"""Inspect what a specific answerer claims about each family."""
import json, sys, re

data = json.load(open("results/queries_20260416_124134.json"))
models = json.load(open("config/models.json"))

# Parse aliases
aliases = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        m = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if m:
            aliases[m.group(1)] = m.group(2)

model_index = {m["model_id"]: m for m in models}

# Find latest per family
latest = {}
for m in models:
    if m["family"] not in latest or m["release_date"] > latest[m["family"]]["release_date"]:
        latest[m["family"]] = m

# Filter by answerer pattern
pattern = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5"

for q in data:
    if pattern not in q["answerer_model_id"]:
        continue

    aid = q["answered_model_id"]
    resolved = aliases.get(aid, aid) if aid else None
    fam = q["subject_family"]
    expected = latest[fam]["model_id"]
    expected_date = latest[fam]["release_date"]

    resolved_info = model_index.get(resolved) if resolved else None
    resolved_date = resolved_info["release_date"] if resolved_info else "?"

    answerer_info = model_index.get(q["answerer_model_id"])
    answerer_date = answerer_info["release_date"] if answerer_info else "?"

    mark = "✓" if resolved == expected else "✗"
    print(f"  {mark} {q['answerer_model_id']} ({answerer_date}) about {fam}:")
    print(f"    raw answer: {aid}")
    print(f"    resolved:   {resolved} ({resolved_date})")
    print(f"    expected:   {expected} ({expected_date})")
    print()

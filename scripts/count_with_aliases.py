"""Re-evaluate results applying the alias mapping from model-aliases.ts."""
import json, re

data = json.load(open("results/queries_20260416_124134.json"))
models = json.load(open("config/models.json"))

# Parse aliases from TS file
aliases = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        m = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if m:
            aliases[m.group(1)] = m.group(2)

model_index = {m["model_id"]: m for m in models}
latest = {}
for m in models:
    if m["family"] not in latest or m["release_date"] > latest[m["family"]]["release_date"]:
        latest[m["family"]] = m

exact = 0
wrong_known = 0
wrong_unknown = 0
parse_fail = 0
unresolved = set()

for q in data:
    aid = q["answered_model_id"]
    fam = q["subject_family"]
    expected_id = latest[fam]["model_id"]

    if not aid:
        parse_fail += 1
        continue

    resolved = aliases.get(aid, aid)

    if resolved == expected_id:
        exact += 1
    elif resolved in model_index:
        wrong_known += 1
    else:
        wrong_unknown += 1
        unresolved.add(aid)

total = len(data)
print(f"Total: {total}")
print(f"Exact: {exact}")
print(f"Wrong (known model): {wrong_known}")
print(f"Wrong (unresolved): {wrong_unknown}")
print(f"Parse failures: {parse_fail}")
print(f"\nStill unresolved ({len(unresolved)}):")
for u in sorted(unresolved):
    print(f"  {u}")

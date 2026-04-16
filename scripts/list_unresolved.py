"""List all unresolved IDs from v2 and v3, with frequency and sample context."""
import json
import re
from collections import Counter

V2 = "results/queries_20260416_124134.json"
V3 = "results/queries_20260416_195217.json"

models = json.load(open("config/models.json"))
model_index = {m["model_id"]: m for m in models}

aliases = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        m = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if m:
            aliases[m.group(1)] = m.group(2)

all_data = json.load(open(V2)) + json.load(open(V3))

unresolved = Counter()
samples = {}
for q in all_data:
    aid = q["answered_model_id"]
    if not aid or aid.startswith("ERROR"):
        continue
    if aid.lower().strip() in ("unknown", "i don't know", "i don’t know") or len(aid) > 60:
        continue
    resolved = aliases.get(aid, aid)
    if resolved in model_index:
        continue
    unresolved[aid] += 1
    if aid not in samples:
        samples[aid] = (q["answerer_model_id"], q["subject_family"])

print(f"{len(unresolved)} unique unresolved IDs\n")
for aid, count in unresolved.most_common():
    answerer, fam = samples[aid]
    print(f"  {count:>3}x  {aid!r:<50}  (e.g. {answerer} about {fam})")

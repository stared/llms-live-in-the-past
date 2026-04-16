"""List pairs where v3 answer became unresolved compared to v2 (regressions)."""
import json, re

V2 = "results/queries_20260416_124134.json"
V3 = "results/queries_20260416_195217.json"

models = json.load(open("config/models.json"))
model_index = {m["model_id"]: m for m in models}

aliases = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        mm = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if mm:
            aliases[mm.group(1)] = mm.group(2)


def status(aid: str | None) -> str:
    if not aid:
        return "parse_fail"
    if aid.lower().strip() in ("unknown", "i don't know", "i don’t know") or len(aid) > 50:
        return "refusal"
    resolved = aliases.get(aid, aid)
    if resolved in model_index:
        return "known"
    return "unresolved"


v2 = json.load(open(V2))
v3 = json.load(open(V3))
v2_by = {(q["answerer_model_id"], q["subject_family"]): q for q in v2}
v3_by = {(q["answerer_model_id"], q["subject_family"]): q for q in v3}

# Pairs where v2 had a matchable answer and v3 doesn't
regressions = []
for pair in v2_by.keys() & v3_by.keys():
    v2_ans = v2_by[pair]["answered_model_id"]
    v3_ans = v3_by[pair]["answered_model_id"]
    v2_st = status(v2_ans)
    v3_st = status(v3_ans)

    if v2_st in ("known",) and v3_st == "unresolved":
        regressions.append((pair[0], pair[1], v2_ans, v3_ans))

print(f"=== {len(regressions)} regressions: v2 resolvable → v3 unresolvable ===\n")
print(f"{'Answerer':<44} {'Family':<14} {'v2 answer':<42} → v3 answer")
print("-" * 130)
for ans_m, fam, v2a, v3a in sorted(regressions):
    print(f"{ans_m:<44} {fam:<14} {v2a!r:<42} → {v3a!r}")

# New unresolved IDs in v3 that weren't in v2
v2_unresolved_ids = {q["answered_model_id"] for q in v2 if status(q["answered_model_id"]) == "unresolved"}
v3_unresolved_ids = {q["answered_model_id"] for q in v3 if status(q["answered_model_id"]) == "unresolved"}
new_in_v3 = v3_unresolved_ids - v2_unresolved_ids

print(f"\n\n=== {len(new_in_v3)} unresolved IDs new in v3 ===\n")
# Show them with pair context
new_occurrences = []
for q in v3:
    if q["answered_model_id"] in new_in_v3:
        pair = (q["answerer_model_id"], q["subject_family"])
        v2_ans = v2_by[pair]["answered_model_id"] if pair in v2_by else None
        new_occurrences.append((q["answerer_model_id"], q["subject_family"], v2_ans, q["answered_model_id"]))

print(f"{'Answerer':<44} {'Family':<14} {'v2 answer':<42} → v3 (new unresolved)")
print("-" * 130)
for ans_m, fam, v2a, v3a in sorted(new_occurrences):
    print(f"{ans_m:<44} {fam:<14} {v2a!r:<42} → {v3a!r}")

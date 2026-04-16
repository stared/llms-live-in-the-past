"""Compare v2 and v3 prompt runs side by side."""
import json
import re

V2 = "results/queries_20260416_124134.json"
V3 = "results/queries_20260416_195217.json"

models = json.load(open("config/models.json"))
model_index = {m["model_id"]: m for m in models}

latest = {}
for m in models:
    if m["family"] not in latest or m["release_date"] > latest[m["family"]]["release_date"]:
        latest[m["family"]] = m

aliases = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        mm = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if mm:
            aliases[mm.group(1)] = mm.group(2)


def analyze(path, label):
    data = json.load(open(path))
    exact = wrong_known = wrong_unresolved = parse_fail = refusal = 0
    unresolved_ids = set()

    for q in data:
        aid = q["answered_model_id"]
        fam = q["subject_family"]
        expected = latest[fam]["model_id"]
        raw = q["raw_response"]

        if raw.startswith("ERROR"):
            continue
        if not aid:
            parse_fail += 1
            continue
        if aid.lower().strip() in ("unknown", "i don't know", "i don’t know") or len(aid) > 50:
            refusal += 1
            continue

        resolved = aliases.get(aid, aid)
        if resolved == expected:
            exact += 1
        elif resolved in model_index:
            wrong_known += 1
        else:
            wrong_unresolved += 1
            unresolved_ids.add(aid)

    total = len(data)
    print(f"\n=== {label} ({path}) ===")
    print(f"Total: {total}")
    print(f"  Exact (correct):     {exact:>4}  ({100*exact/total:.1f}%)")
    print(f"  Wrong (known model): {wrong_known:>4}  ({100*wrong_known/total:.1f}%)")
    print(f"  Wrong (unresolved):  {wrong_unresolved:>4}  ({100*wrong_unresolved/total:.1f}%)")
    print(f"  Refusal:             {refusal:>4}  ({100*refusal/total:.1f}%)")
    print(f"  Parse failure:       {parse_fail:>4}  ({100*parse_fail/total:.1f}%)")
    print(f"  Unresolved IDs count: {len(unresolved_ids)}")
    return {
        "exact": exact, "wrong_known": wrong_known,
        "wrong_unresolved": wrong_unresolved, "refusal": refusal,
        "parse_fail": parse_fail, "unresolved_ids": unresolved_ids,
        "total": total,
    }


def pair_compare(v2_data, v3_data, label):
    # For same (answerer, family) pair, did the answer change?
    v2_by_pair = {(q["answerer_model_id"], q["subject_family"]): q for q in v2_data}
    v3_by_pair = {(q["answerer_model_id"], q["subject_family"]): q for q in v3_data}

    common = set(v2_by_pair) & set(v3_by_pair)
    same = 0
    diff = 0
    diff_samples = []
    for pair in common:
        v2_ans = v2_by_pair[pair]["answered_model_id"]
        v3_ans = v3_by_pair[pair]["answered_model_id"]
        if v2_ans == v3_ans:
            same += 1
        else:
            diff += 1
            if len(diff_samples) < 20:
                diff_samples.append((pair[0], pair[1], v2_ans, v3_ans))

    print(f"\n=== {label}: {len(common)} pairs in common ===")
    print(f"  Same answer: {same} ({100*same/len(common):.1f}%)")
    print(f"  Different:   {diff} ({100*diff/len(common):.1f}%)")
    print("\nSample differences (v2 → v3):")
    for ans_m, fam, v2a, v3a in diff_samples:
        print(f"  {ans_m:45} {fam:14}  {v2a!r:40} → {v3a!r}")


v2 = analyze(V2, "v2 (model number)")
v3 = analyze(V3, "v3 (model ID)")

print("\n" + "=" * 60)
print("DIFFERENCE:")
print(f"  Exact:            {v2['exact']:+} → {v3['exact']:+}   (Δ {v3['exact'] - v2['exact']:+})")
print(f"  Wrong known:      {v2['wrong_known']} → {v3['wrong_known']}   (Δ {v3['wrong_known'] - v2['wrong_known']:+})")
print(f"  Wrong unresolved: {v2['wrong_unresolved']} → {v3['wrong_unresolved']}   (Δ {v3['wrong_unresolved'] - v2['wrong_unresolved']:+})")
print(f"  Refusal:          {v2['refusal']} → {v3['refusal']}   (Δ {v3['refusal'] - v2['refusal']:+})")
print(f"  Parse fail:       {v2['parse_fail']} → {v3['parse_fail']}   (Δ {v3['parse_fail'] - v2['parse_fail']:+})")

only_v3 = v3['unresolved_ids'] - v2['unresolved_ids']
only_v2 = v2['unresolved_ids'] - v3['unresolved_ids']
print(f"\n  Unresolved only in v2 ({len(only_v2)}): {sorted(only_v2)[:10]}")
print(f"  Unresolved only in v3 ({len(only_v3)}): {sorted(only_v3)[:10]}")

pair_compare(
    json.load(open(V2)),
    json.load(open(V3)),
    "Pair-level comparison"
)

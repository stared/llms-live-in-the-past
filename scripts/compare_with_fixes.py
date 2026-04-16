"""Compare v2 and v3 after applying a hypothetical expanded alias set.

Adds aliases for:
  1. `-latest` suffix variants
  2. HuggingFace-style org prefixes (`Qwen/...`, `XiaomiMiMo/...`, `THUDM/...`)
  3. Google `models/` prefix
  4. Newer GPT-4o date stamps
  5. Dot-vs-dash format variations
"""
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

# Existing aliases
current = {}
with open("web/src/model-aliases.ts") as f:
    for line in f:
        mm = re.match(r'\s+"([^"]+)":\s+"([^"]+)"', line)
        if mm:
            current[mm.group(1)] = mm.group(2)


# Hypothetical additions covering fixable categories
HYPOTHETICAL = {
    # -latest variants → base model
    "claude-3-opus-latest": "anthropic/claude-3-opus",
    "claude-3-5-sonnet-latest": "anthropic/claude-3.5-sonnet",
    "claude-3.5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
    "kimi-latest": "moonshotai/kimi-k2-thinking",

    # HuggingFace-style org prefixes
    "Qwen/Qwen2.5-72B-Instruct": "qwen/qwen2.5-72b-instruct",
    "Qwen/MiMo-7B-RL": "xiaomi/mimo-7b",
    "XiaomiMiMo/MiMo-7B-RL": "xiaomi/mimo-7b",
    "Qwen/Qwen2-72B-Instruct": "qwen/qwen2-72b",
    "Qwen2-72B": "qwen/qwen2-72b",

    # Google models/ prefix
    "models/gemini-1.5-pro-latest": "google/gemini-1.5-pro",
    "models/gemini-1.5-flash-latest": "google/gemini-1.5-flash",

    # Format variations for known models
    "gpt-4o-2024-11-20": "openai/gpt-4o",
    "gemini-1.5-flash-001": "google/gemini-1.5-flash",
    "gpt-4-0125-preview": "openai/gpt-4-turbo",
    "claude-sonnet-4-5-20250929": "anthropic/claude-sonnet-4.5",
}

enhanced = {**current, **HYPOTHETICAL}


def status(aid, aliases):
    if not aid:
        return "parse_fail"
    if aid.lower().strip() in ("unknown", "i don't know", "i don’t know") or len(aid) > 50:
        return "refusal"
    resolved = aliases.get(aid, aid)
    if resolved in model_index:
        fam_latest = None
        for fam, m in latest.items():
            if m["model_id"] == resolved:
                return "exact"
        return "known"
    return "unresolved"


def analyze(path, aliases, label):
    data = json.load(open(path))
    exact = known = unresolved = parse_fail = refusal = 0

    for q in data:
        if q["raw_response"].startswith("ERROR"):
            continue
        aid = q["answered_model_id"]
        fam = q["subject_family"]
        expected = latest[fam]["model_id"]

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
            known += 1
        else:
            unresolved += 1

    return {"label": label, "exact": exact, "known": known, "unresolved": unresolved,
            "refusal": refusal, "parse_fail": parse_fail, "total": len(data)}


rows = [
    analyze(V2, current, "v2 (model number) — current aliases"),
    analyze(V3, current, "v3 (model ID)    — current aliases"),
    analyze(V2, enhanced, "v2 (model number) — with extra aliases"),
    analyze(V3, enhanced, "v3 (model ID)    — with extra aliases"),
]

print(f"\n{'':48} {'Exact':>5}  {'Wrong':>6}  {'Unres':>6}  {'Refusal':>7}  {'Parse':>5}")
print("-" * 92)
for r in rows:
    print(f"  {r['label']:<46} {r['exact']:>5}  {r['known']:>6}  {r['unresolved']:>6}  {r['refusal']:>7}  {r['parse_fail']:>5}")

v2c, v3c, v2e, v3e = rows
print("\n── Effect of adding the extra aliases ──")
print(f"  v2: unresolved {v2c['unresolved']} → {v2e['unresolved']} (Δ {v2e['unresolved'] - v2c['unresolved']:+})")
print(f"  v3: unresolved {v3c['unresolved']} → {v3e['unresolved']} (Δ {v3e['unresolved'] - v3c['unresolved']:+})")
print(f"\n  v2: known-wrong {v2c['known']} → {v2e['known']} (Δ {v2e['known'] - v2c['known']:+})")
print(f"  v3: known-wrong {v3c['known']} → {v3e['known']} (Δ {v3e['known'] - v3c['known']:+})")

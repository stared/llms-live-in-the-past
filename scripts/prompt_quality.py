"""Classify answers by format to see if 'exact model number' causes issues."""
import json
import re
from collections import Counter

data = json.load(open("results/queries_20260416_124134.json"))

# Categories
API_ID_WITH_DATE = "API-id with date stamp"       # gpt-4o-2024-08-06, claude-3-opus-20240229
API_ID_CLEAN = "API-id clean"                      # gpt-4o, gemini-1.5-pro, kimi-k2
MARKETING_NAME = "Marketing name (Has Capital / spaces)"  # Claude 3.5 Sonnet, Gemini Pro
HALLUCINATED_NUMERIC = "Hallucinated (weird numbering)"  # CS-2023, MiMo-2, Gemini Flash 3X
PARSE_FAIL_OR_REFUSAL = "Refusal / parse failure"  # "I don't know", None
UNKNOWN = "Unclassified"

buckets = {k: [] for k in [
    API_ID_WITH_DATE, API_ID_CLEAN, MARKETING_NAME,
    HALLUCINATED_NUMERIC, PARSE_FAIL_OR_REFUSAL, UNKNOWN,
]}

def classify(ans: str | None) -> str:
    if not ans:
        return PARSE_FAIL_OR_REFUSAL
    if "don't know" in ans.lower() or "don’t know" in ans.lower() or "unknown" in ans.lower():
        return PARSE_FAIL_OR_REFUSAL
    if "?" in ans or len(ans) > 50:
        return PARSE_FAIL_OR_REFUSAL
    # Date stamp at end: -YYYYMMDD or -YYYY-MM-DD
    if re.search(r"-\d{8}$|-\d{4}-\d{2}-\d{2}$", ans):
        return API_ID_WITH_DATE
    # Has space or capital letters at start (marketing)
    if " " in ans and re.match(r"^[A-Z]", ans):
        return MARKETING_NAME
    # Weird numeric patterns: "CS-2023", "MiMo-2", "Gemini Flash 3X", just a year
    if re.search(r"\b(19|20)\d{2}\b", ans) and not re.search(r"-\d{8}|-\d{4}-\d{2}-\d{2}", ans):
        return HALLUCINATED_NUMERIC
    if re.match(r"^[A-Z][A-Za-z]+-\d+(-?[A-Z])?$", ans):  # "MiMo-2", "GLM-130B"
        return HALLUCINATED_NUMERIC
    # Looks like a clean API id: lowercase, hyphens, digits
    if re.match(r"^[a-z][a-z0-9.\-/:]*$", ans):
        return API_ID_CLEAN
    return UNKNOWN

for q in data:
    ans = q["answered_model_id"]
    if q["raw_response"].startswith("ERROR"):
        continue
    cat = classify(ans)
    buckets[cat].append((q["answerer_model_id"], q["subject_family"], ans))

total = sum(len(v) for v in buckets.values())
print(f"Total non-error responses: {total}\n")
for cat, items in buckets.items():
    pct = 100 * len(items) / total
    print(f"  {cat}: {len(items)} ({pct:.1f}%)")

print("\n── Sample from each bucket ──")
for cat, items in buckets.items():
    print(f"\n{cat}:")
    for ans_m, fam, ans in items[:5]:
        print(f"  {ans_m} about {fam} → {ans}")

"""Check which of our model IDs exist on OpenRouter."""
import json
import urllib.request

# Fetch OpenRouter model list
print("Fetching OpenRouter model list...")
req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models",
    headers={"User-Agent": "Mozilla/5.0"},
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

or_ids = {m["id"] for m in data["data"]}
print(f"OpenRouter has {len(or_ids)} models\n")

# Load our config
models = json.load(open("config/models.json"))
experiment = json.load(open("config/experiment.json"))

# Check all model_ids in models.json
print("=== models.json ===")
for m in models:
    mid = m["model_id"]
    status = "OK" if mid in or_ids else "MISSING"
    if status == "MISSING":
        print(f"  {status}: {mid} ({m['family']})")

# Check answerers
print("\n=== experiment.json answerers ===")
valid = []
invalid = []
for mid in experiment["answerer_model_ids"]:
    if mid in or_ids:
        valid.append(mid)
    else:
        invalid.append(mid)

print(f"Valid: {len(valid)}, Invalid: {len(invalid)}")
if invalid:
    print("\nInvalid answerers:")
    for mid in invalid:
        print(f"  {mid}")

        # Try to find close matches
        prefix = mid.split("/")[0]
        base = mid.split("/")[1].split("-")[0] if "/" in mid else mid
        close = sorted([oid for oid in or_ids if oid.startswith(prefix + "/")])
        # Show ones that share a common substring
        name_part = mid.split("/")[1] if "/" in mid else mid
        matches = [oid for oid in close if any(
            chunk in oid for chunk in name_part.split("-") if len(chunk) > 2
        )]
        if matches:
            print(f"    similar: {', '.join(matches[:5])}")

print(f"\nValid answerers ({len(valid)}):")
for mid in valid:
    print(f"  {mid}")

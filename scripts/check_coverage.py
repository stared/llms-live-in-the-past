"""Check which answerers have actual data vs errors in the latest results."""
import json, sys

# Check both the served file and the latest results file
files = [
    "web/public/data/queries_20260414_140442.json",
    "results/queries_20260414_144217.json",
]

models = json.load(open("config/models.json"))
experiment = json.load(open("config/experiment.json"))
all_answerers = set(experiment["answerer_model_ids"])
all_families = set(experiment["subject_families"])

for path in files:
    try:
        data = json.load(open(path))
    except FileNotFoundError:
        continue

    print(f"\n{'='*60}")
    print(f"File: {path}")
    print(f"Total queries: {len(data)}")

    errors = [q for q in data if q["raw_response"].startswith("ERROR")]
    ok = [q for q in data if not q["raw_response"].startswith("ERROR")]
    print(f"OK: {len(ok)}, Errors: {len(errors)}")

    # Answerers with successful data
    ok_answerers = set(q["answerer_model_id"] for q in ok)
    err_answerers = set(q["answerer_model_id"] for q in errors)

    # Answerers with ONLY errors (no successful queries)
    only_errors = err_answerers - ok_answerers

    print(f"\nAnswerers with data: {len(ok_answerers)}")
    print(f"Answerers with only errors: {len(only_errors)}")
    if only_errors:
        for m in sorted(only_errors):
            sample = next(q for q in errors if q["answerer_model_id"] == m)
            print(f"  {m}: {sample['raw_response'][:120]}")

    # Answerers in experiment but not in data at all
    missing = all_answerers - ok_answerers - err_answerers
    if missing:
        print(f"\nAnswerers in experiment.json but not in data at all: {len(missing)}")
        for m in sorted(missing):
            print(f"  {m}")

    # Per-answerer coverage
    partial = []
    for ans in sorted(ok_answerers):
        fams = set(q["subject_family"] for q in ok if q["answerer_model_id"] == ans)
        err_fams = set(q["subject_family"] for q in errors if q["answerer_model_id"] == ans)
        missing_fams = all_families - fams
        if missing_fams:
            partial.append((ans, missing_fams, err_fams & missing_fams))

    if partial:
        print(f"\nAnswerers with incomplete family coverage:")
        for ans, missing_f, err_f in partial:
            print(f"  {ans}: missing {len(missing_f)} families")

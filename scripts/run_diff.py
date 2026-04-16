"""Run queries only for answerers missing from the latest results file.

Merges new results into the existing file.
Usage: OPENROUTER_API_KEY=... uv run scripts/run_diff.py [results_file]
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir so we can import from main
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import (
    MODELS, PROMPTS, EXPERIMENT,
    build_model_index, find_latest_per_family, extract_model_id,
    Query, AsyncOpenAI, MAX_CONCURRENT, MAX_RETRIES, RETRY_DELAY,
)

RESULTS_FILE = sys.argv[1] if len(sys.argv) > 1 else "results/queries_20260416_124134.json"


async def query_model(client, model, prompt, family):
    from main import query_model as _qm
    return await _qm(client, model, prompt, family)


async def run_one(client, sem, answerer_id, family, prompt, prompt_id, model_index, latest_per_family, idx, total):
    short = answerer_id.split("/", 1)[1]
    async with sem:
        raw = None
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                raw = await query_model(client, answerer_id, prompt, family)
                break
            except Exception as e:
                last_err = e
                if "404" in str(e) or "400" in str(e):
                    break
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        if raw is None:
            print(f"  [{idx}/{total}] {short} — ERROR about {family}", flush=True)
            return Query(
                answerer_model_id=answerer_id, subject_family=family,
                prompt_id=prompt_id, answered_model_id=None,
                raw_response=f"ERROR: {last_err}",
                queried_at=datetime.now(timezone.utc).isoformat(),
            )

    answered_id = extract_model_id(raw)
    answered_short = answered_id.split("/", 1)[1] if answered_id and "/" in answered_id else answered_id
    expected_id = latest_per_family.get(family)
    mark = "✓" if answered_id == expected_id else ("?" if not answered_id else "✗")
    result_str = answered_short or "PARSE FAILURE"
    print(f"  {mark} [{idx}/{total}] {short} said the latest {family} is {result_str}", flush=True)

    return Query(
        answerer_model_id=answerer_id, subject_family=family,
        prompt_id=prompt_id, answered_model_id=answered_id,
        raw_response=raw, queried_at=datetime.now(timezone.utc).isoformat(),
    )


async def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        raise SystemExit(1)

    # Load existing results
    existing = json.load(open(RESULTS_FILE))
    existing_pairs = {(q["answerer_model_id"], q["subject_family"]) for q in existing}
    print(f"Existing: {len(existing)} queries from {RESULTS_FILE}")

    # Find missing pairs
    all_answerers = EXPERIMENT.answerer_model_ids
    all_families = EXPERIMENT.subject_families
    missing = [(a, f) for a in all_answerers for f in all_families if (a, f) not in existing_pairs]
    print(f"Missing: {len(missing)} queries to run\n")

    if not missing:
        print("Nothing to do!")
        return

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    prompt_id = EXPERIMENT.prompt_id
    prompt = PROMPTS[prompt_id]
    model_index = build_model_index(MODELS)
    latest_per_family = find_latest_per_family(MODELS)

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = []
    for idx, (answerer_id, family) in enumerate(missing, 1):
        tasks.append(asyncio.create_task(
            run_one(client, sem, answerer_id, family, prompt, prompt_id,
                    model_index, latest_per_family, idx, len(missing))
        ))

    new_queries = await asyncio.gather(*tasks)

    # Merge
    merged = existing + [json.loads(q.model_dump_json()) for q in new_queries]
    Path(RESULTS_FILE).write_text(json.dumps(merged, indent=2))
    print(f"\nMerged {len(new_queries)} new queries into {RESULTS_FILE} (total: {len(merged)})")


if __name__ == "__main__":
    asyncio.run(main())

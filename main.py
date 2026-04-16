"""AI models live in the past — Do AI models know what's current?

Tests whether AI models correctly identify the most recent version of model
families when asked for OpenRouter model IDs.

Data is normalized into:
  - models.json:  reference table of known model IDs, families, release dates
  - prompts:      registered prompt templates (prompt_id → system + user template)
  - queries JSON:  raw observations (answerer, subject, prompt_id, answer, timestamp)

Evaluation (verdict, expected model, answered release date) is derived by
joining queries against the models table — never stored redundantly.
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, TypeAdapter

CONFIG_DIR = Path(__file__).parent / "config"


# ── Pydantic models ──────────────────────────────────────────────────────────


class Model(BaseModel):
    model_id: str
    family: str
    release_date: str  # "2024-03-13"


class Prompt(BaseModel):
    system: str
    user_template: str


class ExperimentConfig(BaseModel):
    answerer_model_ids: list[str]
    subject_families: list[str]
    prompt_id: str


class Query(BaseModel):
    answerer_model_id: str
    subject_family: str
    prompt_id: str
    answered_model_id: str | None
    raw_response: str
    queried_at: str


class EvaluatedQuery(Query):
    answerer_release_date: str | None = None
    expected_model_id: str | None = None
    expected_release_date: str | None = None
    answered_release_date: str | None = None
    verdict: str  # "exact" | "wrong" | "parse_failure"


# ── Load config ──────────────────────────────────────────────────────────────

_ModelList = TypeAdapter(list[Model])
_PromptDict = TypeAdapter(dict[str, Prompt])

MODELS: list[Model] = _ModelList.validate_json(
    (CONFIG_DIR / "models.json").read_bytes()
)

EXPERIMENT: ExperimentConfig = ExperimentConfig.model_validate_json(
    (CONFIG_DIR / "experiment.json").read_bytes()
)
ANSWERER_MODEL_IDS = EXPERIMENT.answerer_model_ids
SUBJECT_FAMILIES = EXPERIMENT.subject_families
DEFAULT_PROMPT_ID = EXPERIMENT.prompt_id

PROMPTS: dict[str, Prompt] = _PromptDict.validate_json(
    (CONFIG_DIR / "prompts.json").read_bytes()
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_model_index(models: list[Model]) -> dict[str, Model]:
    """model_id → Model"""
    return {m.model_id: m for m in models}


def find_latest_per_family(models: list[Model]) -> dict[str, str]:
    """family → model_id of the most recent model in that family."""
    latest: dict[str, Model] = {}
    for m in models:
        if m.family not in latest or m.release_date > latest[m.family].release_date:
            latest[m.family] = m
    return {fam: m.model_id for fam, m in latest.items()}


def extract_model_id(raw: str) -> str | None:
    """Extract model ID from a response that should be JSON like {"model": "..."}."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "model" in data:
            return data["model"]
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[^}]*"model"\s*:\s*"([^"]+)"[^}]*\}', raw)
    if match:
        return match.group(1)

    return None


def evaluate_query(
    query: Query,
    model_index: dict[str, Model],
    latest_per_family: dict[str, str],
) -> EvaluatedQuery:
    """Enrich a query row with derived fields for display."""
    expected_id = latest_per_family.get(query.subject_family)
    expected_date = model_index[expected_id].release_date if expected_id else None

    answered_info = model_index.get(query.answered_model_id) if query.answered_model_id else None
    answered_date = answered_info.release_date if answered_info else None

    answerer_info = model_index.get(query.answerer_model_id)
    answerer_date = answerer_info.release_date if answerer_info else None

    if query.answered_model_id is None:
        verdict = "parse_failure"
    elif query.answered_model_id == expected_id:
        verdict = "exact"
    else:
        verdict = "wrong"

    return EvaluatedQuery(
        **query.model_dump(),
        answerer_release_date=answerer_date,
        expected_model_id=expected_id,
        expected_release_date=expected_date,
        answered_release_date=answered_date,
        verdict=verdict,
    )


async def query_model(client: AsyncOpenAI, answerer_model: str, prompt: Prompt, family: str) -> str:
    user_content = prompt.user_template.format(family=family)
    response = await client.chat.completions.create(
        model=answerer_model,
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


def write_log(evaluated: list[EvaluatedQuery], path: str) -> None:
    """Write a human-readable log of all results."""
    lines: list[str] = []
    for r in evaluated:
        short = r.answerer_model_id.split("/", 1)[1]
        ans = r.answered_model_id or "PARSE_FAILURE"
        ans_short = ans.split("/", 1)[1] if "/" in ans else ans
        expected = (r.expected_model_id or "?").split("/", 1)[-1]
        mark = "✓" if r.verdict == "exact" else ("✗" if r.verdict == "wrong" else "?")
        lines.append(f"{mark} {short} said the latest {r.subject_family} is {ans_short} (expected {expected})")
    Path(path).write_text("\n".join(lines) + "\n")
    print(f"Log saved to {path}")


MAX_CONCURRENT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def run_query(
    client: AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    answerer_id: str,
    family: str,
    prompt: Prompt,
    prompt_id: str,
    model_index: dict[str, Model],
    latest_per_family: dict[str, str],
    idx: int,
    total: int,
) -> Query:
    short = answerer_id.split("/", 1)[1]
    async with semaphore:
        raw = None
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                raw = await query_model(client, answerer_id, prompt, family)
                break
            except Exception as e:
                last_err = e
                err_str = str(e)
                # Don't retry permanent errors (404 = model gone, 400 = invalid ID)
                if "404" in err_str or "400" in err_str:
                    break
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (attempt + 1)
                    await asyncio.sleep(delay)

        if raw is None:
            print(f"  [{idx}/{total}] {short} — ERROR querying about {family}", flush=True)
            return Query(
                answerer_model_id=answerer_id,
                subject_family=family,
                prompt_id=prompt_id,
                answered_model_id=None,
                raw_response=f"ERROR: {last_err}",
                queried_at=datetime.now(timezone.utc).isoformat(),
            )

    answered_id = extract_model_id(raw)
    answered_short = answered_id.split("/", 1)[1] if answered_id and "/" in answered_id else answered_id

    expected_id = latest_per_family.get(family)
    if answered_id is None:
        mark = "?"
        result_str = "PARSE FAILURE"
    elif answered_id == expected_id:
        mark = "✓"
        result_str = answered_short
    else:
        mark = "✗"
        result_str = answered_short

    print(f"  {mark} [{idx}/{total}] {short} said the latest {family} is {result_str}", flush=True)

    return Query(
        answerer_model_id=answerer_id,
        subject_family=family,
        prompt_id=prompt_id,
        answered_model_id=answered_id,
        raw_response=raw,
        queried_at=datetime.now(timezone.utc).isoformat(),
    )


async def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        raise SystemExit(1)

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    prompt_id = DEFAULT_PROMPT_ID
    prompt = PROMPTS[prompt_id]
    model_index = build_model_index(MODELS)
    latest_per_family = find_latest_per_family(MODELS)

    # Build all tasks with concurrency limit
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks: list[asyncio.Task[Query]] = []
    total = len(ANSWERER_MODEL_IDS) * len(SUBJECT_FAMILIES)
    idx = 0

    for answerer_id in ANSWERER_MODEL_IDS:
        for family in SUBJECT_FAMILIES:
            idx += 1
            task = asyncio.create_task(
                run_query(
                    client, semaphore, answerer_id, family, prompt, prompt_id,
                    model_index, latest_per_family, idx, total,
                )
            )
            tasks.append(task)

    # Run all concurrently
    queries = await asyncio.gather(*tasks)
    queries = list(queries)

    # Evaluate
    evaluated = [evaluate_query(q, model_index, latest_per_family) for q in queries]

    verdicts = [e.verdict for e in evaluated]
    errors = sum(1 for q in queries if q.raw_response.startswith("ERROR"))
    print(
        f"\nSummary: {verdicts.count('exact')} exact, "
        f"{verdicts.count('wrong')} wrong, "
        f"{verdicts.count('parse_failure')} parse failures, "
        f"{errors} errors "
        f"out of {len(verdicts)} total"
    )

    # Save
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    models_path = "results/models.json"
    Path(models_path).write_text(
        _ModelList.dump_json(MODELS, indent=2).decode()
    )

    queries_path = f"results/queries_{timestamp}.json"
    Path(queries_path).write_text(
        TypeAdapter(list[Query]).dump_json(queries, indent=2).decode()
    )
    print(f"Queries saved to {queries_path}")

    log_path = f"results/log_{timestamp}.txt"
    write_log(evaluated, log_path)


if __name__ == "__main__":
    asyncio.run(main())

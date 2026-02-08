"""We Live in the Past — Do AI models know what's current?

Tests whether AI models correctly identify the most recent version of model
families when asked for OpenRouter model IDs.

Data is normalized into:
  - models.json:  reference table of known model IDs, families, release dates
  - prompts:      registered prompt templates (prompt_id → system + user template)
  - queries JSON:  raw observations (answerer, subject, prompt_id, answer, timestamp)

Evaluation (verdict, expected model, answered release date) is derived by
joining queries against the models table — never stored redundantly.
"""

import json
import os
import re
from datetime import datetime, timezone

from openai import OpenAI

# ---------------------------------------------------------------------------
# Models table — every known model with family + release date
# ---------------------------------------------------------------------------

MODELS: list[dict] = [
    # Claude
    {"model_id": "anthropic/claude-3-haiku",       "family": "Claude Haiku",   "release_date": "2024-03-13"},
    {"model_id": "anthropic/claude-3.5-haiku",      "family": "Claude Haiku",   "release_date": "2024-11-04"},
    {"model_id": "anthropic/claude-haiku-4.5",      "family": "Claude Haiku",   "release_date": "2025-10-15"},
    {"model_id": "anthropic/claude-3.5-sonnet",     "family": "Claude Sonnet",  "release_date": "2024-10-22"},
    {"model_id": "anthropic/claude-3.7-sonnet",     "family": "Claude Sonnet",  "release_date": "2025-02-24"},
    {"model_id": "anthropic/claude-sonnet-4",       "family": "Claude Sonnet",  "release_date": "2025-05-22"},
    {"model_id": "anthropic/claude-sonnet-4.5",     "family": "Claude Sonnet",  "release_date": "2025-09-29"},
    {"model_id": "anthropic/claude-opus-4",         "family": "Claude Opus",    "release_date": "2025-05-22"},
    {"model_id": "anthropic/claude-opus-4.1",       "family": "Claude Opus",    "release_date": "2025-08-05"},
    {"model_id": "anthropic/claude-opus-4.5",       "family": "Claude Opus",    "release_date": "2025-11-24"},
    {"model_id": "anthropic/claude-opus-4.6",       "family": "Claude Opus",    "release_date": "2026-02-05"},
    # GPT
    {"model_id": "openai/gpt-4o",                   "family": "GPT",            "release_date": "2024-05-13"},
    {"model_id": "openai/gpt-4o-2024-05-13",        "family": "GPT",            "release_date": "2024-05-13"},
    {"model_id": "openai/gpt-4o-2024-08-06",        "family": "GPT",            "release_date": "2024-08-06"},
    {"model_id": "openai/gpt-4o-2024-11-20",        "family": "GPT",            "release_date": "2024-11-20"},
    {"model_id": "openai/gpt-4o-mini",              "family": "GPT Mini",       "release_date": "2024-07-18"},
    {"model_id": "openai/gpt-5",                    "family": "GPT",            "release_date": "2025-08-07"},
    {"model_id": "openai/gpt-5-mini",               "family": "GPT Mini",       "release_date": "2025-08-07"},
    {"model_id": "openai/gpt-5-nano",               "family": "GPT Nano",       "release_date": "2025-08-07"},
    {"model_id": "openai/gpt-5-pro",                "family": "GPT Pro",        "release_date": "2025-09-26"},
    {"model_id": "openai/gpt-5.1",                  "family": "GPT",            "release_date": "2025-11-13"},
    {"model_id": "openai/gpt-5.2",                  "family": "GPT",            "release_date": "2025-12-10"},
    {"model_id": "openai/gpt-5.2-pro",              "family": "GPT Pro",        "release_date": "2025-12-10"},
    # Gemini
    {"model_id": "google/gemini-2.0-flash-001",     "family": "Gemini Flash",   "release_date": "2025-02-05"},
    {"model_id": "google/gemini-2.5-pro",           "family": "Gemini Pro",     "release_date": "2025-06-17"},
    {"model_id": "google/gemini-2.5-pro-preview",   "family": "Gemini Pro",     "release_date": "2025-06-05"},
    {"model_id": "google/gemini-2.5-flash",         "family": "Gemini Flash",   "release_date": "2025-06-17"},
    {"model_id": "google/gemini-2.5-flash-lite",    "family": "Gemini Flash",   "release_date": "2025-07-22"},
    {"model_id": "google/gemini-3-pro-preview",     "family": "Gemini Pro",     "release_date": "2025-11-18"},
    {"model_id": "google/gemini-3-flash-preview",   "family": "Gemini Flash",   "release_date": "2025-12-17"},
]

# ---------------------------------------------------------------------------
# Prompt templates — keyed by prompt_id
# ---------------------------------------------------------------------------

PROMPTS: dict[str, dict] = {
    "v1": {
        "system": "You are a helpful assistant. Respond with valid JSON only.",
        "user_template": (
            "I want to use the most recent {family} model via OpenRouter API.\n"
            "What model ID should I use? Respond with only:\n"
            '{{\"model\": \"provider/model-name\"}}'
        ),
    },
}

# ---------------------------------------------------------------------------
# Experiment config
# ---------------------------------------------------------------------------

ANSWERER_MODEL_IDS: list[str] = [
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "openai/gpt-5.2",
    "google/gemini-2.5-flash",
    "google/gemini-3-flash-preview",
]

SUBJECT_FAMILIES: list[str] = [
    "Claude Opus",
    "Claude Sonnet",
    "Claude Haiku",
    "GPT",
    "Gemini Pro",
    "Gemini Flash",
]

DEFAULT_PROMPT_ID = "v1"

# ---------------------------------------------------------------------------
# Derived lookups (built from MODELS table)
# ---------------------------------------------------------------------------


def build_model_index(models: list[dict]) -> dict[str, dict]:
    """model_id → {family, release_date}"""
    return {m["model_id"]: m for m in models}


def find_latest_per_family(models: list[dict]) -> dict[str, str]:
    """family → model_id of the most recent model in that family."""
    latest: dict[str, dict] = {}
    for m in models:
        fam = m["family"]
        if fam not in latest or m["release_date"] > latest[fam]["release_date"]:
            latest[fam] = m
    return {fam: m["model_id"] for fam, m in latest.items()}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Evaluation (derived — not stored)
# ---------------------------------------------------------------------------


def evaluate_query(
    query: dict,
    model_index: dict[str, dict],
    latest_per_family: dict[str, str],
) -> dict:
    """Enrich a query row with derived fields for display."""
    family = query["subject_family"]
    expected_id = latest_per_family.get(family)
    expected_date = model_index[expected_id]["release_date"] if expected_id else None

    answered_id = query["answered_model_id"]
    answered_info = model_index.get(answered_id) if answered_id else None
    answered_date = answered_info["release_date"] if answered_info else None

    answerer_info = model_index.get(query["answerer_model_id"])
    answerer_date = answerer_info["release_date"] if answerer_info else None

    if answered_id is None:
        verdict = "parse_failure"
    elif answered_id == expected_id:
        verdict = "exact"
    else:
        verdict = "wrong"

    return {
        **query,
        "answerer_release_date": answerer_date,
        "expected_model_id": expected_id,
        "expected_release_date": expected_date,
        "answered_release_date": answered_date,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------


def query_model(client: OpenAI, answerer_model: str, prompt: dict, family: str) -> str:
    user_content = prompt["user_template"].format(family=family)
    response = client.chat.completions.create(
        model=answerer_model,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def print_table(evaluated: list[dict]) -> None:
    header = (
        f"{'Answerer':<36} | {'Asked about':<14} | "
        f"{'Answered':<40} | {'Expected':<40} | {'Result':<8}"
    )
    print()
    print(header)
    print("-" * len(header))

    for r in evaluated:
        answerer = r["answerer_model_id"]
        a_date = r.get("answerer_release_date") or "?"
        subject = r["subject_family"]
        answered = r["answered_model_id"] or "(parse failure)"
        ans_date = r.get("answered_release_date") or "?"
        expected = r.get("expected_model_id") or "?"
        exp_date = r.get("expected_release_date") or "?"
        verdict = r["verdict"].upper()

        line1 = (
            f"{answerer:<36} | {subject:<14} | "
            f"{answered:<40} | {expected:<40} | {verdict:<8}"
        )
        line2 = (
            f"  ({a_date}){' ' * max(0, 34 - len(str(a_date)) - 4)} | "
            f"{'':14} | "
            f"  ({ans_date}){' ' * max(0, 38 - len(str(ans_date)) - 4)} | "
            f"  ({exp_date}){' ' * max(0, 38 - len(str(exp_date)) - 4)} |"
        )
        print(line1)
        print(line2)

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        raise SystemExit(1)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    prompt_id = DEFAULT_PROMPT_ID
    prompt = PROMPTS[prompt_id]
    model_index = build_model_index(MODELS)
    latest_per_family = find_latest_per_family(MODELS)

    # Collect raw queries
    queries: list[dict] = []
    total = len(ANSWERER_MODEL_IDS) * len(SUBJECT_FAMILIES)
    count = 0

    for answerer_id in ANSWERER_MODEL_IDS:
        for family in SUBJECT_FAMILIES:
            count += 1
            print(f"[{count}/{total}] Asking {answerer_id} about {family}...")

            raw = query_model(client, answerer_id, prompt, family)
            answered_id = extract_model_id(raw)

            query = {
                "answerer_model_id": answerer_id,
                "subject_family": family,
                "prompt_id": prompt_id,
                "answered_model_id": answered_id,
                "raw_response": raw,
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            queries.append(query)

            # Quick feedback
            expected_id = latest_per_family.get(family)
            if answered_id is None:
                print("       → PARSE FAILURE")
            elif answered_id == expected_id:
                print("       → EXACT")
            else:
                info = model_index.get(answered_id)
                date_hint = f", from {info['release_date']}" if info else ""
                print(f"       → WRONG (answered: {answered_id}{date_hint})")

    # Evaluate for display (derived, not saved)
    evaluated = [evaluate_query(q, model_index, latest_per_family) for q in queries]
    print_table(evaluated)

    verdicts = [e["verdict"] for e in evaluated]
    print(
        f"Summary: {verdicts.count('exact')} exact, "
        f"{verdicts.count('wrong')} wrong, "
        f"{verdicts.count('parse_failure')} parse failures "
        f"out of {len(verdicts)} total"
    )

    # Save normalized data
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Models table (overwrite — it's reference data)
    models_path = "results/models.json"
    with open(models_path, "w") as f:
        json.dump(MODELS, f, indent=2)
    print(f"\nModels table saved to {models_path}")

    # Queries table (append-friendly, timestamped)
    queries_path = f"results/queries_{timestamp}.json"
    with open(queries_path, "w") as f:
        json.dump(queries, f, indent=2)
    print(f"Queries saved to {queries_path}")


if __name__ == "__main__":
    main()

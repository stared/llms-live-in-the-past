"""We Live in the Past — Do AI models know what's current?

Tests whether AI models correctly identify the most recent version of model
families when asked for OpenRouter model IDs.
"""

import json
import os
import re
from datetime import datetime

from openai import OpenAI

# ---------------------------------------------------------------------------
# Known models & release dates (for resolving answered model IDs)
# ---------------------------------------------------------------------------

KNOWN_MODELS: dict[str, str] = {
    # Claude
    "anthropic/claude-3-haiku": "2024-03-13",
    "anthropic/claude-3.5-haiku": "2024-11-04",
    "anthropic/claude-3.5-sonnet": "2024-10-22",
    "anthropic/claude-3.7-sonnet": "2025-02-24",
    "anthropic/claude-sonnet-4": "2025-05-22",
    "anthropic/claude-sonnet-4.5": "2025-09-29",
    "anthropic/claude-opus-4": "2025-05-22",
    "anthropic/claude-opus-4.1": "2025-08-05",
    "anthropic/claude-opus-4.5": "2025-11-24",
    "anthropic/claude-opus-4.6": "2026-02-05",
    "anthropic/claude-haiku-4.5": "2025-10-15",
    # GPT
    "openai/gpt-4o": "2024-05-13",
    "openai/gpt-4o-2024-05-13": "2024-05-13",
    "openai/gpt-4o-2024-08-06": "2024-08-06",
    "openai/gpt-4o-2024-11-20": "2024-11-20",
    "openai/gpt-4o-mini": "2024-07-18",
    "openai/gpt-5": "2025-08-07",
    "openai/gpt-5-mini": "2025-08-07",
    "openai/gpt-5-nano": "2025-08-07",
    "openai/gpt-5-pro": "2025-09-26",
    "openai/gpt-5.1": "2025-11-13",
    "openai/gpt-5.2": "2025-12-10",
    "openai/gpt-5.2-pro": "2025-12-10",
    # Gemini
    "google/gemini-2.0-flash-001": "2025-02-05",
    "google/gemini-2.5-pro": "2025-06-17",
    "google/gemini-2.5-pro-preview": "2025-06-05",
    "google/gemini-2.5-flash": "2025-06-17",
    "google/gemini-2.5-flash-lite": "2025-07-22",
    "google/gemini-3-pro-preview": "2025-11-18",
    "google/gemini-3-flash-preview": "2025-12-17",
}

# ---------------------------------------------------------------------------
# Ground truth: subject families
# ---------------------------------------------------------------------------

SUBJECT_FAMILIES: list[dict] = [
    {
        "family_name": "Claude Opus",
        "latest_model_id": "anthropic/claude-opus-4.6",
        "release_date": "2026-02-05",
        "acceptable_answers": [
            "anthropic/claude-opus-4.6",
        ],
    },
    {
        "family_name": "Claude Sonnet",
        "latest_model_id": "anthropic/claude-sonnet-4.5",
        "release_date": "2025-09-29",
        "acceptable_answers": [
            "anthropic/claude-sonnet-4.5",
        ],
    },
    {
        "family_name": "Claude Haiku",
        "latest_model_id": "anthropic/claude-haiku-4.5",
        "release_date": "2025-10-15",
        "acceptable_answers": [
            "anthropic/claude-haiku-4.5",
        ],
    },
    {
        "family_name": "GPT (flagship)",
        "latest_model_id": "openai/gpt-5.2",
        "release_date": "2025-12-10",
        "acceptable_answers": [
            "openai/gpt-5.2",
            "openai/gpt-5.2-pro",
        ],
    },
    {
        "family_name": "Gemini Pro",
        "latest_model_id": "google/gemini-3-pro-preview",
        "release_date": "2025-11-18",
        "acceptable_answers": [
            "google/gemini-3-pro-preview",
        ],
    },
    {
        "family_name": "Gemini Flash",
        "latest_model_id": "google/gemini-3-flash-preview",
        "release_date": "2025-12-17",
        "acceptable_answers": [
            "google/gemini-3-flash-preview",
        ],
    },
]

# ---------------------------------------------------------------------------
# Answerer models
# ---------------------------------------------------------------------------

ANSWERER_MODELS: list[dict] = [
    {
        "model_id": "anthropic/claude-sonnet-4.5",
        "release_date": "2025-09-29",
        "knowledge_cutoff": "2025-04-01",
    },
    {
        "model_id": "openai/gpt-4o",
        "release_date": "2024-05-13",
        "knowledge_cutoff": "2024-10-01",
    },
    {
        "model_id": "google/gemini-2.5-flash",
        "release_date": "2025-06-17",
        "knowledge_cutoff": "2025-01-01",
    },
]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = "You are a helpful assistant. Respond with valid JSON only."

USER_PROMPT_TEMPLATE = (
    "I want to use the most recent {family} model via OpenRouter API.\n"
    "What model ID should I use? Respond with only:\n"
    '{{\"model\": \"provider/model-name\"}}'
)


def build_user_prompt(family_name: str) -> str:
    return USER_PROMPT_TEMPLATE.format(family=family_name)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def extract_model_id(raw: str) -> str | None:
    """Extract model ID from a response that should be JSON like {"model": "..."}."""
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # Try direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "model" in data:
            return data["model"]
    except json.JSONDecodeError:
        pass

    # Fallback: find first JSON object in text
    match = re.search(r'\{[^}]*"model"\s*:\s*"([^"]+)"[^}]*\}', raw)
    if match:
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(answered_id: str | None, subject: dict) -> str:
    """Return 'exact', 'acceptable', 'wrong', or 'parse_failure'."""
    if answered_id is None:
        return "parse_failure"
    if answered_id == subject["latest_model_id"]:
        return "exact"
    if answered_id in subject["acceptable_answers"]:
        return "acceptable"
    return "wrong"


def resolve_release_date(model_id: str | None) -> str | None:
    if model_id is None:
        return None
    return KNOWN_MODELS.get(model_id)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def query_model(client: OpenAI, answerer_model: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=answerer_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_table(results: list[dict]) -> None:
    header = (
        f"{'Answerer':<36} | {'Asked about':<14} | "
        f"{'Answered':<40} | {'Expected':<40} | {'Result':<8}"
    )
    print()
    print(header)
    print("-" * len(header))

    for r in results:
        answerer = r["answerer_model"]
        a_date = r["answerer_release_date"]
        subject = r["subject_family"]
        answered = r["answered_model_id"] or "(parse failure)"
        ans_date = r["answered_release_date"] or "?"
        expected = r["expected_model_id"]
        exp_date = r["expected_release_date"]
        verdict = r["verdict"].upper()

        line1 = (
            f"{answerer:<36} | {subject:<14} | "
            f"{answered:<40} | {expected:<40} | {verdict:<8}"
        )
        line2 = (
            f"  ({a_date}){' ' * (34 - len(a_date) - 4)} | "
            f"{'':14} | "
            f"  ({ans_date}){' ' * (38 - len(str(ans_date)) - 4)} | "
            f"  ({exp_date}){' ' * (38 - len(exp_date) - 4)} |"
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

    results: list[dict] = []
    total = len(ANSWERER_MODELS) * len(SUBJECT_FAMILIES)
    count = 0

    for answerer in ANSWERER_MODELS:
        for subject in SUBJECT_FAMILIES:
            count += 1
            print(
                f"[{count}/{total}] Asking {answerer['model_id']} "
                f"about {subject['family_name']}..."
            )

            prompt = build_user_prompt(subject["family_name"])
            raw = query_model(client, answerer["model_id"], prompt)
            answered_id = extract_model_id(raw)
            verdict = evaluate(answered_id, subject)

            result = {
                "answerer_model": answerer["model_id"],
                "answerer_release_date": answerer["release_date"],
                "answerer_knowledge_cutoff": answerer.get("knowledge_cutoff"),
                "subject_family": subject["family_name"],
                "expected_model_id": subject["latest_model_id"],
                "expected_release_date": subject["release_date"],
                "answered_model_id": answered_id,
                "answered_release_date": resolve_release_date(answered_id),
                "raw_response": raw,
                "verdict": verdict,
            }
            results.append(result)

            label = verdict.upper()
            if verdict == "wrong" and answered_id:
                known_date = resolve_release_date(answered_id)
                label += f" (answered: {answered_id}"
                if known_date:
                    label += f", from {known_date}"
                label += ")"
            print(f"       → {label}")

    # Console table
    print_table(results)

    # Summary
    verdicts = [r["verdict"] for r in results]
    print(
        f"Summary: {verdicts.count('exact')} exact, "
        f"{verdicts.count('acceptable')} acceptable, "
        f"{verdicts.count('wrong')} wrong, "
        f"{verdicts.count('parse_failure')} parse failures "
        f"out of {len(verdicts)} total"
    )

    # Save JSON
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"results/results_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()

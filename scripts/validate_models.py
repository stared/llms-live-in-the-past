"""Check which answerer model IDs are actually available on OpenRouter.

Sends a minimal 1-token request to each model. Reports valid/invalid/error.
Usage: OPENROUTER_API_KEY=... uv run scripts/validate_models.py
"""
import asyncio
import json
import os

from openai import AsyncOpenAI

CONFIG_DIR = "config"
MAX_CONCURRENT = 5


async def check_model(client: AsyncOpenAI, sem: asyncio.Semaphore, model_id: str) -> tuple[str, str, str]:
    """Returns (model_id, status, detail)."""
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "Say hi"}],
                max_tokens=1,
            )
            return (model_id, "ok", resp.choices[0].message.content or "")
        except Exception as e:
            err = str(e)
            if "404" in err:
                return (model_id, "NOT_FOUND", err[:120])
            elif "400" in err and "not a valid" in err:
                return (model_id, "INVALID", err[:120])
            elif "402" in err:
                return (model_id, "NO_CREDITS", err[:120])
            else:
                return (model_id, "ERROR", err[:120])


async def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        raise SystemExit(1)

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    experiment = json.load(open(f"{CONFIG_DIR}/experiment.json"))
    model_ids = experiment["answerer_model_ids"]

    print(f"Checking {len(model_ids)} models on OpenRouter...\n")

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [check_model(client, sem, mid) for mid in model_ids]
    results = await asyncio.gather(*tasks)

    ok = [(m, d) for m, s, d in results if s == "ok"]
    bad = [(m, s, d) for m, s, d in results if s != "ok"]

    print(f"✓ Available: {len(ok)}")
    for m, _ in ok:
        print(f"  {m}")

    if bad:
        print(f"\n✗ Unavailable: {len(bad)}")
        for m, s, d in bad:
            print(f"  {m} [{s}]: {d}")

    # Suggest updated list
    if bad:
        valid_ids = [m for m, _ in ok]
        print(f"\n--- Suggested answerer_model_ids ({len(valid_ids)} models) ---")
        print(json.dumps(valid_ids, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

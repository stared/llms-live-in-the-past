/**
 * Deterministic mapping from native API model IDs (as returned by v2 prompt)
 * to OpenRouter-style model IDs used in models.json.
 *
 * If an answered ID is not here, it's used as-is for lookup.
 */
export const MODEL_ALIASES: Record<string, string> = {
  // Claude
  "claude-opus-4-5": "anthropic/claude-opus-4.5",
  "claude-opus-4-1-20250805": "anthropic/claude-opus-4.1",
  "claude-3-opus-20240229": "anthropic/claude-3-opus",
  "claude-sonnet-4-5": "anthropic/claude-sonnet-4.5",
  "claude-sonnet-4-20250514": "anthropic/claude-sonnet-4",
  "claude-3-5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
  "claude-3-7-sonnet-20250219": "anthropic/claude-3.7-sonnet",
  "claude-haiku-4-5": "anthropic/claude-haiku-4.5",
  "claude-3-5-haiku-20241022": "anthropic/claude-3.5-haiku",
  "claude-3-5-haiku-latest": "anthropic/claude-3.5-haiku",
  // GPT
  "gpt-4o": "openai/gpt-4o",
  "gpt-4.1": "openai/gpt-4.1",
  // Gemini
  "gemini-2.0-flash": "google/gemini-2.0-flash-001",
  "gemini-2.5-pro": "google/gemini-2.5-pro",
  "gemini-2.5-pro-preview-06-05": "google/gemini-2.5-pro",
  "gemini-2.5-flash": "google/gemini-2.5-flash",
  "gemini-2.5-flash-preview-04-17": "google/gemini-2.5-flash",
  // These map to models NOT in models.json (too old to be tracked)
  "gemini-1.5-pro": "google/gemini-1.5-pro",
  "gemini-1.5-pro-002": "google/gemini-1.5-pro",
  "gemini-1.5-flash": "google/gemini-1.5-flash",
  "gemini-1.5-flash-002": "google/gemini-1.5-flash",
};

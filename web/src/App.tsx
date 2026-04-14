import { useEffect, useState } from "react";
import type { Model, Query, EvaluatedQuery } from "./types";
import { buildModelIndex, findLatestPerFamily, evaluateQuery } from "./evaluate";
import { MODEL_ALIASES } from "./model-aliases";

const FAMILY_ORDER = [
  "Claude Opus",
  "Claude Sonnet",
  "Claude Haiku",
  "GPT",
  "Gemini Pro",
  "Gemini Flash",
  "GLM",
  "Qwen",
  "Grok",
  "Kimi",
  "MiMo",
];

const LATEST_QUERY_FILE = "queries_20260411_211727.json";

function shortName(id: string): string {
  return id
    .replace(
      /^(anthropic|openai|google|z-ai|qwen|x-ai|moonshotai|xiaomi)\//,
      ""
    )
    .replace(/-preview$/, "");
}

/** Extract a compact version label for display under dots. */
function dotLabel(modelId: string): string {
  const s = shortName(modelId);

  // GPT with date stamp: "gpt-4o-2024-08-06" → "4o·08"
  let m = s.match(/^gpt-([\d.]+[a-z]?)-\d{4}-(\d{2})-\d{2}$/);
  if (m) return `${m[1]}·${m[2]}`;

  // Claude: "claude-opus-4.5" → "4.5", "claude-3.5-sonnet" → "3.5"
  m =
    s.match(/^claude-(?:opus|sonnet|haiku)-([\d.]+)/) ||
    s.match(/^claude-([\d.]+)/);
  if (m) return m[1];

  // GPT: "gpt-5.4" → "5.4", "gpt-4o" → "4o"
  m = s.match(/^gpt-([\d.]+[a-z]?)(?:-chat)?$/);
  if (m) return m[1];

  // Gemini: "gemini-2.5-pro" → "2.5"
  m = s.match(/^gemini-([\d.]+)/);
  if (m) return m[1];

  // GLM: "glm-5.1" → "5.1"
  m = s.match(/^glm-([\d.]+)/);
  if (m) return m[1];

  // Qwen: "qwen3.6-plus:free" → "3.6"
  m = s.match(/^qwen([\d.]+)/);
  if (m) return m[1];

  // Grok: "grok-4.20" → "4.20"
  m = s.match(/^grok-([\d.]+)/);
  if (m) return m[1];

  // Kimi: "kimi-k2.5" → "k2.5"
  m = s.match(/^kimi-(k[\d.]+)/);
  if (m) return m[1];

  // MiMo: "mimo-v2-flash" → "v2·f"
  m = s.match(/^mimo-(v[\d.]+)-(\w)/);
  if (m) return `${m[1]}·${m[2]}`;

  return s;
}

function App() {
  const [models, setModels] = useState<Model[]>([]);
  const [queries, setQueries] = useState<EvaluatedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredModel, setHoveredModel] = useState<string | null>(null);
  const [pinnedModel, setPinnedModel] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [modelsRes, queriesRes] = await Promise.all([
          fetch("/data/models.json"),
          fetch(`/data/${LATEST_QUERY_FILE}`),
        ]);
        const modelsData: Model[] = await modelsRes.json();
        const rawQueries: Query[] = await queriesRes.json();

        const modelIndex = buildModelIndex(modelsData);
        const latestPerFamily = findLatestPerFamily(modelsData);

        const evaluated = rawQueries.map((q) => {
          const resolvedId = q.answered_model_id
            ? (MODEL_ALIASES[q.answered_model_id] ?? q.answered_model_id)
            : null;
          return evaluateQuery(
            { ...q, answered_model_id: resolvedId },
            modelIndex,
            latestPerFamily
          );
        });

        setModels(modelsData);
        setQueries(evaluated);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="center">Loading...</div>;
  if (error) return <div className="center error">{error}</div>;
  if (!queries.length) return <div className="center">No data found.</div>;

  const activeModel = pinnedModel ?? hoveredModel;

  // Families present in query data
  const familiesInData = [...new Set(queries.map((q) => q.subject_family))];
  const families = FAMILY_ORDER.filter((f) => familiesInData.includes(f));

  // Which models are answerers (have query data)
  const answererSet = new Set(queries.map((q) => q.answerer_model_id));

  // Models grouped by family, sorted by date
  const modelsByFamily = new Map<string, Model[]>();
  for (const fam of families) {
    modelsByFamily.set(
      fam,
      models
        .filter((m) => m.family === fam)
        .sort((a, b) => a.release_date.localeCompare(b.release_date))
    );
  }

  // Latest per family
  const latestPerFamily = new Map<string, string>();
  for (const [fam, fModels] of modelsByFamily) {
    if (fModels.length) {
      latestPerFamily.set(fam, fModels[fModels.length - 1].model_id);
    }
  }

  // Global date range across all displayed families
  const allDates = models
    .filter((m) => families.includes(m.family))
    .map((m) => new Date(m.release_date).getTime());
  const minDate = Math.min(...allDates);
  const maxDate = Math.max(...allDates);
  const dateRange = maxDate - minDate || 1;

  // Answer lookup: answerer → family → query
  const answerLookup = new Map<string, Map<string, EvaluatedQuery>>();
  for (const q of queries) {
    if (!answerLookup.has(q.answerer_model_id)) {
      answerLookup.set(q.answerer_model_id, new Map());
    }
    answerLookup.get(q.answerer_model_id)!.set(q.subject_family, q);
  }

  const PAD = 3;
  function dateToPercent(dateStr: string): number {
    const t = new Date(dateStr).getTime();
    return PAD + ((t - minDate) / dateRange) * (100 - 2 * PAD);
  }

  // Year ticks for time axis
  const minYear = new Date(minDate).getFullYear();
  const maxYear = new Date(maxDate).getFullYear();
  const yearTicks: { year: number; pct: number }[] = [];
  for (let y = minYear; y <= maxYear + 1; y++) {
    const t = new Date(`${y}-01-01`).getTime();
    if (t >= minDate && t <= maxDate) {
      yearTicks.push({ year: y, pct: dateToPercent(`${y}-01-01`) });
    }
  }

  // Default state: each family's latest model's self-assessment (one red dot max)
  const selfClaims = new Map<string, string>();
  for (const [fam, latestId] of latestPerFamily) {
    if (answererSet.has(latestId)) {
      const q = answerLookup.get(latestId)?.get(fam);
      if (q?.answered_model_id && q.answered_model_id !== latestId) {
        selfClaims.set(fam, q.answered_model_id);
      }
    }
  }

  // Hover state: what does the active model claim is newest?
  const hoveredClaims = new Map<string, string>();
  const isAnswererActive = activeModel && answererSet.has(activeModel);
  if (isAnswererActive) {
    const answers = answerLookup.get(activeModel!);
    if (answers) {
      for (const [fam, q] of answers) {
        if (q.answered_model_id) hoveredClaims.set(fam, q.answered_model_id);
      }
    }
  }
  const headerSub = isAnswererActive
    ? `According to ${shortName(activeModel!)}, these are the newest models`
    : "Hover a model to see what it thinks is newest in each family";

  return (
    <div className="container">
      <header>
        <h1>AI models live in the past</h1>
        <p className="sub">{headerSub}</p>
      </header>

      <div className="timelines">
        {/* Continuous vertical year guides spanning all rows */}
        <div className="guides-overlay">
          {yearTicks.map(({ year, pct }) => (
            <div
              key={year}
              className="guide-line"
              style={{ left: `${pct}%` }}
            />
          ))}
        </div>

        {/* Time axis header */}
        <div className="tl-header">
          <div className="tl-label" />
          <div className="tl-track">
            {yearTicks.map(({ year, pct }) => (
              <span
                key={year}
                className="year-label"
                style={{ left: `${pct}%` }}
              >
                {year}
              </span>
            ))}
          </div>
        </div>

        {families.map((fam) => {
          const fModels = modelsByFamily.get(fam) || [];
          const latestId = latestPerFamily.get(fam);
          const hoveredClaimId = hoveredClaims.get(fam);

          return (
            <div key={fam} className="tl-row">
              <div className="tl-label">{fam}</div>
              <div className="tl-track">
                <div className="tl-axis" />

                {/* Model dots */}
                {fModels.map((m) => {
                  const pct = dateToPercent(m.release_date);
                  const isAnswerer = answererSet.has(m.model_id);

                  let dotState: "teal" | "red" | "hollow";
                  if (activeModel) {
                    if (m.model_id === activeModel) dotState = "teal";
                    else if (hoveredClaimId === m.model_id && m.model_id !== latestId) dotState = "red";
                    else dotState = "hollow";
                  } else {
                    if (m.model_id === latestId) dotState = "teal";
                    else if (selfClaims.get(fam) === m.model_id) dotState = "red";
                    else dotState = "hollow";
                  }

                  const classes = [
                    "dot",
                    dotState,
                    isAnswerer && "answerer",
                  ]
                    .filter(Boolean)
                    .join(" ");

                  return (
                    <div
                      key={m.model_id}
                      className={classes}
                      style={{ left: `${pct}%` }}
                      title={`${shortName(m.model_id)}\n${m.release_date}`}
                      onMouseEnter={() => setHoveredModel(m.model_id)}
                      onMouseLeave={() => setHoveredModel(null)}
                      onClick={() =>
                        isAnswerer &&
                        setPinnedModel(
                          pinnedModel === m.model_id ? null : m.model_id
                        )
                      }
                    >
                      <span className="dot-num">{dotLabel(m.model_id)}</span>
                    </div>
                  );
                })}

                {/* Unmatched claim: answered model not in models.json */}
                {hoveredClaimId &&
                  !fModels.some((m) => m.model_id === hoveredClaimId) && (
                    <span className="unmatched">
                      ? {shortName(hoveredClaimId)}
                    </span>
                  )}
              </div>
            </div>
          );
        })}
      </div>

      <footer className="pf">
        <a href="https://github.com/QuesmaOrg/quesma">Quesma</a>
      </footer>
    </div>
  );
}

export default App;

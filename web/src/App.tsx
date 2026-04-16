import { type ReactNode, useEffect, useState } from "react";
import type { Model, Query, EvaluatedQuery } from "./types";
import { buildModelIndex, findLatestPerFamily, evaluateQuery } from "./evaluate";
import { MODEL_ALIASES } from "./model-aliases";

const FAMILY_ORDER = [
  "Claude Opus",
  "Claude Sonnet",
  "Claude Haiku",
  "GPT",
  "GPT Codex",
  "Gemini Pro",
  "Gemini Flash",
  "GLM",
  "Qwen",
  "Grok",
  "Kimi",
  "MiMo",
];

const LATEST_QUERY_FILE = "queries_20260416_124134.json";

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

  // GPT: "gpt-5.4" → "5.4", "gpt-4o" → "4o", "gpt-5.3-codex" → "5.3"
  m = s.match(/^gpt-([\d.]+[a-z]?)(?:-chat|-codex)?$/);
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
        if (!modelsRes.ok) throw new Error(`Failed to load models.json: ${modelsRes.status}`);
        if (!queriesRes.ok) throw new Error(`Failed to load ${LATEST_QUERY_FILE}: ${queriesRes.status}`);
        const modelsData: Model[] = await modelsRes.json();
        const rawQueries: Query[] = await queriesRes.json();

        const modelIndex = buildModelIndex(modelsData);
        const latestPerFamily = findLatestPerFamily(modelsData);

        const evaluated = rawQueries.map((q) => {
          let resolvedId = q.answered_model_id;
          if (resolvedId) {
            if (MODEL_ALIASES[resolvedId]) {
              resolvedId = MODEL_ALIASES[resolvedId];
            } else if (!modelIndex.has(resolvedId)) {
              console.warn(`No alias for "${resolvedId}" (answerer: ${q.answerer_model_id}, family: ${q.subject_family})`);
            }
          }
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

  // All families that have models in models.json
  const familiesInModels = new Set(models.map((m) => m.family));
  const families = FAMILY_ORDER.filter((f) => familiesInModels.has(f));

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

  // Model index for date lookups
  const modelIndex = new Map(models.map((m) => [m.model_id, m]));

  // Default state: each family's newest model's self-assessment
  const selfClaims = new Map<string, string>();
  for (const [fam, latestId] of latestPerFamily) {
    if (answererSet.has(latestId)) {
      const q = answerLookup.get(latestId)?.get(fam);
      if (q?.answered_model_id) selfClaims.set(fam, q.answered_model_id);
    }
  }

  // Average age of claimed models relative to the answerer's release date
  function monthsBetween(from: string, to: string): number {
    return Math.round((new Date(to).getTime() - new Date(from).getTime()) / (1000 * 60 * 60 * 24 * 30.44));
  }

  const claimAges: number[] = [];
  for (const [fam, claimedId] of selfClaims) {
    const claimInfo = modelIndex.get(claimedId);
    const latestId = latestPerFamily.get(fam);
    const latestInfo = latestId ? modelIndex.get(latestId) : undefined;
    if (claimInfo && latestInfo) {
      claimAges.push(monthsBetween(claimInfo.release_date, latestInfo.release_date));
    }
  }
  const avgMonths = claimAges.length
    ? Math.round(claimAges.reduce((a, b) => a + b, 0) / claimAges.length)
    : 0;

  // Hover state: what does the active model claim is newest?
  const activeClaims = new Map<string, string>();
  const isAnswererActive = activeModel && answererSet.has(activeModel);
  if (isAnswererActive) {
    const answers = answerLookup.get(activeModel!);
    if (answers) {
      for (const [fam, q] of answers) {
        if (q.answered_model_id) activeClaims.set(fam, q.answered_model_id);
      }
    }
  }

  // Per family, the latest model released on or before the active model's release date
  // (i.e., the best answer the active model could have given given its knowledge window)
  const correctPerFamily = new Map<string, string>();
  const activeInfoForCorrect = activeModel ? modelIndex.get(activeModel) : undefined;
  const cutoff = activeInfoForCorrect?.release_date;
  if (cutoff) {
    for (const [fam, fModels] of modelsByFamily) {
      let best: Model | undefined;
      for (const m of fModels) {
        if (m.release_date <= cutoff && (!best || m.release_date > best.release_date)) {
          best = m;
        }
      }
      if (best) correctPerFamily.set(fam, best.model_id);
    }
  }
  let headerMain: ReactNode;
  if (!activeModel) {
    headerMain = (
      <>
        According to the <span className="c-teal">newest model</span> in each family, the{" "}
        <span className="c-red">most recent model</span> was already{" "}
        <span className="c-red">{avgMonths} months</span> old when it was released.
      </>
    );
  } else if (isAnswererActive) {
    const activeInfo = modelIndex.get(activeModel!);
    const activeFam = activeInfo?.family;
    const ownClaim = activeFam ? activeClaims.get(activeFam) : undefined;
    const claimInfo = ownClaim ? modelIndex.get(ownClaim) : undefined;

    if (ownClaim && claimInfo && activeInfo) {
      const age = monthsBetween(claimInfo.release_date, activeInfo.release_date);
      const correctId = activeFam ? correctPerFamily.get(activeFam) : undefined;
      const isCorrect = ownClaim === correctId;
      const claimColor = isCorrect ? "c-teal" : "c-red";
      headerMain = isCorrect ? (
        <>
          According to <span className="c-teal">{shortName(activeModel!)}</span>, the newest{" "}
          {activeFam} is <span className={claimColor}>{shortName(ownClaim)}</span> — correct.
        </>
      ) : (
        <>
          According to <span className="c-teal">{shortName(activeModel!)}</span>, the newest{" "}
          {activeFam} is <span className={claimColor}>{shortName(ownClaim)}</span>, which was already{" "}
          <span className="c-red">{age} months</span> old when it was released.
        </>
      );
    } else if (ownClaim) {
      headerMain = (
        <>
          <span className="c-teal">{shortName(activeModel!)}</span> can't correctly identify the newest{" "}
          {activeFam}, saying <span className="c-red">{shortName(ownClaim)}</span>.
        </>
      );
    } else {
      headerMain = (
        <>
          <span className="c-teal">{shortName(activeModel!)}</span> — no query data.
        </>
      );
    }
  } else {
    headerMain = (
      <>
        <span className="c-teal">{shortName(activeModel!)}</span> — no query data.
      </>
    );
  }
  const headerSub = "Hover a model to see what it thinks is newest in each family";

  return (
    <div className="container">
      <header>
        <h1>AI models live in the past</h1>
        <div className="header-block">
          <p className="summary">{headerMain}</p>
          <p className="sub">{headerSub}</p>
        </div>
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
          const claimId = activeModel ? activeClaims.get(fam) : selfClaims.get(fam);

          return (
            <div key={fam} className="tl-row">
              <div className="tl-label">{fam}</div>
              <div className="tl-track">
                <div className="tl-axis" />

                {/* Model dots */}
                {fModels.map((m) => {
                  const pct = dateToPercent(m.release_date);
                  const hasData = answererSet.has(m.model_id);

                  const latestId = latestPerFamily.get(fam);
                  const correctId = correctPerFamily.get(fam);
                  let dotState: "teal" | "teal-fill" | "red" | "hollow";
                  if (activeModel) {
                    if (m.model_id === activeModel) dotState = "teal";
                    else if (claimId === m.model_id)
                      dotState = m.model_id === correctId ? "teal-fill" : "red";
                    else dotState = "hollow";
                  } else {
                    if (m.model_id === latestId) dotState = "teal";
                    else if (claimId === m.model_id) dotState = "red";
                    else dotState = "hollow";
                  }

                  const classes = [
                    "dot",
                    dotState,
                    hasData && "has-data",
                  ]
                    .filter(Boolean)
                    .join(" ");

                  return (
                    <div
                      key={m.model_id}
                      className={classes}
                      style={{ left: `${pct}%` }}
                      title={`${shortName(m.model_id)}\n${m.release_date}`}
                      onMouseEnter={() => hasData && setHoveredModel(m.model_id)}
                      onMouseLeave={() => hasData && setHoveredModel(null)}
                      onClick={() =>
                        hasData &&
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
                {claimId &&
                  !fModels.some((m) => m.model_id === claimId) && (
                    <span className="unmatched">
                      ? {shortName(claimId)}
                    </span>
                  )}
              </div>
            </div>
          );
        })}
      </div>

      <section className="prompt-box">
        <div className="prompt-label">Exact prompt used (temperature 0)</div>
        <p className="prompt-text">
          <span className="prompt-role">system:</span>
          <br />
          You are a helpful assistant. Respond with valid JSON only.
        </p>
        <p className="prompt-text">
          <span className="prompt-role">user:</span>
          <br />
          What is the most recent <span className="prompt-var">{"{family}"}</span> model? Give me the exact model number as used in the official API.
          <br />
          Respond with only:
          <br />
          {"{\"model\": \"[model name]\"}"}
        </p>
      </section>

      <footer className="pf">
        <a href="https://github.com/QuesmaOrg/quesma">Quesma</a>
      </footer>
    </div>
  );
}

export default App;

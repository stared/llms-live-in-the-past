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

const ANSWERER_COLORS = [
  "#7cb9e8",
  "#f4a460",
  "#90ee90",
  "#dda0dd",
  "#ff6b6b",
  "#87ceeb",
  "#ffd700",
  "#98fb98",
  "#ff69b4",
  "#c4a7e7",
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

function App() {
  const [models, setModels] = useState<Model[]>([]);
  const [queries, setQueries] = useState<EvaluatedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredAnswerer, setHoveredAnswerer] = useState<string | null>(null);
  const [pinnedAnswerer, setPinnedAnswerer] = useState<string | null>(null);

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

  const activeAnswerer = pinnedAnswerer ?? hoveredAnswerer;

  const familiesInData = [...new Set(queries.map((q) => q.subject_family))];
  const families = FAMILY_ORDER.filter((f) => familiesInData.includes(f));
  const answerers = [...new Set(queries.map((q) => q.answerer_model_id))];

  // Models grouped by family
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

  // Global date range
  const allDates = models
    .filter((m) => families.includes(m.family))
    .map((m) => new Date(m.release_date).getTime());
  const minDate = Math.min(...allDates);
  const maxDate = Math.max(...allDates);
  const dateRange = maxDate - minDate || 1;

  // Lookup: answerer → family → query
  const answerLookup = new Map<string, Map<string, EvaluatedQuery>>();
  for (const q of queries) {
    if (!answerLookup.has(q.answerer_model_id)) {
      answerLookup.set(q.answerer_model_id, new Map());
    }
    answerLookup.get(q.answerer_model_id)!.set(q.subject_family, q);
  }

  function dateToPercent(dateStr: string): number {
    const t = new Date(dateStr).getTime();
    return 2 + ((t - minDate) / dateRange) * 96;
  }

  const headerSub = activeAnswerer
    ? `According to ${shortName(activeAnswerer)}, these are the newest models`
    : "Each AI was asked: what is the most recent model in each family?";

  return (
    <div className="container">
      <header>
        <h1>We Live in the Past</h1>
        <p className="sub">{headerSub}</p>
      </header>

      <div className="answerers">
        {answerers.map((ans, i) => {
          const color = ANSWERER_COLORS[i % ANSWERER_COLORS.length];
          return (
            <button
              key={ans}
              className={`chip ${activeAnswerer === ans ? "active" : ""}`}
              onMouseEnter={() => setHoveredAnswerer(ans)}
              onMouseLeave={() => setHoveredAnswerer(null)}
              onClick={() =>
                setPinnedAnswerer(pinnedAnswerer === ans ? null : ans)
              }
              style={{ "--c": color } as React.CSSProperties}
            >
              <span className="chip-dot" />
              {shortName(ans)}
            </button>
          );
        })}
      </div>

      <div className="timelines">
        {families.map((fam) => {
          const fModels = modelsByFamily.get(fam) || [];
          const latestId = latestPerFamily.get(fam);

          return (
            <div key={fam} className="tl-row">
              <div className="tl-label">{fam}</div>
              <div className="tl-track">
                <div className="tl-line" />

                {fModels.map((m) => {
                  const pct = dateToPercent(m.release_date);
                  const isLatest = m.model_id === latestId;

                  const pickedByIndices: number[] = [];
                  answerers.forEach((ans, i) => {
                    const q = answerLookup.get(ans)?.get(fam);
                    if (q?.answered_model_id === m.model_id) {
                      pickedByIndices.push(i);
                    }
                  });

                  const isActivePick =
                    activeAnswerer !== null &&
                    pickedByIndices.includes(answerers.indexOf(activeAnswerer));

                  const activeColor = activeAnswerer
                    ? ANSWERER_COLORS[
                        answerers.indexOf(activeAnswerer) %
                          ANSWERER_COLORS.length
                      ]
                    : undefined;

                  return (
                    <div
                      key={m.model_id}
                      className={[
                        "dot",
                        isLatest && "latest",
                        isActivePick && "picked",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      style={{
                        left: `${pct}%`,
                        ...(isActivePick
                          ? ({
                              "--pick-color": activeColor,
                            } as React.CSSProperties)
                          : {}),
                      }}
                      title={`${shortName(m.model_id)}\n${m.release_date}`}
                    >
                      {isActivePick && (
                        <span
                          className="dot-label"
                          style={{ color: activeColor }}
                        >
                          {shortName(m.model_id)}
                        </span>
                      )}

                      {!activeAnswerer &&
                        pickedByIndices.map((idx) => (
                          <span
                            key={idx}
                            className="tick"
                            style={{
                              background:
                                ANSWERER_COLORS[idx % ANSWERER_COLORS.length],
                            }}
                          />
                        ))}
                    </div>
                  );
                })}

                {activeAnswerer &&
                  (() => {
                    const q = answerLookup.get(activeAnswerer)?.get(fam);
                    if (!q || !q.answered_model_id) return null;
                    const matched = fModels.some(
                      (m) => m.model_id === q.answered_model_id
                    );
                    if (matched) return null;
                    const color =
                      ANSWERER_COLORS[
                        answerers.indexOf(activeAnswerer) %
                          ANSWERER_COLORS.length
                      ];
                    return (
                      <span className="unmatched" style={{ color }}>
                        ? {shortName(q.answered_model_id!)}
                      </span>
                    );
                  })()}
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

import { useEffect, useState } from "react";
import type { Model, Query, EvaluatedQuery } from "./types";
import { buildModelIndex, findLatestPerFamily, evaluateQuery } from "./evaluate";

const FAMILY_ORDER = [
  "Claude Opus",
  "Claude Sonnet",
  "Claude Haiku",
  "GPT",
  "Gemini Pro",
  "Gemini Flash",
];

const QUERY_FILES = [
  "queries_20260411_211727.json",
  "queries_20260208_224943.json",
  "queries_20260207_170946.json",
  "queries_20260207_170850.json",
];

function shortName(id: string): string {
  return id.replace(/^(anthropic|openai|google)\//, "").replace(/-preview$/, "");
}

function monthsDehind(answered: string | null, expected: string | null): number | null {
  if (!answered || !expected) return null;
  const ms = new Date(expected).getTime() - new Date(answered).getTime();
  return Math.round((ms / (1000 * 60 * 60 * 24 * 30.44)) * 10) / 10;
}

function lagText(m: number | null): string {
  if (m === null) return "";
  if (m <= 0) return "current";
  return m < 1 ? "<1 mo" : `${Math.round(m)} mo`;
}

function App() {
  const [experiments, setExperiments] = useState<
    { file: string; date: string; queries: EvaluatedQuery[] }[]
  >([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const modelsRes = await fetch("/data/models.json");
        const models: Model[] = await modelsRes.json();
        const modelIndex = buildModelIndex(models);
        const latestPerFamily = findLatestPerFamily(models);

        const exps: { file: string; date: string; queries: EvaluatedQuery[] }[] = [];

        for (const file of QUERY_FILES) {
          try {
            const res = await fetch(`/data/${file}`);
            if (!res.ok) continue;
            const rawQueries: Query[] = await res.json();

            // Deduplicate within this file
            const seen = new Set<string>();
            const deduped: Query[] = [];
            for (const q of rawQueries) {
              const key = `${q.answerer_model_id}::${q.subject_family}`;
              if (!seen.has(key)) {
                seen.add(key);
                deduped.push(q);
              }
            }

            const evaluated = deduped.map((q) =>
              evaluateQuery(q, modelIndex, latestPerFamily)
            );

            const dateMatch = file.match(/(\d{8})/);
            const dateStr = dateMatch
              ? `${dateMatch[1].slice(0, 4)}-${dateMatch[1].slice(4, 6)}-${dateMatch[1].slice(6, 8)}`
              : "";

            exps.push({ file, date: dateStr, queries: evaluated });
          } catch {
            /* skip */
          }
        }

        setExperiments(exps);
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
  if (!experiments.length) return <div className="center">No data found.</div>;

  const exp = experiments[activeIdx];
  const evaluated = exp.queries;

  const answerers = [...new Set(evaluated.map((e) => e.answerer_model_id))];
  const families = [...new Set(evaluated.map((e) => e.subject_family))];
  families.sort(
    (a, b) => (FAMILY_ORDER.indexOf(a) ?? 99) - (FAMILY_ORDER.indexOf(b) ?? 99)
  );

  const lookup = new Map<string, EvaluatedQuery>();
  for (const e of evaluated) {
    lookup.set(`${e.answerer_model_id}::${e.subject_family}`, e);
  }

  // Stats
  const exact = evaluated.filter((e) => e.verdict === "exact").length;

  // Max lag for color scaling
  let maxLag = 1;
  for (const e of evaluated) {
    const lag = monthsDehind(e.answered_release_date, e.expected_release_date);
    if (lag !== null && lag > maxLag) maxLag = lag;
  }

  return (
    <div className="container">
      <header>
        <h1>We Live in the Past</h1>
        <p className="sub">
          Each AI was asked: "What is the most recent model in this family?"
        </p>
        <div className="meta">
          <span>
            {exact}/{evaluated.length} correct
          </span>
          {experiments.length > 1 && (
            <span className="run-picker">
              {experiments.map((ex, i) => (
                <button
                  key={ex.file}
                  className={i === activeIdx ? "active" : ""}
                  onClick={() => setActiveIdx(i)}
                >
                  {ex.date}
                </button>
              ))}
            </span>
          )}
        </div>
      </header>

      <table>
        <thead>
          <tr>
            <th className="corner" />
            {families.map((f) => (
              <th key={f}>{f}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {answerers.map((ans) => {
            const sample = lookup.get(`${ans}::${families[0]}`);
            return (
              <tr key={ans}>
                <td className="rh">
                  <span className="rh-name">{shortName(ans)}</span>
                  <span className="rh-date">{sample?.answerer_release_date ?? ""}</span>
                </td>
                {families.map((fam) => {
                  const e = lookup.get(`${ans}::${fam}`);
                  if (!e) return <td key={fam} className="c" />;

                  const lag =
                    e.verdict === "exact"
                      ? 0
                      : monthsDehind(e.answered_release_date, e.expected_release_date);
                  const unknown = e.verdict === "wrong" && !e.answered_release_date;
                  const intensity =
                    e.verdict === "exact"
                      ? 0
                      : lag !== null
                        ? Math.min(lag / maxLag, 1)
                        : 0.7;

                  const bg =
                    e.verdict === "exact"
                      ? "rgba(46,204,113,0.12)"
                      : `rgba(231,76,60,${0.06 + intensity * 0.18})`;

                  return (
                    <td
                      key={fam}
                      className={`c ${e.verdict}`}
                      style={{ background: bg }}
                      title={[
                        `Expected: ${e.expected_model_id ? shortName(e.expected_model_id) : "?"}`,
                        `Answered: ${e.answered_model_id ?? "(parse failure)"}`,
                        e.expected_release_date && `Expected: ${e.expected_release_date}`,
                        e.answered_release_date && `Answered: ${e.answered_release_date}`,
                        lag !== null && `Behind: ${lagText(lag)}`,
                      ]
                        .filter(Boolean)
                        .join("\n")}
                    >
                      <span className="c-model">
                        {e.answered_model_id
                          ? shortName(e.answered_model_id)
                          : "parse failure"}
                      </span>
                      <span className="c-lag">
                        {e.verdict === "exact"
                          ? "\u2713"
                          : lagText(lag)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td className="rh ft-label">Latest</td>
            {families.map((fam) => {
              const e = evaluated.find((e) => e.subject_family === fam);
              return (
                <td key={fam} className="c ft">
                  <span className="c-model">
                    {e?.expected_model_id ? shortName(e.expected_model_id) : "?"}
                  </span>
                  <span className="c-lag">{e?.expected_release_date ?? ""}</span>
                </td>
              );
            })}
          </tr>
        </tfoot>
      </table>

      <footer className="pf">
        <a href="https://github.com/QuesmaOrg/quesma">Quesma</a>
      </footer>
    </div>
  );
}

export default App;

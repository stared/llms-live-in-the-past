import { useEffect, useState } from "react";
import type { Model, Query, EvaluatedQuery } from "./types";
import { buildModelIndex, findLatestPerFamily, evaluateQuery } from "./evaluate";

function shortModelName(modelId: string): string {
  return modelId.replace(/^(anthropic|openai|google)\//, "");
}

function App() {
  const [evaluated, setEvaluated] = useState<EvaluatedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [modelsRes, q1Res, q2Res] = await Promise.all([
          fetch("/data/models.json"),
          fetch("/data/queries_20260207_170850.json"),
          fetch("/data/queries_20260207_170946.json"),
        ]);
        const models: Model[] = await modelsRes.json();
        const queries1: Query[] = await q1Res.json();
        const queries2: Query[] = await q2Res.json();

        const modelIndex = buildModelIndex(models);
        const latestPerFamily = findLatestPerFamily(models);

        // Use the latest query file (has more answerer models), dedupe by answerer+family
        const allQueries = [...queries1, ...queries2];
        const seen = new Set<string>();
        const deduped: Query[] = [];
        for (const q of allQueries.reverse()) {
          const key = `${q.answerer_model_id}::${q.subject_family}`;
          if (!seen.has(key)) {
            seen.add(key);
            deduped.push(q);
          }
        }

        const results = deduped.map((q) =>
          evaluateQuery(q, modelIndex, latestPerFamily)
        );
        setEvaluated(results);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="loading">Loading results...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  // Build matrix: answerer models (rows) x subject families (columns)
  const answerers = [...new Set(evaluated.map((e) => e.answerer_model_id))];
  const families = [...new Set(evaluated.map((e) => e.subject_family))];

  // Sort families in a logical order
  const familyOrder = [
    "Claude Opus",
    "Claude Sonnet",
    "Claude Haiku",
    "GPT",
    "Gemini Pro",
    "Gemini Flash",
  ];
  families.sort(
    (a, b) => (familyOrder.indexOf(a) ?? 99) - (familyOrder.indexOf(b) ?? 99)
  );

  const lookup = new Map<string, EvaluatedQuery>();
  for (const e of evaluated) {
    lookup.set(`${e.answerer_model_id}::${e.subject_family}`, e);
  }

  const verdictCounts = { exact: 0, wrong: 0, parse_failure: 0 };
  for (const e of evaluated) {
    verdictCounts[e.verdict]++;
  }

  return (
    <div className="container">
      <h1>We Live in the Past</h1>
      <p className="subtitle">
        Do AI models know what's current? Each model was asked to identify the
        most recent model in each family via OpenRouter API.
      </p>

      <div className="summary">
        <span className="badge exact">{verdictCounts.exact} correct</span>
        <span className="badge wrong">{verdictCounts.wrong} wrong</span>
        <span className="badge parse-failure">
          {verdictCounts.parse_failure} parse failures
        </span>
        <span className="badge total">
          {evaluated.length} total
        </span>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th className="answerer-header">Answerer</th>
              {families.map((f) => (
                <th key={f}>{f}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {answerers.map((answerer) => (
              <tr key={answerer}>
                <td className="answerer-cell">
                  <div className="model-name">{shortModelName(answerer)}</div>
                  <div className="model-date">
                    {lookup.get(`${answerer}::${families[0]}`)
                      ?.answerer_release_date ?? ""}
                  </div>
                </td>
                {families.map((family) => {
                  const entry = lookup.get(`${answerer}::${family}`);
                  if (!entry) return <td key={family} className="cell empty">-</td>;
                  return (
                    <td
                      key={family}
                      className={`cell ${entry.verdict}`}
                      title={`Expected: ${entry.expected_model_id}\nAnswered: ${entry.answered_model_id ?? "(parse failure)"}\nExpected date: ${entry.expected_release_date}\nAnswered date: ${entry.answered_release_date ?? "unknown"}`}
                    >
                      <div className="answered-model">
                        {entry.answered_model_id
                          ? shortModelName(entry.answered_model_id)
                          : "parse failure"}
                      </div>
                      {entry.verdict === "wrong" && entry.answered_release_date && (
                        <div className="answered-date">
                          {entry.answered_release_date}
                        </div>
                      )}
                      {entry.verdict === "exact" && (
                        <div className="check-mark">correct</div>
                      )}
                      {entry.verdict === "wrong" &&
                        !entry.answered_release_date && (
                          <div className="unknown-model">unknown model</div>
                        )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="answerer-cell">
                <strong>Expected (latest)</strong>
              </td>
              {families.map((family) => {
                const entry = evaluated.find(
                  (e) => e.subject_family === family
                );
                return (
                  <td key={family} className="cell expected-footer">
                    <div className="answered-model">
                      {entry?.expected_model_id
                        ? shortModelName(entry.expected_model_id)
                        : "?"}
                    </div>
                    <div className="answered-date">
                      {entry?.expected_release_date ?? ""}
                    </div>
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

export default App;

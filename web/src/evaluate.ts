import type { Model, Query, EvaluatedQuery } from "./types";

export function buildModelIndex(models: Model[]): Map<string, Model> {
  return new Map(models.map((m) => [m.model_id, m]));
}

export function findLatestPerFamily(models: Model[]): Map<string, string> {
  const latest = new Map<string, Model>();
  for (const m of models) {
    const current = latest.get(m.family);
    if (!current || m.release_date > current.release_date) {
      latest.set(m.family, m);
    }
  }
  return new Map(
    Array.from(latest.entries()).map(([fam, m]) => [fam, m.model_id])
  );
}

export function evaluateQuery(
  query: Query,
  modelIndex: Map<string, Model>,
  latestPerFamily: Map<string, string>
): EvaluatedQuery {
  const expectedId = latestPerFamily.get(query.subject_family) ?? null;
  const expectedModel = expectedId ? modelIndex.get(expectedId) : undefined;
  const expectedDate = expectedModel?.release_date ?? null;

  const answeredModel = query.answered_model_id
    ? modelIndex.get(query.answered_model_id)
    : undefined;
  const answeredDate = answeredModel?.release_date ?? null;

  const answererModel = modelIndex.get(query.answerer_model_id);
  const answererDate = answererModel?.release_date ?? null;

  let verdict: EvaluatedQuery["verdict"];
  if (query.answered_model_id === null) {
    verdict = "parse_failure";
  } else if (query.answered_model_id === expectedId) {
    verdict = "exact";
  } else {
    verdict = "wrong";
  }

  return {
    ...query,
    expected_model_id: expectedId,
    expected_release_date: expectedDate,
    answered_release_date: answeredDate,
    answerer_release_date: answererDate,
    verdict,
  };
}

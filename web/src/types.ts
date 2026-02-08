export interface Model {
  model_id: string;
  family: string;
  release_date: string;
}

export interface Query {
  answerer_model_id: string;
  subject_family: string;
  prompt_id: string;
  answered_model_id: string | null;
  raw_response: string;
  queried_at: string;
}

export type Verdict = "exact" | "wrong" | "parse_failure";

export interface EvaluatedQuery extends Query {
  expected_model_id: string | null;
  expected_release_date: string | null;
  answered_release_date: string | null;
  answerer_release_date: string | null;
  verdict: Verdict;
}

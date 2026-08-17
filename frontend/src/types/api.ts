export type Platform = {
  id: string;
  display_name: string;
  url: string;
  group: string;
  enabled: boolean;
  sort_order: number;
  health_status: string;
  selectors: Record<string, string>;
  login_status?: string;
  login_checked_at?: string | null;
  login_message?: string;
  url_status?: string;
  url_checked_at?: string | null;
  url_check_message?: string;
  expected_host?: string;
};

export type PlatformAnswer = {
  id?: string;
  platform_id: string;
  platform_name: string;
  platform_url: string;
  answer_text: string;
  status: string;
  error_message: string;
  request_sent_at: string | null;
  first_token_at: string | null;
  completed_at: string | null;
  response_duration_ms: number | null;
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  preview?: string;
  qa_count?: number;
};

export type QAPair = {
  id: string;
  question: string;
  question_time: string;
  answers: PlatformAnswer[];
};

export type SessionDetail = SessionSummary & {
  qa_pairs: QAPair[];
};

export type OptimalAnswer = {
  text: string;
  summary: string;
  key_points: { text: string; sources: string[]; consensus: number }[];
  recommended_source: {
    platform_id: string;
    platform_name: string;
    score: number;
    reason: string;
  } | null;
  sources: { platform_id: string; platform_name: string; score: number; consensus: number; char_count: number }[];
  method: string;
  provider?: string | null;
  provider_label?: string | null;
  model?: string | null;
  confidence: number;
  rationale: string;
};

export type LlmModelOption = {
  id: string;
  label: string;
  tag: string;
};

export type LlmProviderOption = {
  id: string;
  label: string;
  configured: boolean;
  models: LlmModelOption[];
};

export type LlmStatus = {
  configured: boolean;
  provider: string | null;
  label: string | null;
  model: string | null;
  providers?: LlmProviderOption[];
  default_provider?: string | null;
  default_model?: string | null;
};

export type LlmChoice = {
  provider: string;
  model: string;
};

export type CompareResult = {
  compared_count: number;
  lengths: { platform_id: string; platform_name: string; char_count: number; word_count: number }[];
  duration_ranking: { platform_id: string; platform_name: string; duration_ms: number | null }[];
  similarity_matrix: { platform_a: string; platform_b: string; similarity: number }[];
  diff_highlights: { base_platform: string; compare_platform: string; diff_lines: string[] }[];
  optimal_answer?: OptimalAnswer;
};

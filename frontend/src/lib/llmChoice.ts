import type { LlmChoice, LlmStatus } from "../types/api";

const STORAGE_KEY = "oneqmultia.llmChoice";

/** 从本地恢复用户上次选择的最优答案模型。 */
export function loadStoredLlmChoice(): LlmChoice | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LlmChoice;
    if (parsed?.provider && parsed?.model) return parsed;
  } catch {
    return null;
  }
  return null;
}

export function saveLlmChoice(choice: LlmChoice): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
}

/** 优先本地选择，否则用服务端默认已配置模型。 */
export function resolveLlmChoice(status: LlmStatus | null, stored: LlmChoice | null): LlmChoice | null {
  const providers = status?.providers ?? [];
  const usable = (choice: LlmChoice | null) => {
    if (!choice) return false;
    const provider = providers.find((item) => item.id === choice.provider);
    return Boolean(provider?.configured && provider.models.some((m) => m.id === choice.model));
  };
  if (usable(stored)) return stored;
  if (status?.default_provider && status.default_model) {
    return { provider: status.default_provider, model: status.default_model };
  }
  return null;
}

export function compareQuery(choice: LlmChoice | null): string {
  if (!choice?.provider || !choice?.model) return "";
  const params = new URLSearchParams({ provider: choice.provider, model: choice.model });
  return `?${params.toString()}`;
}

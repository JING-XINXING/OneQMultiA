import type { LlmChoice, LlmStatus } from "../types/api";

type Props = {
  status: LlmStatus | null;
  value: LlmChoice | null;
  onChange: (choice: LlmChoice) => void;
  disabled?: boolean;
};

/** 选择用于重写最优答案的国内/国际模型。 */
export function LlmModelPicker({ status, value, onChange, disabled }: Props) {
  const providers = status?.providers ?? [];
  const current = value?.provider && value?.model ? `${value.provider}::${value.model}` : "";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="section-kicker">最优答案模型</p>
          <p className="mt-0.5 text-[11px] text-slate-500">用选定模型阅读全部回答后重写一份完整答案</p>
        </div>
      </div>
      <select
        aria-label="选择最优答案模型"
        className="input-bento py-2.5"
        disabled={disabled || providers.length === 0}
        value={current}
        onChange={(event) => {
          const [provider, model] = event.target.value.split("::");
          if (provider && model) onChange({ provider, model });
        }}
      >
        {!current && <option value="">请选择已配置 Key 的模型</option>}
        {providers.map((item) => (
          <optgroup key={item.id} label={`${item.label}${item.configured ? "" : "（未配置 Key）"}`}>
            {item.models.map((model) => (
              <option key={`${item.id}-${model.id}`} value={`${item.id}::${model.id}`} disabled={!item.configured}>
                {item.label} · {model.label}
                {model.tag ? ` · ${model.tag}` : ""}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

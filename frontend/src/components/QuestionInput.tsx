type Props = {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  disabled?: boolean;
  loading?: boolean;
};

/** Bento 风格提问输入框：提问中显示停止，避免单平台长时间占住进程 */
export function QuestionInput({ value, onChange, onSubmit, onCancel, disabled, loading }: Props) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <textarea
        value={value}
        aria-label="输入问题"
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入一个问题，同时问多个助手。Ctrl + Enter 发送"
        rows={3}
        className="input-bento min-h-[88px] flex-1"
        disabled={loading}
        onKeyDown={(e) => {
          if (loading) return;
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSubmit();
        }}
      />
      {loading ? (
        <button
          type="button"
          className="btn-danger min-h-[44px] w-full flex-shrink-0 px-6 sm:h-[88px] sm:w-auto"
          onClick={onCancel}
        >
          停止
        </button>
      ) : (
        <button
          type="button"
          className="btn min-h-[44px] w-full flex-shrink-0 px-6 sm:h-[88px] sm:w-auto"
          disabled={disabled || !value.trim()}
          onClick={onSubmit}
        >
          发送
        </button>
      )}
    </div>
  );
}

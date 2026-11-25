import { useState } from "react";
import { ExportMenu } from "./ExportMenu";

type Props = {
  sessionId: string | null;
  onShare: (url: string) => void;
};

/** 手机端导出抽屉，与桌面侧栏的导出/分享能力对齐。 */
export function MobileExportSheet({ sessionId, onShare }: Props) {
  const [open, setOpen] = useState(false);
  if (!sessionId) return null;

  return (
    <>
      <button
        type="button"
        className="btn-sm md:hidden"
        onClick={() => setOpen(true)}
      >
        导出 / 分享
      </button>
      {open && (
        <div className="fixed inset-0 z-[60] md:hidden">
          <button
            type="button"
            aria-label="关闭导出"
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 rounded-t-2xl bg-white p-4 pb-8 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">导出与分享</h2>
              <button type="button" className="btn-sm" onClick={() => setOpen(false)}>
                关闭
              </button>
            </div>
            <ExportMenu sessionId={sessionId} onShare={onShare} />
          </div>
        </div>
      )}
    </>
  );
}

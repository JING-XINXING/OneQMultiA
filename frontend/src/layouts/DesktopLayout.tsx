import type { ReactNode } from "react";

type Props = {
  sidebar: ReactNode;
  children: ReactNode;
  header?: ReactNode;
};

/** 桌面端模块化工作台布局。 */
export function DesktopLayout({ sidebar, children, header }: Props) {
  return (
    <div className="hidden md:flex flex-col h-screen overflow-hidden bg-surface">
      {header && (
        <header className="flex-shrink-0 h-[var(--header-h)] border-b border-surface-border bg-white/90 backdrop-blur-sm px-5 flex items-center shadow-[0_1px_0_rgba(15,23,42,0.02)]">
          {header}
        </header>
      )}

      <div className="flex-1 flex overflow-hidden">
        <aside className="flex w-[280px] flex-shrink-0 flex-col space-y-3 overflow-y-auto border-r border-surface-border bg-white/70 p-4">
          {sidebar}
        </aside>

        <main className="flex-1 overflow-y-auto bg-grid-pattern bg-grid p-5">
          <div className="max-w-[1400px] mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

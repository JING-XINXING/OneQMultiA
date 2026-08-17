import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  header?: ReactNode;
};

/** 移动端模块化工作台布局。 */
export function MobileLayout({ children, header }: Props) {
  return (
    <main className="md:hidden min-h-screen bg-surface">
      {header && (
        <header className="sticky top-0 z-40 flex h-[var(--header-h)] items-center border-b border-surface-border bg-white/90 px-4 backdrop-blur-md">
          {header}
        </header>
      )}
      <div className="p-3 pb-24 max-w-lg mx-auto animate-fade-in">
        {children}
      </div>
    </main>
  );
}

import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export function Card({ children, className = "" }: CardProps) {
  return <section className={`page-card ${className}`}>{children}</section>;
}

export function CardHeader({
  action,
  children,
  className = "",
}: CardProps & { action?: ReactNode }) {
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 ${className}`}
    >
      <div>{children}</div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-lg font-bold text-slate-950">{children}</h2>;
}

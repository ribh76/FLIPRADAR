import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export type BreadcrumbItem = {
  label: string;
  to?: string;
};

export function PageHeader({
  action,
  breadcrumbs,
  description,
  eyebrow,
  title,
}: {
  action?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  description?: string;
  eyebrow?: string;
  title: string;
}) {
  return (
    <section className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <nav aria-label="Breadcrumb" className="mb-3">
            <ol className="flex flex-wrap items-center gap-1 text-xs font-semibold text-[rgba(255,247,237,0.72)]">
              {breadcrumbs.map((item, index) => (
                <li className="inline-flex items-center gap-1" key={item.label}>
                  {index > 0 ? (
                    <ChevronRight size={14} aria-hidden="true" />
                  ) : null}
                  {item.to ? (
                    <Link className="hover:text-brand-accent" to={item.to}>
                      {item.label}
                    </Link>
                  ) : (
                    <span aria-current="page">{item.label}</span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
        {eyebrow ? (
          <p className="metric-label text-brand-accent">{eyebrow}</p>
        ) : null}
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-subtitle">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </section>
  );
}

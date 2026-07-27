import { Boxes, Calculator, Search } from "lucide-react";
import { Link } from "react-router-dom";

const actions = [
  {
    to: "/analyze",
    title: "Analyze Set",
    description:
      "Get buy, pass, sell, hold, watch, advice, and analysis from asking price and market context.",
    icon: Calculator,
    iconClass: "bg-brand-accent text-brand-black",
  },
  {
    to: "/portfolio",
    title: "Portfolio",
    description:
      "Track your LEGO collection, cost basis, current value, and unrealized gain or loss.",
    icon: Boxes,
    iconClass: "bg-brand-amber text-brand-black",
  },
  {
    to: "/sets",
    title: "Set Detail Lookup",
    description:
      "Look up LEGO set details, latest market snapshot, valuation status, and current fair value.",
    icon: Search,
    iconClass: "bg-brand-warning text-white",
  },
];

export function DashboardPage() {
  return (
    <section>
      <div className="grid gap-5 md:grid-cols-3">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              className="page-card group block transition hover:-translate-y-1 hover:shadow-[var(--shadow-lifted)]"
              key={action.to}
              to={action.to}
            >
              <div
                className={`mb-8 flex h-12 w-12 items-center justify-center rounded-[var(--radius-control)] ${action.iconClass}`}
              >
                <Icon size={23} aria-hidden="true" />
              </div>
              <h2 className="text-xl font-bold text-[var(--color-text)]">
                {action.title}
              </h2>
              <p className="mt-3 min-h-24 text-sm leading-6 text-[var(--color-text-muted)]">
                {action.description}
              </p>
              <div className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-[var(--color-info)]">
                Open
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

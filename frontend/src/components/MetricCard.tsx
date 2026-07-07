export function MetricCard({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad" | "watch" | "hold";
}) {
  const toneClass = {
    neutral: "border-slate-200",
    good: "border-emerald-200 bg-emerald-50",
    bad: "border-red-200 bg-red-50",
    watch: "border-amber-200 bg-amber-50",
    hold: "border-blue-200 bg-blue-50"
  }[tone];

  return (
    <div className={`rounded-lg border p-5 ${toneClass}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}

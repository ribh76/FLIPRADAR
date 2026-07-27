export function MetricCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad" | "watch" | "hold";
}) {
  const toneClass = {
    neutral: "border-[var(--color-border-soft)]",
    good: "border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)]",
    bad: "border-[var(--color-warning)] bg-[rgba(145,3,3,0.1)]",
    watch: "border-[var(--color-accent-warm)] bg-[rgba(235,136,30,0.14)]",
    hold: "border-[var(--color-accent)] bg-[rgba(73,252,226,0.08)]",
  }[tone];

  return (
    <div className={`rounded-[var(--radius-card)] border p-5 ${toneClass}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}

import { useState } from "react";
import { Logo } from "../../components/Logo";
import {
  Badge,
  Card,
  CardHeader,
  CardTitle,
  ConfirmationDialog,
  DataTable,
  EmptyState,
  FormAlert,
  MetricCard,
  SelectField,
  Skeleton,
  SkeletonCard,
  StatusBadge,
  TextField,
} from "../../components/ui";

const semanticSwatches = [
  {
    label: "Gain",
    className: "bg-[var(--color-gain)]",
    value: "Positive value movement",
  },
  {
    label: "Loss",
    className: "bg-[var(--color-loss)]",
    value: "Negative value movement",
  },
  {
    label: "Warning",
    className: "bg-[var(--color-warning)]",
    value: "Destructive or risky action",
  },
  {
    label: "Information",
    className: "bg-[var(--color-info)]",
    value: "Helpful context and prompts",
  },
  {
    label: "Neutral",
    className: "bg-[var(--color-neutral)]",
    value: "Secondary metadata",
  },
];

const showcaseRows = [
  { change: "+$42", set: "75192-1", status: "BUY", value: "$812" },
  { change: "-$18", set: "10294-1", status: "WATCH", value: "$186" },
];

export function ShowcasePage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  return (
    <section className="space-y-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Logo and Brand Usage</CardTitle>
          </CardHeader>
          <div className="mt-5 space-y-5">
            <div className="rounded-[var(--radius-card)] bg-brand-black p-5">
              <Logo />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] p-4">
                <div className="h-10 rounded-[var(--radius-control)] bg-brand-black" />
                <p className="mt-3 text-sm font-semibold text-[var(--color-text)]">
                  Background
                </p>
                <p className="text-xs text-[var(--color-text-muted)]">
                  #050000
                </p>
              </div>
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] p-4">
                <div className="h-10 rounded-[var(--radius-control)] bg-brand-accent" />
                <p className="mt-3 text-sm font-semibold text-[var(--color-text)]">
                  Primary accent
                </p>
                <p className="text-xs text-[var(--color-text-muted)]">
                  #49fce2
                </p>
              </div>
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] p-4">
                <div className="h-10 rounded-[var(--radius-control)] bg-brand-amber" />
                <p className="mt-3 text-sm font-semibold text-[var(--color-text)]">
                  Warm accent
                </p>
                <p className="text-xs text-[var(--color-text-muted)]">
                  #eb881e
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Typography and Shape</CardTitle>
          </CardHeader>
          <div className="mt-5 space-y-4">
            <div>
              <p className="metric-label">Heading</p>
              <p className="mt-1 text-3xl font-black text-[var(--color-text)]">
                Confident, compact, scannable.
              </p>
            </div>
            <p className="text-sm leading-6 text-[var(--color-text-muted)]">
              Cards use an 8px radius. Form controls use 6px. Spacing follows
              compact 4px multiples, with dense dashboard surfaces and clear
              focus rings.
            </p>
            <div className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] p-4 shadow-[var(--shadow-soft)]">
              Shadow and border sample
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Semantic Colors</CardTitle>
        </CardHeader>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {semanticSwatches.map((swatch) => (
            <div
              className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] p-4"
              key={swatch.label}
            >
              <div
                className={`h-10 rounded-[var(--radius-control)] ${swatch.className}`}
              />
              <p className="mt-3 text-sm font-bold text-[var(--color-text)]">
                {swatch.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">
                {swatch.value}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>States and Skeletons</CardTitle>
          </CardHeader>
          <div className="mt-5 space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="Gain" tone="good" value="+$42" />
              <MetricCard label="Loss" tone="bad" value="-$18" />
              <MetricCard label="Watch" tone="watch" value="12" />
            </div>
            <Skeleton className="h-8 w-2/3" />
            <SkeletonCard />
            <EmptyState
              message="No matching sets yet. Adjust filters or run a new lookup."
              title="No set data"
            />
            <FormAlert tone="success">Saved successfully.</FormAlert>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Forms, Badges, Dialogs</CardTitle>
          </CardHeader>
          <div className="mt-5 space-y-4">
            <TextField
              helpText="Visible labels are required."
              label="Set number"
              placeholder="75192-1"
            />
            <SelectField label="Condition" defaultValue="sealed">
              <option value="sealed">Sealed</option>
              <option value="used">Used</option>
            </SelectField>
            <div className="flex flex-wrap gap-2">
              <Badge tone="success">Gain</Badge>
              <Badge tone="danger">Loss</Badge>
              <Badge tone="warning">Watch</Badge>
              <StatusBadge value="BUY" />
              <StatusBadge value="PASS" />
            </div>
            <button
              className="primary-button"
              onClick={() => setIsDialogOpen(true)}
              type="button"
            >
              Open confirmation
            </button>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="border-b border-[var(--color-border-soft)] p-5">
          <CardTitle>Responsive Table and Card Behavior</CardTitle>
        </div>
        <DataTable
          caption="Example responsive set data"
          columns={[
            {
              header: "Set",
              key: "set",
              render: (row) => (
                <span className="font-bold text-[var(--color-text)]">
                  {row.set}
                </span>
              ),
            },
            { header: "Value", key: "value", render: (row) => row.value },
            {
              header: "Change",
              key: "change",
              render: (row) => (
                <span
                  className={
                    row.change.startsWith("+")
                      ? "semantic-gain"
                      : "semantic-loss"
                  }
                >
                  {row.change}
                </span>
              ),
            },
            {
              header: "Status",
              key: "status",
              render: (row) => <StatusBadge value={row.status} />,
            },
          ]}
          getRowKey={(row) => row.set}
          rows={showcaseRows}
        />
      </Card>

      <ConfirmationDialog
        confirmLabel="Confirm"
        description="This demonstrates a small-screen friendly dialog with keyboard focus and a visible close action."
        isOpen={isDialogOpen}
        onCancel={() => setIsDialogOpen(false)}
        onConfirm={() => setIsDialogOpen(false)}
        title="Confirm action"
      />
    </section>
  );
}

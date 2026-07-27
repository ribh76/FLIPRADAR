import type { ReactNode } from "react";
import { EmptyState } from "./PageState";
import { Skeleton } from "./Skeleton";

export type DataTableColumn<TRow> = {
  align?: "left" | "right";
  header: string;
  key: string;
  render: (row: TRow) => ReactNode;
};

export function DataTable<TRow>({
  columns,
  emptyMessage,
  getRowKey,
  isLoading = false,
  minWidth = "720px",
  rows,
}: {
  columns: DataTableColumn<TRow>[];
  emptyMessage?: string;
  getRowKey: (row: TRow) => string;
  isLoading?: boolean;
  minWidth?: string;
  rows: TRow[];
}) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4" aria-label="Loading rows">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} title="No rows found" />;
  }

  return (
    <>
      <div className="grid gap-3 md:hidden">
        {rows.map((row) => (
          <article
            className="rounded-[var(--radius-card)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4"
            key={getRowKey(row)}
          >
            {columns.map((column) => (
              <div
                className="grid grid-cols-[7.5rem_1fr] gap-3 py-2"
                key={column.key}
              >
                <div className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                  {column.header}
                </div>
                <div className={column.align === "right" ? "text-right" : ""}>
                  {column.render(row)}
                </div>
              </div>
            ))}
          </article>
        ))}
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table
          className="w-full border-collapse text-left text-sm"
          style={{ minWidth }}
        >
          <thead className="bg-[var(--color-surface-muted)] text-xs uppercase tracking-normal text-[var(--color-text-muted)]">
            <tr>
              {columns.map((column) => (
                <th
                  className={`px-4 py-3 ${column.align === "right" ? "text-right" : ""}`}
                  key={column.key}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border-soft)]">
            {rows.map((row) => (
              <tr className="bg-[var(--color-surface)]" key={getRowKey(row)}>
                {columns.map((column) => (
                  <td
                    className={`px-4 py-3 ${column.align === "right" ? "text-right" : ""}`}
                    key={column.key}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

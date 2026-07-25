import type { ReactNode } from "react";
import { EmptyState, LoadingState } from "./PageState";

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
    return <LoadingState title="Loading rows..." />;
  }

  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} title="No rows found" />;
  }

  return (
    <div className="overflow-x-auto">
      <table
        className="w-full border-collapse text-left text-sm"
        style={{ minWidth }}
      >
        <thead className="bg-slate-50 text-xs uppercase tracking-normal text-slate-500">
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
        <tbody className="divide-y divide-slate-200">
          {rows.map((row) => (
            <tr className="bg-white" key={getRowKey(row)}>
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
  );
}

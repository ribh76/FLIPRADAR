export function currency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(parsed);
}

export function numberValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "--";
  }
  return new Intl.NumberFormat("en-US").format(parsed);
}

export function percent(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "--";
  }
  return `${parsed.toFixed(1)}%`;
}

export function signedCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "--";
  }
  const prefix = parsed > 0 ? "+" : "";
  return `${prefix}${currency(parsed)}`;
}

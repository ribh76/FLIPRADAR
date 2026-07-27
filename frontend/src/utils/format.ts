export function currency(
  value: number | string | null | undefined,
  currencyCode = "USD",
): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "--";
  }
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode.toUpperCase(),
      maximumFractionDigits: 0,
    }).format(parsed);
  } catch {
    return parsed.toLocaleString("en-US", {
      maximumFractionDigits: 2,
    });
  }
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

export function signedCurrency(
  value: number | string | null | undefined,
): string {
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

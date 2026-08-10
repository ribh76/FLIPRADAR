const RECENT_SET_SEARCHES_KEY = "flipradar_recent_set_searches";
const DEAL_FILTERS_KEY = "flipradar_deal_filters";
const MAX_RECENT_SEARCHES = 6;

function canUseStorage() {
  return typeof window !== "undefined" && Boolean(window.sessionStorage);
}

export function getRecentSetSearches(): string[] {
  if (!canUseStorage()) return [];
  try {
    const value = JSON.parse(
      window.sessionStorage.getItem(RECENT_SET_SEARCHES_KEY) ?? "[]",
    );
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function saveRecentSetSearch(query: string): void {
  const value = query.trim();
  if (!value || !canUseStorage()) return;
  const next = [value, ...getRecentSetSearches().filter((item) => item !== value)]
    .slice(0, MAX_RECENT_SEARCHES);
  window.sessionStorage.setItem(RECENT_SET_SEARCHES_KEY, JSON.stringify(next));
}

export function getSavedDealFilters(): string {
  return canUseStorage()
    ? window.sessionStorage.getItem(DEAL_FILTERS_KEY) ?? ""
    : "";
}

export function saveDealFilters(filters: string): void {
  if (!canUseStorage()) return;
  window.sessionStorage.setItem(DEAL_FILTERS_KEY, filters);
}

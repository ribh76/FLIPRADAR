#!/usr/bin/env bash
set -euo pipefail

# Measures the running local stack. Start it with ./scripts/run_local_app.sh first.
backend_url="${BACKEND_URL:-http://127.0.0.1:8000}"
frontend_url="${FRONTEND_URL:-http://127.0.0.1:5173}"
requests="${REQUESTS:-25}"
concurrency="${CONCURRENCY:-5}"

measure() {
  local label="$1"
  local url="$2"
  curl --silent --show-error --output /dev/null \
    --write-out "${label} status=%{http_code} connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s\\n" \
    "$url"
}

echo "Single-request latency"
measure backend_health "${backend_url}/health"
measure frontend_shell "${frontend_url}/"

echo "Load: ${requests} backend health requests at concurrency ${concurrency}"
times_file="$(mktemp)"
trap 'rm -f "$times_file"' EXIT
seq 1 "$requests" | xargs -n1 -P"$concurrency" -I{} \
  curl --silent --output /dev/null --write-out '%{time_total}\n' "${backend_url}/health" \
  > "$times_file"
count="$(wc -l < "$times_file" | tr -d ' ')"
average="$(awk '{ sum += $1 } END { if (NR) printf "%.4f", sum / NR }' "$times_file")"
sorted_file="$(mktemp)"
sort -n "$times_file" > "$sorted_file"
p95_index=$(( (count * 95 + 99) / 100 ))
p95="$(sed -n "${p95_index}p" "$sorted_file")"
maximum="$(tail -n 1 "$sorted_file")"
rm -f "$sorted_file"
printf 'count=%s avg=%ss p95=%ss max=%ss\n' "$count" "$average" "$p95" "$maximum"

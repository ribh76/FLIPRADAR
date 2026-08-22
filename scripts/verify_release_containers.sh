#!/usr/bin/env bash
set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repository_root/docker-compose.release.yml"
project_name="flipradar-release-certification-${RANDOM}"
frontend_port="${FRONTEND_PORT:-8080}"
release_tag="${RELEASE_TAG:-local-release-certification}"
compose=(docker compose -p "$project_name" -f "$compose_file")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}

failure_details() {
  echo "Release container certification failed; service logs follow:" >&2
  "${compose[@]}" logs --no-color >&2 || true
}

trap cleanup EXIT
trap failure_details ERR

wait_for_status() {
  local expected_status="$1"
  local url="$2"
  local attempt
  for attempt in {1..30}; do
    local actual_status
    actual_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$url" || true)"
    if [[ "$actual_status" == "$expected_status" ]]; then
      return 0
    fi
    sleep 1
  done
  echo "Expected HTTP $expected_status from $url" >&2
  return 1
}

assert_no_bind_mounts() {
  local service="$1"
  local container_id mounts
  container_id="$("${compose[@]}" ps -q "$service")"
  mounts="$(docker inspect -f '{{range .Mounts}}{{.Type}} {{.Source}}{{"\\n"}}{{end}}' "$container_id")"
  if rg --quiet '^bind ' <<<"$mounts"; then
    echo "$service unexpectedly has a bind mount:" >&2
    echo "$mounts" >&2
    return 1
  fi
}

export FRONTEND_PORT="$frontend_port"
export RELEASE_TAG="$release_tag"

"${compose[@]}" build --pull --quiet
"${compose[@]}" --profile migrations run --rm migrations
"${compose[@]}" up --detach

wait_for_status 200 "http://127.0.0.1:$frontend_port/api/health/live"
wait_for_status 200 "http://127.0.0.1:$frontend_port/api/health/ready"
assert_no_bind_mounts backend
assert_no_bind_mounts frontend

root_page="$(curl --fail --silent "http://127.0.0.1:$frontend_port/")"
[[ "$root_page" == *'id="root"'* ]]

router_page="$(curl --fail --silent "http://127.0.0.1:$frontend_port/portfolio")"
[[ "$router_page" == *'id="root"'* ]]

asset_path="$(tr '"' '\n' <<<"$root_page" | rg '^/assets/' | head -n 1)"
[[ -n "$asset_path" ]]
asset_headers="$(curl --fail --silent --head "http://127.0.0.1:$frontend_port$asset_path")"
rg --ignore-case --quiet '^cache-control: .*immutable' <<<"$asset_headers"

"${compose[@]}" stop db
wait_for_status 200 "http://127.0.0.1:$frontend_port/api/health/live"
wait_for_status 503 "http://127.0.0.1:$frontend_port/api/health/ready"
"${compose[@]}" start db
wait_for_status 200 "http://127.0.0.1:$frontend_port/api/health/ready"

"${compose[@]}" stop -t 35 backend
backend_logs="$("${compose[@]}" logs backend)"
rg --quiet 'application shutdown complete' <<<"$backend_logs"

echo "Release container certification passed."

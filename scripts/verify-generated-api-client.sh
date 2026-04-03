#!/usr/bin/env bash
set -euo pipefail

snapshot() {
  find packages/api-client/openapi.json packages/api-client/src/generated -type f -print0 \
    | sort -z \
    | xargs -0 sha256sum
}

before_snapshot="$(snapshot)"
pnpm --filter @serino/api-client run generate:api >/dev/null
after_snapshot="$(snapshot)"

if [[ "${before_snapshot}" != "${after_snapshot}" ]]; then
  echo "ERROR: generated API client artifacts are not reproducible from the current OpenAPI spec." >&2
  git diff --name-status -- packages/api-client/openapi.json packages/api-client/src/generated >&2 || true
  exit 1
fi

echo "Generated API client artifacts are reproducible."

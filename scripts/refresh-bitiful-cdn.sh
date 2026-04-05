#!/usr/bin/env bash
set -euo pipefail

BINFEN_CDN_API_ENDPOINT="${BINFEN_CDN_API_ENDPOINT:-https://api.bitiful.com/cdn/cache/refresh}"
BINFEN_CDN_API_TOKEN="${BINFEN_CDN_API_TOKEN:?BINFEN_CDN_API_TOKEN is required}"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 <url> [<url> ...]" >&2
  exit 1
fi

python3 - "$@" <<'PY' | while IFS= read -r payload; do
import json
import sys

urls = []
for raw in sys.argv[1:]:
    value = raw.strip()
    if value and value not in urls:
        urls.append(value)

if not urls:
    raise SystemExit(1)

for idx in range(0, len(urls), 20):
    chunk = urls[idx : idx + 20]
    print(json.dumps({"type": "url", "url_list": chunk}, ensure_ascii=False))
PY
  curl --fail-with-body --silent --show-error \
    -X POST \
    -H "Authorization: ${BINFEN_CDN_API_TOKEN}" \
    -H "Content-Type: application/json" \
    "${BINFEN_CDN_API_ENDPOINT}" \
    -d "${payload}"
  printf '\n' >&2
done

#!/usr/bin/env bash
set -euo pipefail

if rg -n --glob '*.{ts,tsx,js,jsx,mjs,cjs}' 'from ["'"'"'](\.\.?/)+packages/.*/src/|import\(["'"'"'](\.\.?/)+packages/.*/src/|from ["'"'"']@serino/.*/src/|import\(["'"'"']@serino/.*/src/' admin/src frontend/src; then
  echo "ERROR: app code must consume workspace packages through their public exports, not packages/*/src/*." >&2
  exit 1
fi

if rg -n --glob '*.{ts,tsx,js,jsx,mjs,cjs}' 'from ["'"'"'](\.\.?/)+(.*/)?(admin|frontend)/|import\(["'"'"'](\.\.?/)+(.*/)?(admin|frontend)/|from ["'"'"'](\.\.?/)*vite\.config|import\(["'"'"'](\.\.?/)*vite\.config' packages; then
  echo "ERROR: workspace packages must not import application source trees or app build configs." >&2
  exit 1
fi

echo "Workspace boundary check passed."

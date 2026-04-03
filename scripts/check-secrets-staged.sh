#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "${ROOT_DIR}"

MODE="${1:-staged}"
if [[ "${MODE}" != "staged" && "${MODE}" != "--all" ]]; then
  echo "Usage: bash scripts/check-secrets-staged.sh [staged|--all]" >&2
  exit 2
fi

mapfile -t FILES < <(
  if [[ "${MODE}" == "--all" ]]; then
    git ls-files
  else
    git diff --cached --name-only --diff-filter=ACMR
  fi
)

if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi

BLOCKED_PATH_RE='(^|/)\.env\.local$|(^|/)\.env\.[^/]+\.local$|^companions/.+/.env$'
HIGH_SIGNAL_RE='(-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})'
HIGH_SIGNAL_ALLOWLIST_RE='(startswith\("-----BEGIN PRIVATE KEY-----"\)|replace-with)'
GENERIC_ASSIGN_RE="^[[:space:]]*['\"]?[A-Za-z0-9_.-]*(password|secret|token|api[_-]?key|client_secret)[A-Za-z0-9_.-]*['\"]?[[:space:]]*[:=][[:space:]]*['\"]?[^'\"[:space:]]{8,}"
ALLOWLIST_RE='(replace-with|change-me|example|yourdomain|your-|<API_KEY>|\$\{|\{\{|localhost|127\.0\.0\.1|do-not-reply@course\.pku\.edu\.cn|smoke-)'

failed=0

is_config_like() {
  case "$1" in
    *.env|*.env.*|*.yaml|*.yml|*.json|*.ini|*.conf|*.cfg)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

check_line() {
  local file="$1"
  local line="$2"

  if [[ "${line}" =~ ${HIGH_SIGNAL_RE} ]] && [[ ! "${line}" =~ ${HIGH_SIGNAL_ALLOWLIST_RE} ]]; then
    echo "[secret-guard] High-risk secret pattern found in ${file}" >&2
    echo "[secret-guard] line: ${line}" >&2
    failed=1
    return
  fi

  if is_config_like "${file}" && [[ "${line}" =~ ${GENERIC_ASSIGN_RE} ]] && [[ ! "${line}" =~ ${ALLOWLIST_RE} ]]; then
    echo "[secret-guard] Suspicious credential assignment found in ${file}" >&2
    echo "[secret-guard] line: ${line}" >&2
    failed=1
  fi
}

for file in "${FILES[@]}"; do
  if [[ ! -f "${file}" ]]; then
    continue
  fi

  if [[ "${file}" =~ ${BLOCKED_PATH_RE} ]]; then
    echo "[secret-guard] Forbidden local secret file staged: ${file}" >&2
    echo "[secret-guard] Keep local env files untracked." >&2
    failed=1
    continue
  fi

  if [[ "${MODE}" == "--all" ]]; then
    while IFS= read -r line; do
      check_line "${file}" "${line}"
    done < "${file}"
    continue
  fi

  while IFS= read -r line; do
    check_line "${file}" "${line}"
  done < <(git --no-pager diff --cached -U0 -- "${file}" | grep -E '^\+[^+]' | sed 's/^+//')
done

if [[ ${failed} -ne 0 ]]; then
  echo "[secret-guard] Commit blocked. Remove secrets or move them to local ignored files." >&2
  exit 1
fi

exit 0
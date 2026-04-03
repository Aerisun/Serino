#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
HOOKS_DIR="${ROOT_DIR}/.git/hooks"
PRE_COMMIT_HOOK="${HOOKS_DIR}/pre-commit"

mkdir -p "${HOOKS_DIR}"

cat > "${PRE_COMMIT_HOOK}" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
bash "${ROOT_DIR}/scripts/check-secrets-staged.sh" staged

if command -v pre-commit >/dev/null 2>&1; then
	mapfile -t STAGED_FILES < <(git diff --cached --name-only --diff-filter=ACMR)
	if [[ ${#STAGED_FILES[@]} -gt 0 ]]; then
		pre-commit run --hook-stage pre-commit --files "${STAGED_FILES[@]}"
	fi
fi
HOOK

chmod +x "${PRE_COMMIT_HOOK}"

echo "Installed git pre-commit hook: ${PRE_COMMIT_HOOK}"
echo "This hook blocks committing local env files and obvious secret strings."
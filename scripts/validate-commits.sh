#!/usr/bin/env bash
set -euo pipefail
range="${1:-HEAD~1..HEAD}"
commits=$(git rev-list --no-merges "${range}")
[[ -z "${commits}" ]] && exit 0
invalid=0
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([[:alnum:]_.-]+\))?(!)?: .+'
while IFS= read -r commit; do
  subject=$(git log -1 --format=%s "${commit}")
  if [[ ! "${subject}" =~ ${pattern} ]]; then
    printf 'Commit inválido: %s (%s)\n' "${commit}" "${subject}" >&2
    invalid=1
  fi
done <<< "${commits}"
exit "${invalid}"

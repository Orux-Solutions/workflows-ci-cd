#!/usr/bin/env bash
set -euo pipefail
last_tag=$(git describe --tags --abbrev=0 2>/dev/null || true)
range="${last_tag:+${last_tag}..}HEAD"
subjects=$(git log --format=%s "${range}")
[[ -z "${subjects}" ]] && exit 0
if grep -Eq '(^|!)(\(|:)|BREAKING CHANGE' <<< "${subjects}"; then bump=major
elif grep -Eq '^feat(\([^)]*\))?:' <<< "${subjects}"; then bump=minor
elif grep -Eq '^(fix|perf)(\([^)]*\))?:' <<< "${subjects}"; then bump=patch
else exit 0; fi
base=${last_tag#v}; base=${base:-0.0.0}
IFS=. read -r major minor patch <<< "${base}"
case "${bump}" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
esac
printf '%s.%s.%s\n' "${major}" "${minor}" "${patch}"

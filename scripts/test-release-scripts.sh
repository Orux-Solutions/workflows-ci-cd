#!/usr/bin/env bash
set -euo pipefail
test_root=$(mktemp -d)
script_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
trap 'rm -rf "${test_root}"' EXIT
git -C "${test_root}" init -q
git -C "${test_root}" config user.name tester
git -C "${test_root}" config user.email tester@example.com
touch "${test_root}/README"
git -C "${test_root}" add README
git -C "${test_root}" commit -qm 'feat: initial functionality'
assert_version() {
  local expected=$1 actual
  actual=$(cd "${test_root}" && "${script_root}/calculate-version.sh")
  [[ "${actual}" == "${expected}" ]] || { echo "Expected ${expected}, got ${actual}" >&2; exit 1; }
}
assert_version 0.1.0
git -C "${test_root}" tag v0.1.0
git -C "${test_root}" commit --allow-empty -qm 'fix: repair release trigger'
assert_version 0.1.1
for feature in $(seq 1 10); do
  git -C "${test_root}" commit --allow-empty -qm "feat: add capability ${feature}"
done
assert_version 1.0.0
git -C "${test_root}" tag v1.0.0
git -C "${test_root}" commit --allow-empty -qm 'feat: add release dispatch'
assert_version 1.1.0
git -C "${test_root}" commit --allow-empty -qm 'feat!: change release contract'
assert_version 2.0.0
git -C "${test_root}" commit --allow-empty -qm 'invalid release message'
if (cd "${test_root}" && "${script_root}/validate-commits.sh" HEAD~1..HEAD); then
  echo 'Expected invalid commit to fail validation' >&2
  exit 1
fi
git -C "${test_root}" commit --allow-empty -qm 'ci: validate release messages'
(cd "${test_root}" && "${script_root}/validate-commits.sh" HEAD~1..HEAD)
echo 'release scripts: all tests passed'

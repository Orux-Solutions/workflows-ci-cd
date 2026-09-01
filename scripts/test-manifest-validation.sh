#!/usr/bin/env bash
set -euo pipefail
root=$(mktemp -d)
script_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
trap 'rm -rf "${root}"' EXIT
mkdir -p "${root}/packages/bookings"
cat > "${root}/packages/bookings/manifest.json" <<'JSON'
{"module":"bookings","section":"services","page":"bookings","features":[{"key":"create","dependencies":[]},{"key":"photo_upload","dependencies":["create"]}]}
JSON
(cd "${root}" && "${script_root}/validate-manifests.sh")
echo 'manifest validation tests: all passed'

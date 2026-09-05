#!/usr/bin/env bash
set -Eeuo pipefail

required=(
  GITHUB_ORG
  GITHUB_APP_ID
  GITHUB_APP_INSTALLATION_ID
  GITHUB_RUNNER_GROUP_ID
  GITHUB_APP_PRIVATE_KEY_FILE
)

for variable in "${required[@]}"; do
  if [[ -z "${!variable:-}" ]]; then
    printf 'Missing required runner setting: %s\n' "${variable}" >&2
    exit 78
  fi
done

for variable in GITHUB_APP_ID GITHUB_APP_INSTALLATION_ID GITHUB_RUNNER_GROUP_ID; do
  if [[ ! "${!variable}" =~ ^[0-9]+$ ]]; then
    printf 'Runner setting %s must be numeric.\n' "${variable}" >&2
    exit 78
  fi
done

if [[ ! -r "${GITHUB_APP_PRIVATE_KEY_FILE}" ]]; then
  printf 'GitHub App private key is not readable: %s\n' "${GITHUB_APP_PRIVATE_KEY_FILE}" >&2
  exit 78
fi

base64url() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

github_request() {
  curl --fail-with-body --silent --show-error \
    --retry 4 --retry-all-errors --retry-delay 2 \
    --header 'Accept: application/vnd.github+json' \
    --header "Authorization: Bearer ${1}" \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    "${@:2}"
}

issued_at=$(( $(date +%s) - 60 ))
expires_at=$(( issued_at + 600 ))
header=$(printf '%s' '{"alg":"RS256","typ":"JWT"}' | base64url)
payload=$(printf '{"iat":%s,"exp":%s,"iss":"%s"}' \
  "${issued_at}" "${expires_at}" "${GITHUB_APP_ID}" | base64url)
unsigned_token="${header}.${payload}"
signature=$(printf '%s' "${unsigned_token}" \
  | openssl dgst -sha256 -sign "${GITHUB_APP_PRIVATE_KEY_FILE}" -binary \
  | base64url)
app_jwt="${unsigned_token}.${signature}"

installation_response=$(github_request "${app_jwt}" \
  --request POST \
  "https://api.github.com/app/installations/${GITHUB_APP_INSTALLATION_ID}/access_tokens")
installation_token=$(jq -er '.token' <<<"${installation_response}")

runner_name="${GITHUB_RUNNER_NAME_PREFIX:-orux}-${HOSTNAME}-$(date +%s)"
labels_json=$(jq -cn --arg labels "${GITHUB_RUNNER_LABELS:-orux-ci,linux,x64}" \
  '$labels | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))')
jit_payload=$(jq -cn \
  --arg name "${runner_name}" \
  --argjson group_id "${GITHUB_RUNNER_GROUP_ID}" \
  --argjson labels "${labels_json}" \
  '{name: $name, runner_group_id: $group_id, labels: $labels, work_folder: "_work"}')

jit_response=$(github_request "${installation_token}" \
  --request POST \
  --header 'Content-Type: application/json' \
  --data "${jit_payload}" \
  "https://api.github.com/orgs/${GITHUB_ORG}/actions/runners/generate-jitconfig")
jit_config=$(jq -er '.encoded_jit_config' <<<"${jit_response}")

unset app_jwt installation_token installation_response jit_payload jit_response signature unsigned_token

printf 'Starting ephemeral GitHub runner %s for %s\n' "${runner_name}" "${GITHUB_ORG}"

# Recreate the installation as the unprivileged job user. /runner is tmpfs,
# so a stopped runner leaves no checkout or runner credentials on disk.
exec gosu runner:docker bash -c '
  set -Eeuo pipefail
  find /runner -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  cp -a --no-preserve=ownership /home/runner/. /runner/
  exec /runner/run.sh --jitconfig "$1"
' orux-runner "${jit_config}"

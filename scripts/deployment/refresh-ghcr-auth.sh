#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Ejecutar con sudo: sudo %s\n' "$0" >&2
  exit 1
fi

project_dir=$(cd -- "$(dirname -- "$0")/../.." && pwd)
deployer_user=${SUDO_USER:-fedemarkoo}
source_token="/home/${deployer_user}/.config/orux/ghcr-token"
target_token="/etc/orux/secrets/ghcr-token"
env_file="${project_dir}/.env"

if [[ ! -s ${source_token} ]]; then
  printf 'No existe el token fuente: %s\n' "${source_token}" >&2
  exit 1
fi

install -d -o "${deployer_user}" -g "${deployer_user}" -m 0700 /etc/orux/secrets
install -o "${deployer_user}" -g "${deployer_user}" -m 0400 "${source_token}" "${target_token}"

python3 - "${env_file}" "${target_token}" <<'PY'
from pathlib import Path
import sys

env_file, token_file = map(Path, sys.argv[1:])
lines = env_file.read_text().splitlines()
lines = [line for line in lines if not line.startswith("GHCR_TOKEN_FILE=")]
lines.append(f"GHCR_TOKEN_FILE={token_file}")
if not any(line.startswith("GHCR_USERNAME=") for line in lines):
    lines.append("GHCR_USERNAME=FedeMarkoo")
env_file.write_text("\n".join(lines) + "\n")
PY

systemctl restart orux-deployer.service
sleep 15
systemctl --no-pager --full status orux-deployer.service | sed -n '1,30p'
printf '\nÚltimos eventos del autodeployer:\n'
journalctl -u orux-deployer.service --since '30 seconds ago' --no-pager \
  | grep -E 'GHCR|Pulling|Pulled|unauthorized|403|Deployment stopped|Orux stack deployed|Deployment metadata' \
  | tail -80 || true

printf '\nSecreto instalado: '
stat -c '%U:%G %a %n' "${target_token}"

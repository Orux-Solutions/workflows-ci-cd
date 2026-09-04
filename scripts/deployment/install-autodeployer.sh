#!/usr/bin/env bash
set -Eeuo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="${ORUX_COMPOSE:-${project_dir}/compose.yaml}"; env_file="${ORUX_ENV_FILE:-${project_dir}/.env}"
user="${SUDO_USER:-$(id -un)}"; group="$(id -gn "${user}")"; target=/etc/systemd/system/orux-deployer.service
if [[ ${EUID} -ne 0 ]]; then exec sudo env ORUX_COMPOSE="${compose_file}" ORUX_ENV_FILE="${env_file}" "$0" "$@"; fi
[[ -f "${compose_file}" && -f "${env_file}" ]] || { echo "Se requieren compose.yaml y .env" >&2; exit 1; }
id -nG "${user}" | tr ' ' '\n' | grep -qx docker || { echo "${user} no pertenece al grupo docker" >&2; exit 1; }
rendered="$(mktemp)"; trap 'rm -f -- "${rendered}"' EXIT
sed -e "s|@ORUX_DIR@|${project_dir}|g" -e "s|@ORUX_COMPOSE@|${compose_file}|g" -e "s|@ORUX_ENV_FILE@|${env_file}|g" -e "s|@ORUX_USER@|${user}|g" -e "s|@ORUX_GROUP@|${group}|g" "${project_dir}/deploy/orux-deployer.service" > "${rendered}"
install -o root -g root -m 0644 "${rendered}" "${target}"; systemctl daemon-reload; systemctl enable --now orux-deployer.service
echo "Orux autodeployer instalado."

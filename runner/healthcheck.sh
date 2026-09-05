#!/usr/bin/env bash
set -euo pipefail
pgrep -u runner -f 'Runner.Listener' >/dev/null

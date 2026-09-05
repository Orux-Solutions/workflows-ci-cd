#!/usr/bin/env python3
"""Proxy runner en workflows-ci-cd para el motor canónico de auditoría técnica.

Delega la ejecución al motor canónico centralizado y versionado en:
documentaciones/skills/analisis-tecnico/scripts/audit_ecosystem.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    # Ascender hasta la raíz del ecosistema que contiene documentaciones y workflows-ci-cd
    candidate = script_dir.parent
    workspace_root = script_dir.parent.parent
    while candidate.parent != candidate:
        if (candidate / "documentaciones").is_dir() and (candidate / "business-backend").is_dir():
            workspace_root = candidate
            break
        candidate = candidate.parent

    canonical_auditor = (
        workspace_root / "documentaciones" / "skills" / "analisis-tecnico" / "scripts" / "audit_ecosystem.py"
    )
    if not canonical_auditor.exists():
        canonical_auditor = (
            workspace_root / ".agents" / "skills" / "analisis-tecnico" / "scripts" / "audit_ecosystem.py"
        )

    if not canonical_auditor.exists():
        print(f"❌ Error: No se encontró el motor canónico en: {canonical_auditor}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(canonical_auditor)] + sys.argv[1:]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())

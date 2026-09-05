#!/usr/bin/env python3
"""Audit Ecosystem — Motor Central de Auditoría Canónica y Tolerancia Cero para Orux/Aurea.

Evalúa de forma determinista y exhaustiva el 100% de las reglas exigidas por `/analisis-tecnico`
sobre todos los repositorios del ecosistema:
- documentaciones
- admin-backend
- admin-frontend
- business-backend
- business-frontend
- client-backend
- client-frontend
- workflows-ci-cd

Uso:
  python3 audit_ecosystem.py [--fast | --full] [--repo <nombre>] [--format <markdown|json>] [--ci]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# Constantes y Clasificación Canónica
STATUS_PASS = "🟢 CUMPLE"
STATUS_FAIL = "🔴 DESVÍO CRÍTICO"
STATUS_UNCERTAIN = "🟡 NO DEFINIDO / LEVANTAR DUDA"
STATUS_UNVERIFIABLE = "⚪ NO VERIFICABLE"


@dataclasses.dataclass
class Finding:
    repo: str
    file_path: str
    line_number: int | None
    dimension: str  # e.g., 'Isomorfismo', 'Tenancy y Seguridad', 'Bounded Context', 'Build y Tests', 'Theming'
    status: str     # STATUS_*
    rule: str
    detail: str


@dataclasses.dataclass
class RepoSummary:
    name: str
    isomorphism_status: str = STATUS_PASS
    tenancy_status: str = STATUS_PASS
    bounded_context_status: str = STATUS_PASS
    build_test_status: str = STATUS_PASS
    findings: list[Finding] = dataclasses.field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0


class EcosystemAuditor:
    def __init__(self, root_dir: Path, mode: str = "fast", target_repo: str = "all"):
        self.root = root_dir.resolve()
        self.mode = mode  # 'fast' (static analysis only) or 'full' (includes build/test execution)
        self.target_repo = target_repo
        self.canonical_sections: dict[str, set[str]] = {}
        self.canonical_pages_info: dict[str, dict] = {}
        self.canonical_areas: dict[str, dict] = {}
        self.canonical_paths: dict[str, str] = {}
        self.repo_summaries: dict[str, RepoSummary] = {}
        self.all_findings: list[Finding] = []

        self.repo_names = [
            "documentaciones",
            "admin-backend",
            "admin-frontend",
            "business-backend",
            "business-frontend",
            "client-backend",
            "client-frontend",
            "workflows-ci-cd",
        ]

        for r in self.repo_names:
            self.repo_summaries[r] = RepoSummary(name=r)

    def resolve_repo_path(self, repo_name: str) -> Path:
        return self.root / repo_name

    def load_canonical_taxonomy(self) -> None:
        """Carga la taxonomía desde documentaciones como la Fuente de la Verdad Absoluta."""
        doc_dir = self.resolve_repo_path("documentaciones")
        struct_file = doc_dir / "docs" / "modules-dynamic" / "taxonomy" / "structure.json"
        area_file = doc_dir / "docs" / "modules-dynamic" / "taxonomy" / "area.json"

        if not struct_file.exists():
            self.add_finding(
                repo="documentaciones",
                file_path="docs/modules-dynamic/taxonomy/structure.json",
                line=1,
                dim="Taxonomía",
                status=STATUS_FAIL,
                rule="Fuente de Verdad Absoluta",
                detail="El archivo canónico structure.json no existe en el repositorio documentaciones.",
            )
            return

        try:
            struct_data = json.loads(struct_file.read_text(encoding="utf-8"))
            sections_dict = struct_data.get("sections", {})
            for sec_key, sec_val in sections_dict.items():
                self.canonical_sections[sec_key] = set(sec_val.get("pages", {}).keys())
                for page_key, page_val in sec_val.get("pages", {}).items():
                    p_path = page_val.get("path") or f"/{sec_key}/{page_key}"
                    self.canonical_paths[f"{sec_key}.{page_key}"] = p_path
                    self.canonical_pages_info[f"{sec_key}.{page_key}"] = page_val
        except Exception as exc:
            self.add_finding(
                repo="documentaciones",
                file_path="docs/modules-dynamic/taxonomy/structure.json",
                line=1,
                dim="Taxonomía",
                status=STATUS_FAIL,
                rule="Taxonomía Válida",
                detail=f"Error parseando structure.json: {exc}",
            )

        if area_file.exists():
            try:
                area_data = json.loads(area_file.read_text(encoding="utf-8"))
                self.canonical_areas = area_data.get("areas", {})
            except Exception as exc:
                self.add_finding(
                    repo="documentaciones",
                    file_path="docs/modules-dynamic/taxonomy/area.json",
                    line=1,
                    dim="Taxonomía",
                    status=STATUS_FAIL,
                    rule="Taxonomía Válida",
                    detail=f"Error parseando area.json: {exc}",
                )

    def add_finding(
        self,
        repo: str,
        file_path: str,
        line: int | None,
        dim: str,
        status: str,
        rule: str,
        detail: str,
    ) -> None:
        finding = Finding(
            repo=repo,
            file_path=file_path,
            line_number=line,
            dimension=dim,
            status=status,
            rule=rule,
            detail=detail,
        )
        self.all_findings.append(finding)
        if repo in self.repo_summaries:
            summary = self.repo_summaries[repo]
            summary.findings.append(finding)
            if status == STATUS_FAIL:
                if "Isomorfismo" in dim or "Jerarquía" in dim or "Rutas" in dim:
                    summary.isomorphism_status = STATUS_FAIL
                elif "Tenancy" in dim or "Seguridad" in dim or "Scopes" in dim:
                    summary.tenancy_status = STATUS_FAIL
                elif "Bounded" in dim or "Cohesión" in dim:
                    summary.bounded_context_status = STATUS_FAIL
                elif "Build" in dim or "Test" in dim or "Lint" in dim:
                    summary.build_test_status = STATUS_FAIL
            elif status == STATUS_UNCERTAIN:
                if summary.isomorphism_status != STATUS_FAIL and ("Isomorfismo" in dim or "Jerarquía" in dim):
                    summary.isomorphism_status = STATUS_UNCERTAIN
                if summary.tenancy_status != STATUS_FAIL and ("Tenancy" in dim or "Seguridad" in dim):
                    summary.tenancy_status = STATUS_UNCERTAIN

    # =========================================================================
    # 1. AUDITORÍA DE ISOMORFISMO Y JERARQUÍA EN 3 NIVELES (Sección -> Página -> Módulo)
    # =========================================================================

    def audit_isomorphism_business_backend(self) -> None:
        repo = "business-backend"
        rpath = self.resolve_repo_path(repo)
        sections_dir = rpath / "src" / "tenant" / "sections"
        if not sections_dir.exists():
            self.add_finding(
                repo=repo,
                file_path="src/tenant/sections",
                line=1,
                dim="Isomorfismo y Jerarquía",
                status=STATUS_FAIL,
                rule="Jerarquía Canónica 3 Niveles",
                detail="Directorio src/tenant/sections no existe.",
            )
            return

        # 1. Validar nombres de carpetas de secciones
        for sec_dir in sections_dir.iterdir():
            if not sec_dir.is_dir() or sec_dir.name.startswith("."):
                continue
            if sec_dir.name not in self.canonical_sections:
                self.add_finding(
                    repo=repo,
                    file_path=str(sec_dir.relative_to(rpath)),
                    line=1,
                    dim="Isomorfismo y Jerarquía",
                    status=STATUS_FAIL,
                    rule="Secciones Canónicas",
                    detail=f"Sección '{sec_dir.name}' no está registrada en taxonomy/structure.json.",
                )
                continue

            allowed_pages = self.canonical_sections[sec_dir.name]
            for page_dir in sec_dir.iterdir():
                if not page_dir.is_dir() or page_dir.name.startswith((".", "dto", "contracts", "manifests")):
                    continue
                if page_dir.name not in allowed_pages:
                    self.add_finding(
                        repo=repo,
                        file_path=str(page_dir.relative_to(rpath)),
                        line=1,
                        dim="Isomorfismo y Jerarquía",
                        status=STATUS_FAIL,
                        rule="Páginas Canónicas",
                        detail=f"Página '{page_dir.name}' en sección '{sec_dir.name}' no pertenece a taxonomy/structure.json.",
                    )

        # 2. Validar decoradores @FeatureDomain y guards en controladores
        domain_pattern = re.compile(r"@FeatureDomain\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
        auth_guard_pattern = re.compile(r"@(Require(Read|Write|Feature|Permissions)|Roles|Public|IsPublic)\s*\(")

        for c_file in sections_dir.rglob("*.controller.ts"):
            rel_file = str(c_file.relative_to(rpath))
            parts = c_file.relative_to(sections_dir).parts
            content = c_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            if len(parts) >= 2:
                section, page = parts[0], parts[1]
                expected_domain = f"{section}.{page}"

                # Chequear @FeatureDomain
                match = domain_pattern.search(content)
                if not match:
                    self.add_finding(
                        repo=repo,
                        file_path=rel_file,
                        line=1,
                        dim="Isomorfismo y Jerarquía",
                        status=STATUS_FAIL,
                        rule="Decorador @FeatureDomain",
                        detail=f"Controlador no declara @FeatureDomain('{expected_domain}').",
                    )
                else:
                    found_domain = match.group(1)
                    valid_domains = {expected_domain, page, f"public.{page}", f"{expected_domain}.public"}
                    if found_domain not in valid_domains and not found_domain.startswith(f"{expected_domain}."):
                        line_no = next((i + 1 for i, l in enumerate(lines) if match.group(0) in l), 1)
                        self.add_finding(
                            repo=repo,
                            file_path=rel_file,
                            line=line_no,
                            dim="Isomorfismo y Jerarquía",
                            status=STATUS_FAIL,
                            rule="Decorador @FeatureDomain",
                            detail=f"Declara @FeatureDomain('{found_domain}') pero debe coincidir con '{expected_domain}'.",
                        )

            # Chequear presencia de guards de capability o lectura/escritura en la clase o métodos
            has_auth = bool(auth_guard_pattern.search(content))
            if not has_auth:
                self.add_finding(
                    repo=repo,
                    file_path=rel_file,
                    line=1,
                    dim="Tenancy y Seguridad",
                    status=STATUS_FAIL,
                    rule="Guards de Autorización Obligatorios",
                    detail="Controlador no declara @RequireFeature(), @RequireRead()/@RequireWrite(), @Roles() ni @Public().",
                )

    def audit_isomorphism_business_frontend(self) -> None:
        repo = "business-frontend"
        rpath = self.resolve_repo_path(repo)
        sections_dir = rpath / "src" / "tenant" / "sections"
        if not sections_dir.exists():
            return

        for sec_dir in sections_dir.iterdir():
            if not sec_dir.is_dir() or sec_dir.name.startswith("."):
                continue
            if sec_dir.name not in self.canonical_sections:
                self.add_finding(
                    repo=repo,
                    file_path=str(sec_dir.relative_to(rpath)),
                    line=1,
                    dim="Isomorfismo y Jerarquía",
                    status=STATUS_FAIL,
                    rule="Secciones Canónicas Frontend",
                    detail=f"Sección '{sec_dir.name}' no está registrada en taxonomy/structure.json.",
                )
                continue

            allowed_pages = self.canonical_sections[sec_dir.name]
            for page_dir in sec_dir.iterdir():
                if not page_dir.is_dir() or page_dir.name.startswith((".", "components")):
                    continue
                if page_dir.name not in allowed_pages:
                    self.add_finding(
                        repo=repo,
                        file_path=str(page_dir.relative_to(rpath)),
                        line=1,
                        dim="Isomorfismo y Jerarquía",
                        status=STATUS_FAIL,
                        rule="Páginas Canónicas Frontend",
                        detail=f"Página '{page_dir.name}' en sección '{sec_dir.name}' no pertenece a taxonomy/structure.json.",
                    )

        # Chequear features.ts
        feature_pattern = re.compile(r"['\"]([a-zA-Z0-9_-]+\.[a-zA-Z0-9_.-]+)['\"]")
        for f_file in sections_dir.rglob("features.ts"):
            rel_file = str(f_file.relative_to(rpath))
            parts = f_file.relative_to(sections_dir).parts
            if len(parts) >= 2 and parts[0] in self.canonical_sections:
                section, page = parts[0], parts[1]
                content = f_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                for line_idx, line_content in enumerate(lines, 1):
                    for match in feature_pattern.finditer(line_content):
                        key = match.group(1)
                        if key.startswith("api/") or key.startswith("http"):
                            continue
                        valid_prefixes = (f"{section}.{page}.", f"{page}.", f"{section}.{page}")
                        if not any(key.startswith(p) for p in valid_prefixes):
                            self.add_finding(
                                repo=repo,
                                file_path=rel_file,
                                line=line_idx,
                                dim="Isomorfismo y Jerarquía",
                                status=STATUS_FAIL,
                                rule="Isomorfismo de Features Frontend",
                                detail=f"Clave de feature '{key}' no pertenece al namespace de '{section}.{page}'.",
                            )

    # =========================================================================
    # 2. AUDITORÍA DE RUTAS JERÁRQUICAS (Prohibición de Rutas Planas)
    # =========================================================================

    def audit_hierarchical_routes(self) -> None:
        page_to_section: dict[str, str] = {}
        for sec, pages in self.canonical_sections.items():
            for p in pages:
                page_to_section[p] = sec

        for repo_name in ["business-frontend", "admin-frontend", "client-frontend"]:
            rpath = self.resolve_repo_path(repo_name)
            if not rpath.exists():
                continue

            app_files = list(rpath.glob("src/**/App.tsx")) + list(rpath.glob("src/**/routes.tsx")) + list(rpath.glob("src/**/router.tsx"))
            for app_file in app_files:
                rel_file = str(app_file.relative_to(rpath))
                content = app_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                route_pattern = re.compile(r'<Route\s+path=["\']([^"\']+)["\']')

                for line_idx, line_content in enumerate(lines, 1):
                    for match in route_pattern.finditer(line_content):
                        path_val = match.group(1).strip("/")
                        if not path_val or path_val in (
                            "login", "register", "auth/magic", "auth/google/callback",
                            "auth/forgot-password", "auth/reset-password", "unauthorized",
                            "settings", "profile", "onboarding"
                        ) or path_val.startswith(("public/", "superadmin", "preview/", "platform/")):
                            continue

                        parts = path_val.split("/")
                        if len(parts) == 1:
                            p_key = parts[0]
                            if p_key in page_to_section:
                                sec = page_to_section[p_key]
                                canonical = self.canonical_paths.get(f"{sec}.{p_key}", f"/{sec}/{p_key}")
                                self.add_finding(
                                    repo=repo_name,
                                    file_path=rel_file,
                                    line=line_idx,
                                    dim="Isomorfismo y Jerarquía",
                                    status=STATUS_FAIL,
                                    rule="Ruta Jerárquica Obligatoria (Regla 4.5)",
                                    detail=f"Ruta plana prohibida path='{match.group(1)}'. Debe ser '{canonical}'.",
                                )
                        elif len(parts) >= 2:
                            sec, page = parts[0], parts[1]
                            if sec in self.canonical_sections and page not in self.canonical_sections[sec]:
                                self.add_finding(
                                    repo=repo_name,
                                    file_path=rel_file,
                                    line=line_idx,
                                    dim="Isomorfismo y Jerarquía",
                                    status=STATUS_FAIL,
                                    rule="Ruta Jerárquica Válida",
                                    detail=f"Ruta '{match.group(1)}' no pertenece a la sección canónica '{sec}'.",
                                )

    # =========================================================================
    # 3. AUDITORÍA DE TENANCY, SEGURIDAD Y AISLAMIENTO DE DATOS
    # =========================================================================

    def audit_tenancy_business_backend(self) -> None:
        repo = "business-backend"
        rpath = self.resolve_repo_path(repo)
        if not rpath.exists():
            return

        # 1. Chequear inyección prohibida de tenantId por Body en controladores
        c_files = list((rpath / "src" / "tenant").rglob("*.controller.ts"))
        body_tenant_pattern = re.compile(r"@Body\s*\(\s*['\"]tenantId['\"]\s*\)")

        for c_file in c_files:
            rel_file = str(c_file.relative_to(rpath))
            content = c_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_idx, line in enumerate(lines, 1):
                if body_tenant_pattern.search(line):
                    self.add_finding(
                        repo=repo,
                        file_path=rel_file,
                        line=line_idx,
                        dim="Tenancy y Seguridad",
                        status=STATUS_FAIL,
                        rule="Aislamiento Multi-Tenant",
                        detail="Prohibido aceptar @Body('tenantId') como fuente de autorización. Debe provenir del JWT/request.",
                    )

        # 2. Chequear que los servicios operacionales incluyan filtro tenantId en consultas Prisma
        s_files = list((rpath / "src" / "tenant" / "sections").rglob("*.service.ts"))
        prisma_op_pattern = re.compile(r"this\.prisma\.([a-zA-Z0-9_]+)\.(findMany|findFirst|update|updateMany|delete|deleteMany|count)\s*\(\s*\{")

        for s_file in s_files:
            rel_file = str(s_file.relative_to(rpath))
            content = s_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_idx, line in enumerate(lines, 1):
                match = prisma_op_pattern.search(line)
                if match:
                    model, op = match.group(1), match.group(2)
                    if model in ("systemSetting", "platformPlan", "platformModule", "tenant"):
                        continue
                    # Extraer el bloque de la consulta (próximas 15 líneas)
                    block = "\n".join(lines[line_idx - 1 : min(len(lines), line_idx + 15)])
                    
                    # Si no tiene tenantId en el bloque directo where:
                    if "where:" in block and "tenantId" not in block:
                        # Verificar si en las líneas previas del mismo método ya se filtró por tenantId
                        preceding_scope = "\n".join(lines[max(0, line_idx - 25) : line_idx])
                        if "tenantId" in preceding_scope and ("findFirst" in preceding_scope or "findUnique" in preceding_scope):
                            continue  # El ID ya fue validado con tenantId previamente en este flujo

                        self.add_finding(
                            repo=repo,
                            file_path=rel_file,
                            line=line_idx,
                            dim="Tenancy y Seguridad",
                            status=STATUS_FAIL,
                            rule="Filtro tenantId Obligatorio",
                            detail=f"Consulta prisma.{model}.{op} no incluye 'tenantId' en el bloque where ni cuenta con validación previa de tenantId.",
                        )

        # 3. Chequear retorno opaco 403 ante tenant mismatch
        mismatch_404_pattern = re.compile(r"if\s*\(.*tenantId.*\)\s*\{\s*throw\s+new\s+NotFoundException")
        for s_file in s_files:
            rel_file = str(s_file.relative_to(rpath))
            content = s_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                if mismatch_404_pattern.search(line):
                    self.add_finding(
                        repo=repo,
                        file_path=rel_file,
                        line=line_idx,
                        dim="Tenancy y Seguridad",
                        status=STATUS_FAIL,
                        rule="403 Opaco ante Acceso Cruzado",
                        detail="Uso de NotFoundException ante validación de tenantId. Debe retornar ForbiddenException (403).",
                    )

    # =========================================================================
    # 4. AUDITORÍA DE SEGREGACIÓN DE SCOPES (Platform vs Tenant)
    # =========================================================================

    def audit_platform_scope(self) -> None:
        repo = "admin-backend"
        rpath = self.resolve_repo_path(repo)
        if not rpath.exists():
            return

        # 1. Chequear que endpoints mutantes en admin-backend no permitan platform_readonly
        c_files = list(rpath.glob("src/**/*.controller.ts"))
        mutation_pattern = re.compile(r"@(Post|Put|Patch|Delete)\s*\(")
        roles_pattern = re.compile(r"@Roles\s*\(\s*([^)]+)\s*\)")

        for c_file in c_files:
            rel_file = str(c_file.relative_to(rpath))
            content = c_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_idx, line in enumerate(lines, 1):
                if mutation_pattern.search(line):
                    preceding = "\n".join(lines[max(0, line_idx - 6) : line_idx])
                    roles_match = roles_pattern.search(preceding)
                    if roles_match:
                        roles = roles_match.group(1)
                        if "platform_readonly" in roles:
                            self.add_finding(
                                repo=repo,
                                file_path=rel_file,
                                line=line_idx,
                                dim="Segregación de Scopes",
                                status=STATUS_FAIL,
                                rule="Segregación platform_readonly",
                                detail="Método mutante permite el rol 'platform_readonly'. Debe restringirse a 'platform_owner'.",
                            )

        # 2. Chequear que admin-backend no importe módulos operativos de business-backend
        for ts_file in rpath.rglob("*.ts"):
            if "node_modules" in ts_file.parts or "dist" in ts_file.parts:
                continue
            content = ts_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                if "business-backend" in line:
                    self.add_finding(
                        repo=repo,
                        file_path=str(ts_file.relative_to(rpath)),
                        line=line_idx,
                        dim="Segregación de Scopes",
                        status=STATUS_FAIL,
                        rule="Aislamiento Platform vs Tenant",
                        detail="Importación prohibida de business-backend en admin-backend.",
                    )

        # 3. Chequear prefijo global /api en main.ts (Decisión #4)
        main_file = rpath / "src" / "main.ts"
        if main_file.exists():
            main_content = main_file.read_text(encoding="utf-8")
            if "setGlobalPrefix('api/v1')" in main_content or 'setGlobalPrefix("api/v1")' in main_content:
                self.add_finding(
                    repo=repo,
                    file_path="src/main.ts",
                    line=1,
                    dim="Isomorfismo y Jerarquía",
                    status=STATUS_FAIL,
                    rule="Prefijo de API Unificado (/api)",
                    detail="admin-backend usa prefijo 'api/v1' en lugar del canónico unificado 'api'.",
                )

    # =========================================================================
    # 5. AUDITORÍA DE THEMING Y FRONTEND
    # =========================================================================

    def audit_theming_and_frontend(self) -> None:
        for repo in ["client-frontend", "business-frontend"]:
            rpath = self.resolve_repo_path(repo)
            if not rpath.exists():
                continue

            for css_file in rpath.rglob("*.css"):
                if "tenant-" in css_file.name:
                    self.add_finding(
                        repo=repo,
                        file_path=str(css_file.relative_to(rpath)),
                        line=1,
                        dim="Theming y Frontend",
                        status=STATUS_FAIL,
                        rule="Multi-tenancy Theming Dinámico",
                        detail=f"Archivo CSS estático por tenant detectado: {css_file.name}. Prohibido CSS estático por tenant.",
                    )

            for f in rpath.rglob("*.[tj]sx"):
                if "node_modules" in f.parts or "dist" in f.parts:
                    continue
                content = f.read_text(encoding="utf-8")
                lines = content.splitlines()
                for line_idx, line in enumerate(lines, 1):
                    if any(sec in line for sec in ["PLATFORM_SECRET", "JWT_SECRET", "ADMIN_TOKEN"]):
                        self.add_finding(
                            repo=repo,
                            file_path=str(f.relative_to(rpath)),
                            line=line_idx,
                            dim="Tenancy y Seguridad",
                            status=STATUS_FAIL,
                            rule="Fuga de Secretos de Plataforma",
                            detail="Referencia a secreto de plataforma detectada en frontend público.",
                        )

    # =========================================================================
    # 6. AUDITORÍA DE BOUNDED CONTEXT Y GOD SERVICES
    # =========================================================================

    def audit_bounded_context_and_cohesion(self) -> None:
        for repo in ["business-backend", "admin-backend", "client-backend"]:
            rpath = self.resolve_repo_path(repo)
            src_dir = rpath / "src"
            if not src_dir.exists():
                continue

            service_files = list(src_dir.rglob("*.service.ts"))
            for s_file in service_files:
                rel_file = str(s_file.relative_to(rpath))
                content = s_file.read_text(encoding="utf-8")

                imported_sections = set()
                for sec in self.canonical_sections:
                    if f"/sections/{sec}/" in content or f"'{sec}/" in content:
                        imported_sections.add(sec)

                if len(imported_sections) > 1:
                    self.add_finding(
                        repo=repo,
                        file_path=rel_file,
                        line=1,
                        dim="Bounded Context y Cohesión de Servicios",
                        status=STATUS_FAIL,
                        rule="Prohibición de God Services",
                        detail=f"Servicio concentra múltiples dominios disjuntos: {sorted(imported_sections)}.",
                    )

    # =========================================================================
    # 6.1. AUDITORÍA DE CERO HARDCODEO EN CATÁLOGOS Y MÓDULOS (Regla 2: 100% en BD)
    # =========================================================================

    def audit_no_hardcoded_catalogs(self) -> None:
        """Verifica que ningún servicio defina listas o arrays estáticos/hardcodeados de módulos."""
        hardcode_patterns = [
            re.compile(r"(standardModules|defaultModules|hardcodedModules|staticModules)\s*=\s*\["),
            re.compile(r"const\s+[a-zA-Z0-9_]*modules\s*=\s*\[\s*\{[^}]*key:\s*['\"][a-zA-Z0-9_-]+['\"]", re.IGNORECASE),
        ]

        for repo in ["business-backend", "admin-backend", "client-backend"]:
            rpath = self.resolve_repo_path(repo)
            src_dir = rpath / "src"
            if not src_dir.exists():
                continue

            for ts_file in src_dir.rglob("*.ts"):
                if any(x in ts_file.name for x in [".spec.", ".test.", "sync-taxonomy"]):
                    continue
                content = ts_file.read_text(encoding="utf-8")
                lines = content.splitlines()

                for line_idx, line in enumerate(lines, 1):
                    for pat in hardcode_patterns:
                        if pat.search(line):
                            self.add_finding(
                                repo=repo,
                                file_path=str(ts_file.relative_to(rpath)),
                                line=line_idx,
                                dim="Isomorfismo y Jerarquía",
                                status=STATUS_FAIL,
                                rule="Prohibición de Catálogo Hardcodeado (Regla 2: 100% en BD)",
                                detail=f"Definición estática de módulos detectada en servicio ('{line.strip()}'). Los módulos y textos deben residir y consultarse exclusivamente desde MongoDB (module_catalog).",
                            )

    # =========================================================================
    # 7. EJECUCIÓN O VERIFICACIÓN DE BUILDS, TIPADO Y TESTS
    # =========================================================================

    def run_command(self, cmd: list[str], cwd: Path) -> tuple[int, str, str]:
        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "Comando excedió el tiempo límite (120s)."
        except Exception as exc:
            return 1, "", str(exc)

    def audit_builds_and_tests(self) -> None:
        for repo in self.repo_names:
            if self.target_repo != "all" and self.target_repo != repo:
                continue

            rpath = self.resolve_repo_path(repo)
            if not rpath.exists():
                continue

            summary = self.repo_summaries[repo]
            pkg_file = rpath / "package.json"
            if not pkg_file.exists():
                continue

            try:
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            scripts = pkg.get("scripts", {})

            if self.mode == "fast":
                has_build = "build" in scripts
                has_test = "test" in scripts
                if not has_build and repo not in ("workflows-ci-cd", "documentaciones"):
                    self.add_finding(
                        repo=repo,
                        file_path="package.json",
                        line=1,
                        dim="Build, Lint y Pruebas",
                        status=STATUS_FAIL,
                        rule="Script de Build",
                        detail="Falta script 'build' en package.json.",
                    )
                if not has_test and repo not in ("workflows-ci-cd", "documentaciones", "business-frontend", "client-frontend"):
                    self.add_finding(
                        repo=repo,
                        file_path="package.json",
                        line=1,
                        dim="Build, Lint y Pruebas",
                        status=STATUS_UNCERTAIN,
                        rule="Script de Tests",
                        detail="Falta script 'test' en package.json.",
                    )
                continue

            print(f"⚙️ [{repo}] Ejecutando validación completa (Build & Tests)...", flush=True)

            if (rpath / "prisma" / "schema.prisma").exists():
                code, out, err = self.run_command(["npx", "prisma", "generate"], rpath)
                if code != 0:
                    self.add_finding(
                        repo=repo,
                        file_path="prisma/schema.prisma",
                        line=1,
                        dim="Build, Lint y Pruebas",
                        status=STATUS_FAIL,
                        rule="Compilación Prisma",
                        detail=f"Fallo 'prisma generate': {err.strip() or out.strip()}",
                    )

            if "build" in scripts:
                code, out, err = self.run_command(["npm", "run", "build"], rpath)
                if code != 0:
                    self.add_finding(
                        repo=repo,
                        file_path="package.json",
                        line=1,
                        dim="Build, Lint y Pruebas",
                        status=STATUS_FAIL,
                        rule="Compilación y Tipado (Build)",
                        detail=f"Fallo 'npm run build': {err.strip() or out.strip()[:300]}",
                    )

            if "test" in scripts:
                code, out, err = self.run_command(["npm", "test", "--", "--run"], rpath)
                test_output = out + err

                passed_match = re.search(r"(\d+)\s+passed", test_output)
                failed_match = re.search(r"(\d+)\s+failed", test_output)
                if passed_match:
                    summary.tests_passed = int(passed_match.group(1))
                if failed_match:
                    summary.tests_failed = int(failed_match.group(1))

                if code != 0 or summary.tests_failed > 0:
                    self.add_finding(
                        repo=repo,
                        file_path="test",
                        line=1,
                        dim="Build, Lint y Pruebas",
                        status=STATUS_FAIL,
                        rule="Ejecución de Tests",
                        detail=f"Tests fallaron ({summary.tests_failed} fallas). Salida: {test_output[-400:].strip()}",
                    )

    # =========================================================================
    # 8. AUDITORÍA INTEGRAL Y COORDINACIÓN
    # =========================================================================

    def run_all_checks(self) -> None:
        self.load_canonical_taxonomy()

        if self.target_repo in ("all", "business-backend"):
            self.audit_isomorphism_business_backend()
            self.audit_tenancy_business_backend()

        if self.target_repo in ("all", "business-frontend"):
            self.audit_isomorphism_business_frontend()

        if self.target_repo in ("all", "business-frontend", "admin-frontend", "client-frontend"):
            self.audit_hierarchical_routes()
            self.audit_theming_and_frontend()

        if self.target_repo in ("all", "admin-backend"):
            self.audit_platform_scope()

        self.audit_bounded_context_and_cohesion()
        self.audit_no_hardcoded_catalogs()
        self.audit_builds_and_tests()

    # =========================================================================
    # 9. GENERACIÓN DEL INFORME CANÓNICO (Markdown y JSON)
    # =========================================================================

    def generate_markdown_report(self) -> str:
        total_critical = sum(1 for f in self.all_findings if f.status == STATUS_FAIL)
        total_uncertain = sum(1 for f in self.all_findings if f.status == STATUS_UNCERTAIN)

        if total_critical > 0:
            general_status = "CON DESVÍOS CRÍTICOS"
        elif total_uncertain > 0:
            general_status = "PENDIENTE DE DEFINICIÓN"
        else:
            general_status = "APROBADO"

        lines = [
            "# 🔍 Informe de Análisis Técnico Integral — Tolerancia Cero",
            "",
            "## 📋 Resumen Ejecutivo",
            f"- **Estado general del ecosistema:** {general_status}",
            f"- **Repositorios auditados:** {', '.join(self.repo_names)}",
            f"- **Total de cumplimientos:** {sum(1 for f in self.all_findings if f.status == STATUS_PASS)}",
            f"- **Total de desvíos críticos (🔴):** {total_critical}",
            f"- **Total de dudas levantadas (🟡):** {total_uncertain}",
            "",
            "---",
            "",
            "## 🔬 Detalle por Repositorio",
            "",
        ]

        for repo in self.repo_names:
            if self.target_repo != "all" and self.target_repo != repo:
                continue
            summary = self.repo_summaries[repo]
            repo_findings = [f for f in self.all_findings if f.repo == repo]

            lines.extend([
                f"### {repo}",
                f"- **Isomorfismo y Jerarquía (3 Niveles):** {summary.isomorphism_status}",
                f"- **Tenancy y Seguridad:** {summary.tenancy_status}",
                f"- **Bounded Context y Cohesión de Servicios:** {summary.bounded_context_status}",
                f"- **Build, Lint y Pruebas:** {summary.build_test_status}" + (f" ({summary.tests_passed} pasadas, {summary.tests_failed} fallidas)" if summary.tests_passed > 0 or summary.tests_failed > 0 else ""),
                "- **Hallazgos Específicos:**",
            ])

            if not repo_findings:
                lines.append("  - 🟢 100% conforme a las especificaciones documentales.")
            else:
                for f in repo_findings:
                    line_str = f":L{f.line_number}" if f.line_number else ""
                    lines.append(f"  - {f.status} `[{f.file_path}{line_str}]` **{f.rule}**: {f.detail}")

            lines.append("")

        lines.extend([
            "---",
            "",
            "## ❓ Dudas Levantadas (No Especificadas en Documentación)",
            "> [!WARNING]",
            "> Los siguientes ítems no están contemplados o presentan ambigüedades en `documentaciones`. Conforme a la regla de tolerancia cero, se levantan para definición del usuario y no han sido aprobados:",
        ])

        uncertain_findings = [f for f in self.all_findings if f.status == STATUS_UNCERTAIN]
        if not uncertain_findings:
            lines.append("1. Ninguna duda pendiente. La totalidad de los módulos y comportamientos inspeccionados cuenta con especificación canónica en `documentaciones`.")
        else:
            for idx, f in enumerate(uncertain_findings, 1):
                lines.append(f"{idx}. **[{f.repo}]** `{f.file_path}`: {f.detail}")

        lines.extend([
            "",
            "## 🚨 Matriz de Desvíos Críticos (Requieren Corrección)",
            "| Repositorio | Archivo / Componente | Regla Infringida | Impacto / Detalle |",
            "| :--- | :--- | :--- | :--- |",
        ])

        critical_findings = [f for f in self.all_findings if f.status == STATUS_FAIL]
        if not critical_findings:
            lines.append("| Ninguno | N/A | N/A | Cero desvíos críticos detectados. Todos los repositorios cumplen al 100%. |")
        else:
            for f in critical_findings:
                line_str = f":{f.line_number}" if f.line_number else ""
                lines.append(f"| `{f.repo}` | `{f.file_path}{line_str}` | {f.rule} | {f.detail} |")

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "mode": self.mode,
            "target_repo": self.target_repo,
            "summary": {
                "critical_violations": sum(1 for f in self.all_findings if f.status == STATUS_FAIL),
                "uncertainties": sum(1 for f in self.all_findings if f.status == STATUS_UNCERTAIN),
                "total_findings": len(self.all_findings),
            },
            "findings": [dataclasses.asdict(f) for f in self.all_findings],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría Canónica Automatizada de Ecosistema Orux/Aurea (Tolerancia Cero)")
    parser.add_argument("--mode", choices=["fast", "full"], default="fast", help="Modo: 'fast' (análisis estático ultra-rápido) o 'full' (ejecuta prisma, build y tests)")
    parser.add_argument("--repo", default="all", help="Repositorio específico a auditar o 'all'")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Formato del informe de salida")
    parser.add_argument("--output", help="Ruta de archivo para guardar el informe")
    parser.add_argument("--ci", action="store_true", help="Falla con exit code > 0 si hay desvíos críticos o dudas")

    args = parser.parse_args()

    current_dir = Path(__file__).resolve().parent
    workspace_root = current_dir.parent.parent.parent
    while workspace_root.name not in ("Aurea", "") and not (workspace_root / "documentaciones").exists():
        if workspace_root.parent == workspace_root:
            break
        workspace_root = workspace_root.parent

    auditor = EcosystemAuditor(root_dir=workspace_root, mode=args.mode, target_repo=args.repo)
    auditor.run_all_checks()

    if args.format == "json":
        output_content = json.dumps(auditor.to_json(), indent=2, ensure_ascii=False)
    else:
        output_content = auditor.generate_markdown_report()

    if args.output:
        Path(args.output).write_text(output_content, encoding="utf-8")
        print(f"✅ Informe de auditoría guardado en: {args.output}")
    else:
        print(output_content)

    critical_count = sum(1 for f in auditor.all_findings if f.status == STATUS_FAIL)
    uncertain_count = sum(1 for f in auditor.all_findings if f.status == STATUS_UNCERTAIN)

    if args.ci and critical_count > 0:
        return 1
    if args.ci and uncertain_count > 0:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

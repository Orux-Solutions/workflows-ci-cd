# ⚙️ Orux CI/CD & DevOps Hub (`workflows-ci-cd`)

> Repositorio centralizado de pipelines de Integración Continua, Entrega Continua, validadores arquitectónicos y gobernanza para el ecosistema Orux / Aurea.

---

> [!IMPORTANT]
> **Fuente de la Verdad Absoluta:**
> Toda la normativa de integración, gobernanza de branches, contratos de release y políticas de calidad están formalizados en el repositorio [**`documentaciones`**](../documentaciones) (especialmente [`docs/ci.md`](../documentaciones/docs/ci.md)).

---

## 📋 Arquitectura de CI Reutilizable

Los repositorios consumidores (`admin-backend`, `admin-frontend`, `business-backend`, `business-frontend`, `client-backend`, `client-frontend`, `documentaciones`) no duplican lógica de CI. Todos consumen el workflow centralizado reutilizable [`ci.yml`](.github/workflows/ci.yml):

```yaml
# .github/workflows/pr-quality.yml en cada repo
name: PR Quality
on:
  pull_request:
    branches: [main]

permissions:
  actions: read
  contents: read
  pull-requests: write
  issues: write

jobs:
  quality:
    uses: Orux-Solutions/workflows-ci-cd/.github/workflows/ci.yml@main
    with:
      project-type: node-frontend # o node-backend
```

### Perfiles Soportados:
- **`node-frontend`:** Instalación de dependencias, verificación de tipos TypeScript y build de producción con Vite.
- **`node-backend`:** Instalación de dependencias, Prisma generate, validación estática con linter, suite de tests y build de producción NestJS.
- **`docs`:** Validación de enlaces, manifests de taxonomía e integridad de gobernanza.

---

## 🛡️ Controles de Calidad Ejecutados en Cada PR

1. **Conventional Commits:** Valida que cada commit del PR cumpla el estándar (`feat:`, `fix:`, `refactor:`, etc.).
2. **Validación de Arquitectura:**
   - [`validate-architecture.py`](scripts/validate-architecture.py): Verifica la jerarquía canónica de 3 niveles (`Sección → Página → Módulo`) contra `taxonomy/structure.json` y el isomorfismo `@FeatureDomain`.
   - [`validate-services-cohesion.py`](scripts/validate-services-cohesion.py): Detecta y bloquea **God Services** o controladores multidominio garantizando Bounded Contexts puros.
3. **Validación de Gobernanza:** [`validate-governance.mjs`](scripts/validate-governance.mjs) valida coherencia de tags, releases y dependencias.
4. **Seguridad y Secretos:** Detección de credenciales y secretos con Gitleaks y Dependency Review.
5. **CodeQL:** Análisis estático avanzado de vulnerabilidades de seguridad (configurable vía `run-codeql`).
6. **PR Quality Report:** Consolida el estado de todos los controles en un único comentario interactivo e idempotente en el PR.

---

## 🏷️ Versionado Automático (Autotagging)

El workflow de release en `main` determina el próximo tag `vX.Y.Z` automáticamente analizando los commits integrados:
- `fix`, `perf` $\rightarrow$ Incrementa versión **Patch** (`v1.0.X`).
- `feat` $\rightarrow$ Incrementa versión **Minor** (`v1.X.0`).
- Breaking Changes o acumulación de 10 `feat` $\rightarrow$ Incrementa versión **Major** (`vX.0.0`).

---

## 📁 Estructura de Scripts de Validación

```text
workflows-ci-cd/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Workflow reusable central de calidad de PRs
│       ├── release.yml            # Pipeline de autotagging y GitHub Releases
│       └── notify.yml             # Notificaciones a Discord y Telegram
├── docs/
│   ├── OPERATIONS_RUNBOOK.md      # Runbook operativo para despliegues
│   └── pr-gate-contract.md        # Contrato normativo de los gates de PR
└── scripts/
    ├── validate-architecture.py   # Validador de jerarquía 3 niveles e isomorfismo
    ├── validate-services-cohesion.py # Detector de God Services y cohesión
    ├── validate-commits.sh        # Validador de Conventional Commits
    └── validate-governance.mjs    # Validador de integridad de repositorios
```

## Docker Compose modular y runners propios

El despliegue usa un único [`compose.yaml`](compose.yaml) padre con includes
recursivos para Orux, Cloudflare, monitoreo y GitHub. Requiere Docker Compose
2.20 o posterior.

- [`docs/COMPOSE_ARCHITECTURE.md`](docs/COMPOSE_ARCHITECTURE.md): módulos,
  redes, monitoreo, exposición y operación.
- [`docs/GITHUB_RUNNERS.md`](docs/GITHUB_RUNNERS.md): runners JIT aislados,
  GitHub Apps, routing, fallback, pruebas y rollback.

Portainer y cAdvisor no forman parte del stack. La versión desplegada y el
estado de cada aplicación se consultan en Admin; Prometheus/Grafana y
node-exporter cubren la salud del host. Ningún componente de monitoreo tiene
acceso al socket Docker.

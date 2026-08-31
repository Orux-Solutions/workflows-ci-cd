# Aurea CI

Workflows compartidos de integración continua para los repositorios de Aurea.

## Cómo agregar un repo

Cada aplicación sólo necesita tres workflows pequeños. No hay que copiar pasos ni inventar comandos:

```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
  push: { branches: [main] }
jobs:
  ci:
    uses: aurea-io/aurea-ci/.github/workflows/ci.yml@v1
    with:
      project-type: node-frontend
```

Perfiles disponibles:

- `node-frontend`: instala dependencias y ejecuta `npm run build`.
- `node-backend`: instala dependencias, ejecuta `npm run lint`, `npm test` y `npm run build`.
- `node-pages`: instala dependencias, ejecuta `npm run check`, `npm test` y valida el Dockerfile.

Además, cada repo agrega los workflows `security.yml`, `commit-policy.yml` y `release.yml` apuntando a `@v1`. Sus detalles viven únicamente aquí.

## Versionado automático

El autotagger usa Conventional Commits:

- `fix` y `perf` incrementan patch.
- `feat` incrementa minor.
- Un breaking change incrementa major.
- Diez `feat` desde el último tag incrementan major aunque no haya breaking change.

El umbral se puede cambiar con `AUREA_FEATURES_FOR_MAJOR`, siempre con un entero positivo.

## Regla de mantenimiento

Los cambios de CI se hacen en este repo, se prueban con `scripts/test-release-scripts.sh` y luego se actualiza el tag `v1`. Los repos de aplicación no deben contener scripts de CI propios.

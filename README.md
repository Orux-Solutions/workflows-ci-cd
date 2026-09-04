# Orux CI

Workflows compartidos de integración continua para los repositorios de Orux.

## Cómo agregar un repo

Cada aplicación sólo necesita callers pequeños. No hay que copiar pasos ni inventar comandos; el workflow de CI compartido incluye el gate de calidad y los controles de seguridad:

```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
  push: { branches: [main] }
jobs:
  ci:
    uses: Orux-Solutions/orux-ci/.github/workflows/ci.yml@main
    with:
      project-type: node-frontend
```

Perfiles disponibles:

- `node-frontend`: instala dependencias y ejecuta `npm run build`.
- `node-backend`: instala dependencias, ejecuta `npm run lint`, `npm test` y `npm run build`.
- `node-pages`: instala dependencias, ejecuta `npm run check`, `npm test` y valida el Dockerfile.

Además, cada repo agrega los workflows `security.yml`, `commit-policy.yml` y `release.yml` apuntando a `@main`, que representa la versión latest del CI compartido.

## Notificaciones cross-repo

Las notificaciones de imágenes publicadas y despliegues se centralizan en
`.github/workflows/notify.yml`. Los repositorios consumidores sólo deben llamar
al workflow reutilizable con `secrets: inherit`; los valores deben existir como
secretos de la organización `Orux-Solutions`, nunca en el código.

Secretos soportados:

- `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
- `DISCORD_BOT_TOKEN` y `DISCORD_CHANNEL_ID`, o `DISCORD_WEBHOOK_URL`.

Variables opcionales de organización:

- `ORUX_DEPLOY_URL`: URL pública común o por repositorio para incluir en avisos.

Los repos nuevos deben copiar únicamente los callers documentados en
`docs/consumer-workflows.yml` y apuntar a la referencia latest (`@main`).

## Versionado automático

El autotagger usa Conventional Commits:

- `fix` y `perf` incrementan patch.
- `feat` incrementa minor.
- Un breaking change incrementa major.
- Diez `feat` desde el último tag incrementan major aunque no haya breaking change.

El umbral se puede cambiar con `ORUX_FEATURES_FOR_MAJOR`, siempre con un entero positivo.

## Regla de mantenimiento

Los cambios de CI se hacen en este repo, se prueban con `scripts/test-release-scripts.sh` y luego se actualiza el tag `v1`. Los repos de aplicación no deben contener scripts de CI propios.

## Autodeployer local

Para instalaciones Orux con un `compose.yaml` en servidor propio, el autodeployer
periódicamente hace pull, recrea los servicios configurados y valida un endpoint
de salud. Se ejecuta una vez con `--once` o en modo continuo con `--interval`:

```bash
ORUX_DEPLOY_SERVICES="backend frontend" \
python3 scripts/deployment/local-deployer.py \
  --compose /srv/orux/compose.yaml --env-file /srv/orux/.env \
  --health-url http://127.0.0.1/health --once
```

En Linux se puede instalar como servicio con `sudo scripts/deployment/install-autodeployer.sh`.
Es opcional y no reemplaza el despliegue existente a Render.

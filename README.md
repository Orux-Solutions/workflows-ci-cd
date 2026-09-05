# Orux CI

Workflows compartidos de integración continua para los repositorios de Orux.

## Cómo agregar un repo

Cada aplicación sólo necesita callers pequeños. No hay que copiar pasos ni inventar comandos; el workflow de CI compartido incluye el gate de calidad y los controles de seguridad:

```yaml
# .github/workflows/pr-quality.yml
name: CI
on:
  pull_request:
jobs:
  quality:
    uses: Orux-Solutions/workflows-ci-cd/.github/workflows/ci.yml@main
    with:
      project-type: node-frontend
```

Perfiles disponibles:

- `node-frontend`: instala dependencias y ejecuta `npm run build`.
- `node-backend`: instala dependencias, ejecuta `npm run lint`, `npm test` y `npm run build`.
- `node-pages`: instala dependencias, ejecuta `npm run check`, `npm test` y valida el Dockerfile.

Cada repo agrega además `release.yml` y `docker-publish.yml`. No se agregan `security.yml`, `commit-policy.yml` ni workflows de summary: sus responsabilidades viven en el único workflow de calidad del PR.

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

### Túnel gratuito de Cloudflare

El autodeployer levanta automáticamente el servicio `cloudflared` cuando el archivo
`.env` contiene `CLOUDFLARE_TUNNEL_TOKEN`. El túnel se crea una sola vez desde
Cloudflare Zero Trust como túnel administrado remotamente; allí también se configura
el hostname `orux.ar` y el servicio local (por ejemplo `http://business-frontend:80`).
Luego se copia el token en `.env`:

```bash
CLOUDFLARE_TUNNEL_TOKEN=<token-del-tunel>
```

También se puede usar `CLOUDFLARE_TUNNEL_TOKEN_FILE` para mantener el token fuera
del `.env`. El archivo puede contener solo el token o una línea
`CLOUDFLARE_TUNNEL_TOKEN=...`.

No se publica el token en el repositorio. Si la variable está vacía, el autodeployer
funciona como antes y no inicia Cloudflare.

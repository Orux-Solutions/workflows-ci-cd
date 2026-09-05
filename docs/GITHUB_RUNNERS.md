# Runners GitHub Actions de Orux

## Política

Los jobs de CI, auditoría y publicación ejecutan siempre en Orux:

```yaml
runs-on: [self-hosted, linux, x64, orux-ci]
runs-on: [self-hosted, linux, x64, orux-buildkit]
```

No hay fallback a `ubuntu-latest`. Si Orux está apagado o el runner no está online, el job queda en cola y no consume minutos de GitHub-hosted. Si Orux no está disponible, tampoco se crea ni publica la imagen.

## Seguridad

El runner usa la imagen oficial, elimina `sudo`, descarta capabilities y baja al usuario `runner`. No tiene socket Docker, bind mounts del host, acceso a la red de Orux, puertos publicados ni modo privilegiado.

Es JIT y acepta un solo job. `/runner`, `_work` y las credenciales son tmpfs; al terminar se elimina el registro. Las builds usan BuildKit rootless en una red privada, sin acceso al daemon Docker del host.

## Configuración

Crear un Runner Group, por ejemplo `orux-isolated`, limitado a los repositorios privados de Orux. Crear una GitHub App privada con el único permiso `Self-hosted runners: Read and write` y guardar App ID, Installation ID y PEM.

```bash
sudo install -d -o root -g "$(id -gn)" -m 0750 /etc/orux/secrets
sudo install -o root -g root -m 0400 github-runner-app.pem /etc/orux/secrets/github-runner-app.pem
```

En el `.env` local e ignorado por Git:

```dotenv
ORUX_RUNNER_ENABLED=true
GITHUB_RUNNER_ORG=Orux-Solutions
GITHUB_RUNNER_IMAGE=ghcr.io/orux-solutions/orux-github-runner:2.337.0
GITHUB_RUNNER_APP_ID=<app-id>
GITHUB_RUNNER_APP_INSTALLATION_ID=<installation-id>
GITHUB_RUNNER_GROUP_ID=<runner-group-id>
GITHUB_RUNNER_APP_PRIVATE_KEY_FILE=/etc/orux/secrets/github-runner-app.pem
GITHUB_RUNNER_LABELS=orux-ci,orux-buildkit,linux,x64
```

```bash
sudo scripts/deployment/install-autodeployer.sh
docker compose --env-file .env -f compose.yaml --profile github up -d
docker compose --env-file .env -f compose.yaml ps github-runner buildkit
docker compose --env-file .env -f compose.yaml logs -f github-runner
```

El autodeployer sólo activa el perfil cuando todos los datos y la PEM existen. Con configuración incompleta deja Orux funcionando, pero no inicia un runner inválido.

## Workflows e imágenes

`ci.yml` usa `orux-ci`. `docker-publish.yml` usa `orux-buildkit` y Buildx con `tcp://buildkit:1234`.

Cada imagen se publica con `latest` para despliegue y con el tag de release para trazabilidad. También incorpora etiquetas OCI de release y commit. El autodeployer inspecciona la imagen después del pull y expone esos datos en Admin.

## Operación

```bash
docker compose --env-file .env -f compose.yaml ps github-runner buildkit
docker compose --env-file .env -f compose.yaml logs --tail=100 github-runner
```

GitHub no reasigna un job ya asignado si el host cae durante su ejecución; se debe revisar el run y relanzarlo cuando Orux vuelva a estar online.

Para rollback, usar temporalmente `ORUX_RUNNER_ENABLED=false` y reinstalar la unidad. Los workflows quedarán esperando Orux hasta que se reactive.

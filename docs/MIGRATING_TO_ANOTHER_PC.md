# Migrar Orux a otra PC

El repositorio contiene toda la infraestructura reproducible: Compose modular,
workflows, autodeployer, runner Docker y documentación. Las credenciales reales
no forman parte de GitHub.

## 1. Preparar la PC

Instalar Docker Engine, Docker Compose v2 y Git. Clonar este repositorio y los
repositorios de aplicaciones dentro del mismo directorio de trabajo.

## 2. Restaurar secretos

Copiar el ZIP cifrado al directorio de `workflows-ci-cd` y extraerlo con la
contraseña entregada fuera del repositorio:

```bash
unzip orux-secrets-*.zip -d .
chmod 600 .env
chmod 400 secrets/github-runner-app.pem
```

El ZIP debe contener `.env`, `cloudflared/credentials.json` y
`secrets/github-runner-app.pem`. Nunca subirlo a GitHub ni incluirlo en logs.

## 3. Verificar rutas

Si la ruta de la clave cambia, actualizar en `.env`:

```dotenv
GITHUB_RUNNER_APP_PRIVATE_KEY_FILE=/ruta/absoluta/secrets/github-runner-app.pem
```

La GitHub App debe estar instalada en la organización `Orux-Solutions` y el
Runner Group y sus IDs deben coincidir con `.env`.

## 4. Levantar

```bash
sudo scripts/deployment/install-autodeployer.sh
docker compose --env-file .env up -d
docker compose --env-file .env --profile github up -d buildkit github-runner
docker compose ps
```

El runner debe aparecer online en `Orux-Solutions > Settings > Actions >
Runners`. Los workflows principales usan siempre `orux-ci` o
`orux-buildkit`; si el runner no está disponible, el job queda en cola.

## 5. Actualizaciones

Las aplicaciones se despliegan siempre con `:latest`. Cada publicación también
conserva el tag de release y las etiquetas OCI de release y commit, que Admin
lee para mostrar qué versión está desplegada.

# Arquitectura Docker Compose de Orux

## Objetivo

`compose.yaml` es el único punto de entrada del despliegue. Usa `include`,
disponible desde Docker Compose 2.20, para reunir módulos que siguen siendo
legibles y mantenibles por separado.

```text
orux
├── orux
│   ├── data: mongo
│   ├── admin: backend + frontend
│   ├── business: backend + frontend
│   └── client: backend + frontend
├── edge: cloudflared
├── monitoring
│   ├── prometheus
│   ├── grafana
│   └── node-exporter
└── github (perfil opcional)
    ├── github-runner
    └── buildkit rootless
```

Los includes se resuelven recursivamente y cada ruta relativa se interpreta
desde el directorio del archivo hijo. Verificar siempre el modelo resultante:

```bash
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml config --services
```

## Operación

Desplegar Orux sin capacidad de GitHub:

```bash
docker compose --env-file .env -f compose.yaml up -d
```

Activar también el runner, una vez configuradas sus credenciales:

```bash
docker compose --env-file .env -f compose.yaml --profile github up -d
```

El autodeployer activa el mismo perfil cuando `ORUX_RUNNER_ENABLED=true` y la
configuración segura está completa. Si falta un ID o la clave privada, omite
el runner y continúa desplegando la aplicación.

## Puertos y exposición

Los puertos de MongoDB, backends, frontends, Prometheus y Grafana sólo se
publican en `127.0.0.1`. El acceso público de las aplicaciones se realiza por
el túnel saliente de Cloudflare. El runner y BuildKit no publican puertos.

Portainer fue eliminado porque la operación se realiza por terminal y su
acceso al socket Docker daba control administrativo sobre el host. La ruta
`docker.orux.ar` también fue eliminada de la configuración local y del ejemplo.
El volumen antiguo no se borra automáticamente. Después de comprobar que no
contiene nada necesario se puede retirar manualmente:

```bash
docker volume ls --filter name=portainer-data
docker volume rm orux_portainer-data
```

No ejecutar el segundo comando sin revisar primero el nombre exacto y confirmar
que no se necesita recuperar configuración.

## Monitoreo de Docker

La matriz de versiones, commits y disponibilidad ya existente en Admin es la
fuente de verdad para saber qué está desplegado. Para conocer la antigüedad del
proceso desde terminal se usa `docker compose ps`; no hace falta cAdvisor.

Las aplicaciones siguen desplegándose desde el tag móvil `latest`. Al publicar
una release, `docker-publish.yml` graba dentro de la imagen el tag semántico y
el commit como labels OCI. Después del pull, el autodeployer lee esos labels y
los inyecta como `*_VERSION`/`*_COMMIT` en los servicios; Admin muestra así el
tag que produjo la imagen, aunque Docker haya consumido `latest`. Las imágenes
anteriores sin labels se identifican de forma inequívoca como
`latest@<digest-corto>`.

Para paquetes privados, el servicio no reutiliza `~/.docker/config.json`. Se
configuran `GHCR_USERNAME` y `GHCR_TOKEN_FILE`; el archivo debe pertenecer al
usuario del autodeployer, ser modo `0400` y contener un token clásico con
alcance `read:packages`. Docker guarda la sesión resultante únicamente bajo
`/run/orux-deployer`, que es volátil. Si la autenticación o el pull fallan, el
despliegue conserva la imagen local anterior en lugar de interrumpir el servicio.

```bash
sudo install -d -o "$(id -un)" -g "$(id -gn)" -m 0700 /etc/orux/deployer
sudo install -o "$(id -un)" -g "$(id -gn)" -m 0400 ghcr-read-token \
  /etc/orux/deployer/ghcr-read-token
```

Prometheus conserva las métricas del host expuestas por node-exporter. Ambos
comparten la red interna `monitoring`; node-exporter no publica puertos. La
versión, uptime y disponibilidad de aplicaciones quedan en Admin. Ningún
componente de monitoreo monta `docker.sock` ni `containerd.sock`.

```bash
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml images
```

## Secretos

- `.env`, `cloudflared/` y claves PEM no deben versionarse.
- `JWT_ACCESS_SECRET` es obligatorio; ya no existe una clave predeterminada.
- La clave de la GitHub App debe vivir fuera del checkout, por ejemplo en
  `/etc/orux/secrets/github-runner-app.pem`, propiedad de root y modo `0400`.
- El bind mount usa `create_host_path: false`: si la clave no existe, Docker no
  crea silenciosamente un directorio en su lugar.

## Límites de aislamiento

El runner está en redes exclusivas y no monta el socket Docker ni directorios
del host. Un contenedor sigue compartiendo kernel con el host. Para ejecutar
código que no sea de colaboradores confiables, desplegar el módulo GitHub en
una VM dedicada aunque use el mismo hardware físico.

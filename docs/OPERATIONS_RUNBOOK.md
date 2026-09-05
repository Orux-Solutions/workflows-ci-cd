# Orux: runbook operativo

Este runbook aplica a los servicios Orux desplegados detrás de un health check y
una base de datos por entorno. No depende de producción para validarse: los
comandos de CI ejecutan la validación de manifests y los checks de release sobre
el checkout del commit.

## Health check y respuestas seguras

- `GET /` o `/health` debe devolver `200` solo cuando el proceso está vivo.
- Si MongoDB no está disponible, el endpoint de readiness debe devolver `503` y
  no filtrar nombres de colecciones, credenciales ni errores internos.
- El liveness check no debe depender de MongoDB: permite que el orquestador
  diferencie un proceso vivo de una dependencia caída.

## Degradación de Redis

Redis es una optimización. Si falla, el servicio debe continuar consultando la
fuente primaria, registrar un warning con `requestId` y evitar reintentos
infinitos. Nunca se debe devolver información de otro `tenantId` por un fallo de
caché.

## Métricas y logs mínimos

Registrar latencia y errores por ruta, cache hit/miss, lecturas a MongoDB y
tenant aislado por un identificador no sensible. Evitar emails, JWT, tokens,
payloads completos y labels de alta cardinalidad. Los logs deben ser JSON e
incluir `timestamp`, `level`, `service`, `requestId` y `tenantId` cuando exista.

## Alertas iniciales

- readiness `503` durante 5 minutos;
- error rate superior al 5% durante 10 minutos;
- p95 por encima del SLO acordado durante 10 minutos;
- cache miss sostenido o aumento anormal de lecturas MongoDB.

## Rollback

1. Identificar el release y commit fallido desde la URL de release.
2. Revertir a la última release estable; no modificar datos manualmente.

Si el autodeployer informa `403 Forbidden` o `unauthorized` contra `ghcr.io`,
verificar el login del usuario del servicio con un token que tenga
`read:packages`. El autodeployer conserva los contenedores actuales hasta que
el pull completo sea autorizado.

El workflow `Release` debe crear el GitHub Release con el secreto
`ORUX_RELEASE_TOKEN`, no con `GITHUB_TOKEN`: GitHub no inicia workflows por
eventos generados por `GITHUB_TOKEN`. `Publish Docker image` se mantiene
intencionalmente limitado a `release.published`.
3. Validar health/readiness y el flujo con un tenant de prueba.
4. Documentar causa, duración, impacto y commit restaurado.

## Operación del stack modular

Validar antes de desplegar:

```bash
docker compose --env-file .env -f compose.yaml config --quiet
```

Los servicios públicos salen exclusivamente por Cloudflare Tunnel. Los puertos
locales están ligados a `127.0.0.1`. Consultar la arquitectura completa en
[`COMPOSE_ARCHITECTURE.md`](COMPOSE_ARCHITECTURE.md).

El runner de GitHub es opcional. Su indisponibilidad no debe bloquear el
despliegue ni los workflows: el autodeployer omite el perfil si su configuración
está incompleta y Actions vuelve a runners administrados por GitHub. Consultar
[`GITHUB_RUNNERS.md`](GITHUB_RUNNERS.md).

Las imágenes privadas `latest` requieren `GHCR_USERNAME` y un
`GHCR_TOKEN_FILE` propiedad del usuario del autodeployer y modo `0400`, con un
token de sólo lectura para paquetes. Luego de cambiar la unidad systemd o estas
credenciales, volver a ejecutar `sudo scripts/deployment/install-autodeployer.sh`.

### Comandos habituales

```bash
docker compose ps
docker compose logs -f --tail=200
docker compose top
docker stats
systemctl status orux-deployer.service
journalctl -u orux-deployer.service -n 200 --no-pager
```

### Portainer retirado

Portainer fue eliminado del modelo y `docker.orux.ar` del túnel. El volumen
histórico no se elimina automáticamente. Conservarlo hasta confirmar que no se
requiere recuperar ninguna configuración y eliminarlo después de forma manual.

## Escalar un tenant

El routing debe resolver `tenantId` antes de seleccionar servidor o shard. La
configuración de destino se cambia mediante variables/secretos del entorno,
conservando el mismo contrato de API y comprobando autorización en el backend.

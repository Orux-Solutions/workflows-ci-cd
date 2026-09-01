# Aurea: runbook operativo

Este runbook aplica a los servicios Aurea desplegados detrás de un health check y
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
3. Validar health/readiness y el flujo con un tenant de prueba.
4. Documentar causa, duración, impacto y commit restaurado.

## Escalar un tenant

El routing debe resolver `tenantId` antes de seleccionar servidor o shard. La
configuración de destino se cambia mediante variables/secretos del entorno,
conservando el mismo contrato de API y comprobando autorización en el backend.

# Contrato del gate de Pull Request

El workflow reusable [`ci.yml`](../.github/workflows/ci.yml) es el único gate
obligatorio para los repositorios consumidores. En un Pull Request ejecuta, en
paralelo cuando corresponde al perfil, la validación de la aplicación, la
auditoría de dependencias, Conventional Commits, Dependency Review, CodeQL y
Gitleaks.

El job `gate` depende explícitamente de todos esos jobs y sólo termina en verde
cuando cada resultado es `success` o `skipped` por una condición documentada.
Un fallo, cancelación o resultado inesperado hace fallar el gate y debe bloquear
el merge mediante la regla de protección de ramas del repositorio consumidor.

Dependency Review se ejecuta cuando el Dependency Graph de GitHub está
habilitado. Si no lo está, el workflow deja constancia del motivo y mantiene
`dependency-audit` como control obligatorio para los perfiles Node; esto evita
presentar un control no soportado como si hubiera pasado.

Los callers deben apuntar a `orux-ci/.github/workflows/ci.yml@main`, declarar
el perfil correcto y configurar el nombre del job reusable como required check
en la protección de `main`.

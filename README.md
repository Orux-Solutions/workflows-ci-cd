# Aurea CI

Workflows y scripts compartidos de integración continua para los repositorios de Aurea.

## Versionado automático

El autotagger usa Conventional Commits:

- `fix` y `perf` incrementan patch.
- `feat` incrementa minor.
- Un breaking change incrementa major.
- Diez `feat` desde el último tag incrementan major aunque no haya breaking change.

El umbral se puede cambiar con `AUREA_FEATURES_FOR_MAJOR`, siempre con un entero positivo.

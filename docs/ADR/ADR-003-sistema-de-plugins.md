# ADR-003: Sistema de Plugins

## Data
2026-07-16

## Status
Aprovado

## Decisão
Extensões externas (integrações) são plugins instaláveis em `plugins/`.
Módulos internos (`src/`) fazem parte do núcleo e não são plugins.

## Consequências
- Núcleo protegido
- Extensibilidade controlada
- Atualizações independentes
- Ecossistema de plugins no futuro
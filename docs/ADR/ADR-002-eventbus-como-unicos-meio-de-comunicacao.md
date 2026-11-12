# ADR-002: EventBus como Único Meio de Comunicação

## Data
2026-07-16

## Status
Aprovado

## Decisão
Nenhum módulo chama outro diretamente. Toda comunicação passa pelo EventBus.

## Consequências
- Desacoplamento total
- Facilidade para adicionar novos módulos
- Auditoria de todas as interações
- Prevenção de dependências circulares
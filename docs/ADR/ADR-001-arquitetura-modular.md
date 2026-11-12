# ADR-001: Arquitetura Modular

## Data
2026-07-16

## Status
Aprovado

## Contexto
A EVA precisa evoluir por décadas sem perder estabilidade.

## Decisão
Arquitetura baseada em módulos independentes que se comunicam exclusivamente via EventBus.

## Consequências
- Módulos podem ser substituídos individualmente
- Testes isolados
- Escalabilidade horizontal
- Facilidade de manutenção
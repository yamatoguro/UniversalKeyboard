---
description: 'Regras para documentação e ADRs: estrutura de README, formato de ADR, changelog e o que deve ser atualizado junto com o código.'
applyTo: '**/*.md, **/docs/**'
---

# Documentação e ADR — regras

## Princípio

Documentação existe para **reduzir a chance de alguém quebrar o sistema**. Se um
documento não muda decisão de ninguém, ele é ruído.

## README de repo

Obrigatoriamente responde, nesta ordem:

1. O que este repo faz (uma frase).
2. Como construir.
3. Como testar.
4. Como executar / gravar no hardware.
5. O que este repo **não** faz (fronteira).

Nunca duplique o context map; referencie.

## ADR (Architecture Decision Record)

Um ADR por decisão. Local: `docs/adr/NNNN-titulo-em-kebab-case.md`.
O template está em [`docs/adr/0000-template.md`](../../docs/adr/0000-template.md).

Regras:

- Numeração sequencial, sem reaproveitar número.
- Status: `Proposto` → `Aceito` → (`Substituído por ADR-NNNN` | `Rejeitado`).
- ADR aceito é **imutável**: mude o mundo, não o registro. Correção vira novo ADR.
- Uma decisão por ADR. Não use como diário de bordo.

Quando criar ADR:

- mudança de contrato de protocolo serial,
- escolha de toolchain, biblioteca ou versão de linguagem,
- mudança de topologia entre repos,
- qualquer escolha com custo de reversão alto.

Não criar ADR para: renomear variável, corrigir bug, ajustar formatação.

## Changelog

`CHANGELOG.md` por repo, formato Keep a Changelog, seções
`Adicionado / Alterado / Corrigido / Removido / Segurança`. Entrada sempre com data
`AAAA-MM-DD` e referência ao ADR quando houver.

## Diagramas

- Mermaid em bloco cercado; nunca imagem binária versionada para diagrama de arquitetura.
- Diagrama de bancada elétrica pode ser imagem, com fonte (`.svg`) versionada junto.

## Idioma e tom

- Português (pt-BR), direto, sem marketing.
- Termos técnicos em inglês quando forem o padrão de mercado (`debounce`, `frame`, `ISR`).
- Primera menção de sigla expandida.
- Nada de "simplesmente", "basta", "obviamente" — documentação que presume não ajuda.

## Sincronização obrigatória

Atualize junto com o código, no mesmo commit:

| Mudou | Atualize |
|---|---|
| Fronteira entre repos | [`docs/context-map.md`](../../docs/context-map.md) §2 |
| Contrato serial | context map §6 + ADR + header de protocolo |
| Stack/toolchain | context map §4 + README do repo |
| Comando de build | README do repo + badge do CI |
| Comportamento observável | `CHANGELOG.md` |

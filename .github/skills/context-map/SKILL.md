---
name: context-map
description: |
  Mapa de contexto do UniversalKeyboard: teclado de 112 teclas com tela por keycap, layout adaptativo ao host. Define repos, fronteiras, contratos, orçamentos e decisões pendentes.
  Triggers: "contexto do projeto", "onde fica", "qual repo", "fronteira", "arquitetura geral", "visão do projeto", "context map", "onboarding".
  Use no início de qualquer sessão e antes de mudanças que cruzam repositórios.
  NOT for: detalhe de implementação de um módulo específico (use a skill do módulo).
---

# Context map

Fonte de verdade: [`docs/context-map.md`](../../../docs/context-map.md). Leia-o.

## Resumo operacional

**Produto:** teclado físico full-size de 112 teclas, cada keycap com display próprio. O
layout exibido se adapta ao computador conectado (ABNT2, ANSI US, …). O host vê um teclado
USB HID padrão.

**Fato central:** HID transporta usage IDs, não caracteres. O SO aplica o layout. A legenda
correta depende do layout ativo do host — informação que não existe no HID e chega pelo
canal vendor-specific, enviada pelo `uk-gui`.

## Repositórios

| Repo | Papel | Linguagem |
|---|---|---|
| `uk-gui` | Painel no host: detecta layout do SO, edita macros/layouts, gerencia driver | **a decidir** (Rust/C++/C) |
| `uk-pi0` | Daemon no Pi Zero 2W: estado, render, driver de tela, USB HID gadget | C++17 |
| `uk-sc-integration` | Contrato Pi↔Arduino + firmware do Arduino: frame, CRC, FSM | C11 / AVR |

## Fronteiras

- `uk-gui` fala **só** por HID vendor-specific. Não linka biblioteca dos outros repos.
- `uk-sc-integration` é dono exclusivo do frame serial.
- `uk-pi0` consome o contrato; não redefine frame.
- Nenhum repo inclui header privado de outro.

## Ordem de implementação ao cruzar camadas

```text
uk-sc-integration (contrato) → firmware AVR → uk-pi0 → uk-gui
```

## Orçamento que define decisões

| Operação | Tempo |
|---|---|
| 1 tecla | ~6,5 ms |
| 10 teclas | ~65 ms |
| 112 teclas (tela cheia) | ~730 ms |

Consequência: atualização é **sempre por tecla suja**. Tela cheia só em troca de
layout/tema/boot, em background.

## Decisões pendentes (não assumir)

1. Stack do `uk-gui`.
2. Frame serial v1 (stuffing vs COBS).
3. Protocolo HID vendor-specific (opcodes, fatiamento, transação).
4. Display: modelo, resolução e barramento.
5. Pi: `armhf` ou `arm64`.
6. AVR: ATmega328P ou ATmega32U4.
7. Pinagem da matriz 8×14 e do barramento de display.
8. Layouts suportados no v1.
9. Protocolo de update de firmware.

Se a tarefa depende de uma dessas, **pergunte** antes de codificar.

## Ao responder

Sempre diga qual repo e qual camada a mudança toca, e em que ordem implementar.

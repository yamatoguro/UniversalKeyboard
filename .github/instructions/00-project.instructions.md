---
description: 'Regras transversais do UniversalKeyboard: prioridade de falha, fronteiras entre repositórios, invariantes e convenções comuns.'
applyTo: '**'
---

# Regras transversais

## Contexto

Consulte [`docs/context-map.md`](../../docs/context-map.md) antes de alteração estrutural.

## Escopo da mudança

| Escopo | Sinais |
|---|---|
| Firmware MCU | `.ino`, `matrix`, `gpio`, `avr`, `firmware/` (vive em `uk-sc-integration`) |
| Daemon Linux | `uk-pi0/`, `systemd`, `hidg`, `epoll`, `render`, `display` |
| Protocolo | `uk-sc-integration/`, `frame`, `crc`, `proto` |
| Painel host | `uk-gui/`, `layout`, `detect`, `hidapi`, `macro` |

Mudança que atravessa camadas: implemente na ordem
**contrato (`uk-sc-integration`) → firmware → daemon → `uk-gui`**.
Nunca quebre o contrato sem versioná-lo.

## Prioridade de falha

1. Modificador preso é o pior defeito possível: inutiliza a máquina do usuário.
2. Falha de render não pode impedir de digitar.
3. Falha do `uk-gui` não pode impedir de digitar (último perfil persiste).
4. Boot protocol precisa funcionar em BIOS/UEFI/KVM.

## Invariantes

1. Link perdido, timeout, exceção, sinal de término ou watchdog ⇒ liberar **todas** as
   teclas e modificadores; entrar em `SAFE`.
2. Sem `malloc`/`new` após init no MCU.
3. ISR sem bloqueio, log, alocação ou espera ativa.
4. Dado compartilhado com ISR: `volatile` + seção crítica (ou atômico).
5. Sem `delay()`/`sleep()` no caminho de evento.
6. Entrada externa validada: tamanho, faixa, CRC.
7. Sem segredo, chave ou IP privado versionado.
8. **Nunca** atualizar 120 teclas por evento de tecla (orçamento: ~786 ms por tela cheia).

## Estilo de mudança

- Menor diff que satisfaz o requisito; sem refactor oportunista no mesmo commit.
- Função pública tem contrato documentado (pré, pós, erros).
- Código de retorno explícito; nunca ignorar retorno de I/O.
- Números mágicos nomeados com `UK_*`.
- Unidades explícitas no nome: `_ms`, `_us`, `_hz`, `_bytes`, `_px`.

## Diagnóstico

- Log fora do caminho crítico; no MCU, buffer circular em RAM com dreno controlado.
- Nunca `printf` em ISR nem em código de tempo real.
- `assert` só para invariante de programação, nunca para validar entrada externa.

## Comentários

Só o que o código não diz: **por quê**, não **o quê**. Sem código comentado — apague (o git
guarda). `TODO` com dono e condição: `TODO(tau): remover após ADR-0004`.

## Observabilidade mínima

Todo módulo expõe contadores de erro observáveis (sem alocação):

- frames descartados por CRC, por tamanho, por timeout;
- teclas sujas pendentes e profundidade da fila de render;
- tempo gasto por ciclo de scan / por ciclo de render;
- último erro do link e contagem de resync.

Contador que não pode ser lido é contador que não existe.

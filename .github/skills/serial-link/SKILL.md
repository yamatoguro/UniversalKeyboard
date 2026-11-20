---
name: serial-link
description: |
  Procedimento para o link Pi<->Arduino: layout de frame com SOF/VER/TYPE/LEN/payload/CRC16, byte stuffing vs COBS, resync após corrupção, heartbeat, timeout e liberação de teclas na perda.
  Triggers: "protocolo serial", "frame", "SOF", "CRC16", "CCITT", "COBS", "stuffing", "resync", "heartbeat", "timeout", "UART", "baud", "link caiu", "de-framing", "parser".
  NOT for: HID para o host (use hid-gadget), matriz de teclas (use input-matrix).
---

# Link serial — procedimento

`uk-sc-integration` é o **dono exclusivo** deste contrato. Firmware e daemon consomem.

## Frame

```text
+------+------+------+--------+---------+-------+
| SOF  | VER  | TYPE | LEN(1) | PAYLOAD | CRC16 |
| 0xA5 | 0x01 | 0xT  |   N    |   N B   |  2 B  |
+------+------+------+--------+---------+-------+
```

- `LEN` ≤ 64. `CRC16` = CCITT-FALSE (poly `0x1021`, init `0xFFFF`) sobre `VER..PAYLOAD`.
- Endianness do CRC: definir e testar com vetor conhecido. Ambiguidade aqui custa dias.
- `TYPE` em enum fechada; tipo desconhecido ⇒ ignora o frame e incrementa contador.

## Delimitação do payload

Escolha **uma** e registre em ADR:

| Opção | Prós | Contras |
|---|---|---|
| Byte stuffing (`0xA5` → `0xA5 0x00`) | simples, pouco overhead | pior caso 2×; bug clássico de escape |
| COBS | overhead determinístico, bom para payload binário | precisa de buffer de saída +1 |
| Tamanho fixo | trivial | desperdício e sem flexibilidade |

Se o payload nunca contém `0xA5` (por design do protocolo), dispensa delimitação — mas isso
é frágil e precisa estar escrito.

## Parser

Máquina de estados explícita, sem alocação, com resync:

```c
typedef enum {
    RX_WAIT_SOF = 0,
    RX_VER, RX_TYPE, RX_LEN, RX_PAYLOAD, RX_CRC_LO, RX_CRC_HI,
} rx_state_t;
```

- `LEN` inválido (`> UK_PROTO_MAX_PAYLOAD`) ⇒ volta a `RX_WAIT_SOF` e conta erro.
- CRC inválido ⇒ descarta o frame, **continua** o de-framing, conta erro. Não derruba o link.
- Timeout intra-frame (`UK_FRAME_TIMEOUT_MS`): descarta o parcial e volta a `RX_WAIT_SOF`.
  Sem isso, um byte perdido trava o parser para sempre.
- Nunca use `memcpy` de payload antes de validar `LEN`.

## Heartbeat e perda de link

- Pi envia heartbeat a cada `UK_HEARTBEAT_MS` (ex.: 100 ms).
- Arduino e daemon consideram link perdido após `UK_LINK_TIMEOUT_MS` (ex.: 250 ms).
- Perda ⇒ daemon: **liberar todas as teclas**, estado `SAFE`, sinalizar na tela.
- Perda ⇒ firmware: liberar estado interno, piscar status, esperar reconexão.
- Recuperação: ao voltar, **publicar estado "todas liberadas"** antes de qualquer evento real,
  senão a primeira transição gera release fantasma.

## Backpressure

- O Arduino não pode bloquear o scan esperando UART. Buffer circular de TX com tamanho fixo.
- Buffer cheio ⇒ **descartar evento antigo e contar overflow**, nunca perder transição de
  "release" (o inverso prende tecla).
- Prioridade: release > press.

## Taxa

- `921600` baud é razoável para 112 teclas e frames curtos; 115200 também serve para
  transições (não para streaming de estado completo).
- Streaming de bitmap completo é proibido em regime normal: envie só transições.
- Calcule: 112 teclas × ~120 acionamentos/min é trivial; o pior caso é "todas as teclas
  mudam ao mesmo tempo" (troca de camada) — dimensione para isso.

## Teste

Vetores obrigatórios:

- frame válido com payload de 0 e de `MAX` bytes;
- CRC errado → descartado, parser continua;
- frame truncado seguido de frame válido → recupera;
- ruído antes do SOF → ignora;
- `0xA5` dentro do payload → tratado conforme a delimitação escolhida;
- `LEN` acima do máximo → descartado sem overflow de buffer;
- timeout intra-frame → resolve.

Propriedade (fuzz): nenhuma entrada arbitrária produz escrita fora do buffer nem laço
infinito.

## Não faça

- Assumir que leitura de UART entrega frame completo.
- Derramar o link por CRC errado.
- Perder release por buffer cheio.
- Duplicar a definição do frame em dois repos.

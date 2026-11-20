# ADR-0002 — Frame do link serial v1

- **Status:** Proposto
- **Data:** 2026-11-20
- **Decisores:** autor do projeto (`tau` propõe, decisão humana)
- **Substitui:** —
- **Substituído por:** —

## Contexto

O link entre o Arduino (que varre a matriz de 112 teclas) e o Raspberry Pi Zero 2W (que
mantém o estado e apresenta o teclado ao host) precisa transportar transições de tecla com
latência baixa e detecção de erro.

Restrições reais:

- **RAM do AVR:** 2 KB no ATmega328P. O buffer de TX não pode ser grande.
- **UART sem controle de fluxo confiável** em cabo curto: corrupção pontual é possível.
- **Perda de link não pode prender tecla**: o protocolo precisa de sinal de vida.
- **`uk-sc-integration` é o dono exclusivo** deste contrato; firmware e daemon não devem
  redefini-lo.

Volume esperado: 112 teclas, tipicamente uma transição por vez. O pior caso é troca de
camada, em que muitas teclas mudam de estado quase simultaneamente.

## Decisão

### Estrutura

```text
+------+------+------+------+--------+---------+-------+
| SOF  | VER  | TYPE | LEN  | PAYLOAD| CRC16   |       |
| 0xA5 | 0x01 | 0xT  |  N   |  N B   | lo, hi  |       |
+------+------+------+------+--------+---------+-------+
       \___________ CRC cobre daqui ate o fim do payload _____/
```

| Campo | Tamanho | Regra |
|---|---|---|
| `SOF` | 1 | fixo `0xA5`, **não** coberto pelo CRC |
| `VER` | 1 | `0x01`; **nunca pode ser `0x00`** (ver delimitação) |
| `TYPE` | 1 | enum fechada |
| `LEN` | 1 | `0..32` |
| `PAYLOAD` | `LEN` | sem interpretação no de-framing |
| `CRC16` | 2 | CCITT-FALSE, **little-endian** (byte baixo primeiro) |

- **CRC16-CCITT-FALSE:** poly `0x1021`, init `0xFFFF`, sem reflexão, sem xor final.
  Vetor de teste obrigatório: `CRC("123456789") == 0x29B1`.
- **`UK_PROTO_MAX_PAYLOAD = 32`.** Escolha deliberada: mantém o pior caso de buffer sob
  controle no AVR (ver abaixo) e é suficiente para 15 eventos de tecla por frame ou 1
  snapshot completo.

### Delimitação: byte stuffing (não COBS)

`0xA5` no corpo do frame (de `VER` até `CRC_HI`) é escapado como `0xA5 0x00`.

- O escape é inequívoco **porque `VER` nunca é `0x00`**: na busca por início de frame,
  `A5 00` só pode ser byte literal; `A5 01` é início de frame v1.
- Pior caso de expansão: 2×. Buffer de TX dimensionado por:

```text
1 (SOF) + 2 * (1 + 1 + 1 + 32 + 2) = 1 + 2 * 37 = 75 bytes  ->  UK_TX_BUF = 96 B
```

COBS foi considerado e descartado **nesta versão**: exigiria segundo buffer de saída no AVR
e trocaria o delimitador para `0x00`, sem ganho relevante para payloads de 32 bytes.

### Tipos de mensagem

| `TYPE` | Nome | Payload | Direção |
|---|---|---|---|
| `0x01` | `KEY_EVENT` | `count(1)` + `count × {key_idx(1), flags(1)}` | Arduino → Pi |
| `0x02` | `KEY_SNAPSHOT` | `14 B` bitmap de 112 bits | Arduino → Pi |
| `0x03` | `HEARTBEAT` | vazio | ambos |
| `0x04` | `STATUS` | contadores de erro do firmware | Arduino → Pi |
| `0x05` | `BOOT_INFO` | `VER` de firmware, geometria da matriz | Arduino → Pi |
| `0x7F` | `NACK` | código de erro | ambos |

- `flags` bit 0 = pressionada. Bits 1..7 reservados, devem ser `0`.
- `KEY_EVENT` máximo: `(32 - 1) / 2 = 15` eventos por frame.
- `KEY_SNAPSHOT` cobre o caso de rajada (troca de camada): 14 bytes representam 112 teclas.

### Heartbeat e perda de link

| Parâmetro | Valor | Justificativa |
|---|---|---|
| `UK_HEARTBEAT_MS` | 100 | 10 Hz dá resolução de 100 ms para detectar perda |
| `UK_LINK_TIMEOUT_MS` | 250 | 2,5 heartbeats perdidos; abaixo disso, falso positivo |
| `UK_FRAME_TIMEOUT_MS` | 20 | frame máximo a 921600 baud leva ~0,8 ms; 20 ms é folga ampla |

Na perda: daemon libera todas as teclas e entra em `SAFE`; firmware zera estado e pisca
status. Na reconexão, o Arduino envia `KEY_SNAPSHOT` **antes** de qualquer `KEY_EVENT`, para
que o Pi não interprete estado antigo como transição nova.

### Prioridade em buffer cheio

`release` tem prioridade sobre `press`. Perder um `press` engole um acionamento; perder um
`release` **prende a tecla**. Se o buffer encher, descarta-se o `press` mais antigo e conta-se
`tx_overflow`.

### Taxa

`921600` baud como padrão. Não é requisito de banda (o tráfego real é trivial); é margem para
o pior caso de snapshot + eventos simultâneos.

## Alternativas consideradas

| Alternativa | Prós | Contras | Por que não |
|---|---|---|---|
| **Stuffing com `0xA5`** | Simples de verificar, sem buffer extra, pior caso limitado a 2× | Expansão 2× no pior caso | **Recomendada** |
| COBS | Overhead determinístico, bom para payload binário grande | Exige buffer de saída no AVR, delimitador `0x00` | Payload é pequeno; ganho não compensa complexidade |
| Payload de tamanho fixo | Trivial de implementar | Desperdício; sem evolução | Não aceita `KEY_SNAPSHOT` e `KEY_EVENT` no mesmo formato |
| Sem `VER` | Frame menor | Impossível evoluir sem quebrar | Inaceitável |

## Consequências

**Positivas**

- De-framing determinístico, com pior caso de buffer conhecido (`96 B`) e verificável em
  tempo de compilação.
- Resync explícito: CRC errado descarta o frame e **continua**, não derruba o link.
- Versão no frame permite evoluir sem adivinhar.

**Negativas**

- Expansão de até 2× no pior caso (aceitável no volume real).
- Exige a invariante "`VER` nunca `0x00`", que precisa de `static_assert` e teste.
- Sem número de sequência por frame: perda de frame isolada só é detectada pelo estado
  seguinte (snapshot na reconexão) ou pelo heartbeat.

**Mitigações**

- `static_assert(UK_PROTO_VER != 0x00, ...)` no header.
- Teste de propriedade: nenhuma entrada arbitrária gera escrita fora do buffer.
- `STATUS` reporta contadores de CRC e overflow, permitindo detectar perda em campo.

## Verificação

1. CRC bate com o vetor `"123456789" → 0x29B1`.
2. Fuzzer do parser roda 60 s sem crash e sem escrita fora do buffer.
3. Bancada: latência evento → frame no Pi medida com analisador lógico.
4. Desligar o Arduino em operação: o Pi entra em `SAFE` em ≤ 250 ms e libera as teclas.

## Referências

- [`docs/context-map.md`](../context-map.md) §4 e §6.1
- [`skills/serial-link`](../../.github/skills/serial-link/SKILL.md)
- CRC-16/CCITT-FALSE: poly `0x1021`, init `0xFFFF`, check `0x29B1`

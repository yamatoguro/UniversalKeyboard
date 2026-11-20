# ADR-0003 — Protocolo HID vendor-specific

- **Status:** Proposto
- **Data:** 2026-11-20
- **Decisores:** autor do projeto (`tau` propõe, decisão humana)
- **Substitui:** —
- **Substituído por:** —

## Contexto

O `uk-gui` precisa enviar ao teclado o **layout ativo do host**, além de perfis, macros e o
que desenhar em cada tecla. Esse é o único caminho possível: HID não expõe o layout do
host, e o teclado não pode inferi-lo.

O canal precisa ser:

- **independente da digitação** — falha ou lentidão aqui não pode travar o teclado;
- **transacional** — configuração parcial não pode virar estado inconsistente;
- **validado** — o report é entrada externa hostil;
- **versionado** — é contrato entre dois repos (`uk-gui` e `uk-pi0`).

### O limite físico que define o desenho

Em USB full-speed, um endpoint de interrupção entrega no máximo **64 bytes por pacote**, com
intervalo de 1 ms. Isso dá **~64 KB/s** de teto teórico.

| Transferência | Tamanho | Tempo a 64 KB/s |
|---|---|---|
| 1 imagem de tecla (128×128 RGB565) | 32 KB | ~0,5 s |
| 112 imagens (tela cheia) | 3,67 MB | **~56 s** |
| Sprite de ícone (32×32, 1 bpp) | 128 B | ~2 ms |
| Tabela de legendas de um layout (112 × 8 B) | ~0,9 KB | ~14 ms |

Conclusão que governa o protocolo:

> **O canal vendor transporta configuração semântica, não framebuffer.**
> O teclado renderiza a partir de *glyph IDs*, ícones pequenos e tema — não recebe pixels de
> tela cheia pelo HID.

Empurrar imagens completas levaria quase um minuto e travaria a percepção de resposta. Se
algum dia for necessário provisionar imagens completas, isso é um modo explícito, com
progresso na tela, nunca o caminho normal.

## Decisão

### Transporte

- Interface HID **vendor-defined** dedicada (interface 2 do dispositivo composto).
- Sem `report ID`: cada função HID do `configfs` vira um nó próprio (`/dev/hidgN`), então não
  há multiplexação a resolver.
- Report de **64 bytes**, nos dois sentidos.

### Formato de mensagem

```text
+-------+------+--------+------+------+---------+-------+
| MAGIC | VER  | OPCODE | SEQ  | LEN  | PAYLOAD | CRC16 |
| 0x55  | 0x01 |  0xNN  |  n   |  N   |   N B   | lo,hi |
+-------+------+--------+------+------+---------+-------+
                                             max 64 total
        \_________________ CRC cobre daqui _____________/
```

| Campo | Bytes | Regra |
|---|---|---|
| `MAGIC` | 1 | `0x55`; fora do CRC |
| `VER` | 1 | `0x01` |
| `OPCODE` | 1 | ver tabela |
| `SEQ` | 1 | incrementa por mensagem; ecoado na resposta |
| `LEN` | 1 | `0..57` |
| `PAYLOAD` | `LEN` | específico do opcode |
| `CRC16` | 2 | CCITT-FALSE sobre `VER..PAYLOAD`, little-endian |

`LEN` máximo = `64 - 5 - 2 = 57`.

### Opcodes

| Faixa | Opcode | Nome | Direção |
|---|---|---|---|
| Controle | `0x01` | `PING` | ambos |
| Controle | `0x02` | `GET_INFO` | gui → teclado |
| Controle | `0x03` | `GET_STATS` | gui → teclado |
| Controle | `0x04` | `GET_STATE` | gui → teclado |
| Config | `0x10` | `SET_HOST_LAYOUT` | gui → teclado |
| Config | `0x11` | `SET_ACTIVE_PROFILE` | gui → teclado |
| Transferência | `0x20` | `TX_BEGIN` | gui → teclado |
| Transferência | `0x21` | `TX_DATA` | gui → teclado |
| Transferência | `0x22` | `TX_COMMIT` | gui → teclado |
| Transferência | `0x23` | `TX_ABORT` | gui → teclado |
| Resposta | `0x7F` | `ACK` | teclado → gui |
| Resposta | `0x7E` | `NACK` | teclado → gui |

`SET_HOST_LAYOUT` cabe em um único report: `layout_id(1)` + `variant(1)` + `flags(1)` +
`fingerprint_hash(8)`.

### Transferência de blobs (perfil, tabela de legendas, sprites)

```text
TX_BEGIN   payload: opcode_alvo(1) | total_len(4) | crc32(4)   -> session_id(1)
TX_DATA    payload: session_id(1) | offset(2) | data(≤54)
TX_COMMIT  payload: session_id(1)                              -> ACK ou NACK
TX_ABORT   payload: session_id(1)
```

- Nada é aplicado ao estado antes de `TX_COMMIT`.
- `TX_COMMIT` valida `total_len` e `crc32` **antes** de aplicar; divergência ⇒ `NACK` e
  estado anterior preservado.
- Sessão expira após **2 s** sem `TX_DATA`; o dispositivo descarta o buffer e libera a sessão.
- Uma sessão por vez. `TX_BEGIN` com sessão ativa é `NACK`.

### Idempotência

`SET_HOST_LAYOUT` e `SET_ACTIVE_PROFILE` são **idempotentes**: reenviar o mesmo valor não
marca teclas como sujas nem redesenha nada. Isso é obrigatório porque o `uk-gui` reenvia
configuração a cada reconexão.

### Versionamento

- `GET_INFO` devolve `proto_ver`, `fw_ver`, `capabilities` (bitmask) e geometria da matriz.
- O `uk-gui` **verifica** `proto_ver` e `capabilities` antes de usar um opcode opcional.
- Opcode desconhecido ⇒ `NACK` com `ERR_UNSUPPORTED`; nunca silêncio.
- Adicionar opcode é compatível; mudar formato de opcode existente exige `VER` novo e ADR.

### Erros

| Código | Nome | Significado |
|---|---|---|
| `0x00` | `OK` | sucesso |
| `0x01` | `ERR_UNSUPPORTED` | opcode ou capability ausente |
| `0x02` | `ERR_BAD_LEN` | `LEN` fora do permitido para o opcode |
| `0x03` | `ERR_BAD_CRC` | CRC da mensagem inválido |
| `0x04` | `ERR_BAD_STATE` | operação inválida no estado atual |
| `0x05` | `ERR_NO_SESSION` | `session_id` desconhecido ou expirado |
| `0x06` | `ERR_TOO_LARGE` | `total_len` acima do limite |
| `0x07` | `ERR_CRC32` | conteúdo do blob não confere no `COMMIT` |
| `0x08` | `ERR_UNKNOWN_LAYOUT` | `layout_id` não suportado |

### Não bloqueio

- O processamento de vendor report **não pode** ocorrer na thread de scan nem na de render.
- Buffer de recepção pequeno e fixo; mensagem que não couber é `NACK`, não é acumulada
  indefinidamente.
- Se o host não consumir respostas, o dispositivo **descarta** respostas antigas em vez de
  bloquear.

## Alternativas consideradas

| Alternativa | Prós | Contras | Por que não |
|---|---|---|---|
| **HID vendor + transferência transacional** | Sem driver de kernel no host; funciona em qualquer SO com HID; transacional | 64 B por report; fatiamento necessário | **Recomendada** |
| USB CDC/serial adicional | Fluxo, sem fatiamento manual | Segundo dispositivo; alguns SO fazem enumeração extra; nem todo ambiente libera | Adiciona dependência desnecessária |
| Rede local (WebSocket no Pi) | Payload grande, fácil depurar | Exige IP, firewall, descoberta; falha em ambiente corporativo | Contraria "sem dependência de rede" |
| Transferir framebuffer completo | Flexibilidade visual total | ~56 s para tela cheia (§ acima) | Inviável como caminho normal |

## Consequências

**Positivas**

- Sem driver no host: qualquer SO com HID fala o protocolo.
- Transacional: configuração parcial nunca vira estado inconsistente.
- Versionado e com `capabilities`: evolução sem quebrar cliente antigo.
- Limite de banda respeitado por desenho (semântica, não pixels).

**Negativas**

- Fatiamento manual e CRC duplo (mensagem e blob) aumentam a superfície de bug.
- Payload de 57 B limita a tabela de legendas: 112 entradas exigem ~2 KB ⇒ ~36 mensagens.
- Sem `report ID`: exige uma função HID dedicada por interface.

**Mitigações**

- Testes de protocolo com vetores fixos e fuzzer do parser de mensagem.
- Tabela de legendas comprimida (delta ou índice de glifo) para reduzir mensagens.
- Limite de `total_len` declarado e verificado dos dois lados.

## Verificação

1. `SET_HOST_LAYOUT` idempotente: reenvio não gera tráfego de render (medir em log).
2. `TX_ABORT` no meio de um perfil deixa o estado anterior intacto.
3. `NACK` com `ERR_CRC32` quando o blob é corrompido de propósito.
4. `uk-gui` desconhecido (versão maior) recebe `ERR_UNSUPPORTED` e degrada sem quebrar.
5. Inundar o canal vendor **não** atrasa a digitação (medir latência de tecla durante a
   transferência).

## Referências

- [`docs/context-map.md`](../context-map.md) §4 e §6.2
- ADR-0001 (stack do `uk-gui`, cliente deste protocolo)
- [`skills/hid-gadget`](../../.github/skills/hid-gadget/SKILL.md) e
  [`instructions/hid-usb`](../../.github/instructions/hid-usb.instructions.md)

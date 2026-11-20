---
name: arduino-firmware
description: |
  Procedimento para o firmware do Arduino que varre a matriz de 112 teclas: estrutura setup/loop, board_pins.h, orçamento de RAM, build com arduino-cli, upload e verificação de uso de flash/RAM.
  Triggers: "arduino", "firmware", "sketch", "ino", "arduino-cli", "fqbn", "upload", "avr-gcc", "PROGMEM", "RAM", "flash", "board_pins", "ATmega".
  NOT for: lógica da matriz em si (use input-matrix), frame serial (use serial-link).
---

# Firmware Arduino — procedimento

Local: `uk-sc-integration/firmware/` (é uma das pontas do contrato serial).

## Estrutura

```text
firmware/
├── firmware.ino          ← setup/loop, nada de lógica
├── board_pins.h          ← toda a pinagem, um arquivo
├── matrix.c/.h           ← varredura + debounce (testável no host)
├── link.c/.h             ← frame, CRC, parser
└── status_led.c/.h
```

- `firmware.ino` só orquestra. Lógica em `.c`/`.cpp` para poder testar no host.
- Nada de pino numérico fora de `board_pins.h`.
- Conflito de pino detectado em compilação:

```c
static_assert(PIN_ROW0 != PIN_UART_TX, "conflito: ROW0 vs UART TX");
```

## `loop()` não bloqueia

```cpp
void loop()
{
    const uint32_t now = millis();
    matrix_poll(now);
    link_poll(now);
    status_led_poll(now);
}
```

- Sem `delay()`. Sem `while` esperando periférico.
- `delay()` só em `setup()` para estabilização, com comentário do motivo.

## Orçamento de RAM (ATmega328P = 2 KB)

| Item | Bytes |
|---|---|
| Bitmap de 112 teclas | 14 |
| Debounce por tecla (1 B estado + 4 B timestamp) | 560 |
| Buffer de TX | 64–128 |
| Buffer de RX | 64 |

- `String` proibido. `char[]` fixo.
- Texto em `F()`/`PROGMEM`.
- Verifique no build: `avr-size --format=avr --mcu=atmega328p firmware.elf`

## Build e upload

```bash
arduino-cli compile --fqbn arduino:avr:uno --warnings all firmware/
arduino-cli upload  --fqbn arduino:avr:uno --port /dev/ttyACM0 firmware/
```

- `--fqbn` sempre explícito e igual ao documentado no README.
- Reporte **flash e RAM** no resultado do build.
- Para AVR puro: `Makefile` com `avr-gcc -Os -mmcu=...`.

## Link e heartbeat

- Se o Pi não pingar em `UK_LINK_TIMEOUT_MS`: liberar estado, piscar status, esperar.
- Ao reconectar: publicar "todas liberadas" antes de qualquer evento real.
- Buffer de TX cheio: descartar press antigo, **nunca** release.

## Interrupções

- `attachInterrupt` só para evento realmente urgente. Matriz: polling por timer.
- ISR com corpo mínimo; flag `volatile`.
- Nunca `Serial.*`, `malloc` ou `millis()` com lock dentro de ISR.

## Checklist antes de considerar pronto

- [ ] Scan completo medido (≤ 1 ms).
- [ ] Uso de RAM reportado e dentro do orçamento.
- [ ] Sem `delay()` no `loop()`.
- [ ] Perda de link libera estado.
- [ ] Reconexão não emite evento fantasma.
- [ ] Todas as 112 teclas testadas individualmente.

## Não faça

- Lógica dentro do `.ino`.
- Pino mágico.
- `String` em caminho de evento.
- Upload com `--fqbn` diferente do documentado.
- Assumir link sempre presente.

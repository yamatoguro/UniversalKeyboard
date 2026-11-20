---
description: 'Regras para firmware AVR/Arduino: laço não bloqueante, pinagem centralizada, scan de matriz 6x23, debounce por timestamp e orçamento de RAM.'
applyTo: '**/*.ino, **/firmware/**, **/*.pde'
---

# Arduino / AVR

O firmware vive em `uk-sc-integration` (é uma das pontas do contrato serial).

## Estrutura

- `setup()` inicializa hardware e deixa estado conhecido; não faz trabalho de produto.
- `loop()` **nunca** bloqueia. Sem `delay()`, sem `while` esperando periférico.
- Ordem de init: clock → GPIO seguro → link → periféricos → habilitar IRQ.

```cpp
void loop()
{
    const uint32_t now = millis();
    matrix_poll(now);
    link_poll(now);
    status_led_poll(now);
}
```

- `delay()` só em `setup()` para estabilização, com comentário do motivo e do tempo.

## Pinagem

- Toda pinagem em um único `board_pins.h` por placa, com comentário do conector físico.
- Proibido número de pino no corpo do código.
- Pinos reservados (UART, I2C, SPI, LED) documentados e verificados em tempo de compilação:

```c
static_assert(PIN_ROW0 != PIN_UART_TX, "conflito de pino: ROW0 vs UART TX");
```

- Pino de saída inicia em nível seguro antes de virar saída.

## Matriz 6×23 (120 teclas)

- Colunas dirigidas uma por vez, linhas lidas com pull-up; **um diodo por tecla**.
- Tempo de acomodação entre acionar coluna e ler linha: constante nomeada
  (`UK_MATRIX_SETTLE_US`), não literal solto.
- Varredura completa em ≤ 1 ms; se não couber, reduza a frequência de scan — nunca remova o
  settle.
- Estado por tecla: `pressed`, `last_change_ms`. Debounce por timestamp, nunca por `delay()`.
- Ao final de cada varredura, comparar o bitmap com o anterior e emitir apenas transições.
- NKRO: enviar bitmap; o Pi decide o que vai ao host.

## RAM (2 KB no ATmega328P)

- Conte cada buffer global. `120 bits` de estado = 15 bytes; o resto é orçamento real.
- String literal em `F()`/`PROGMEM`; não deixe crescer `.data`.
- Sem `String`. `char[]` de tamanho fixo.
- Verifique no build: `avr-size --format=avr --mcu=...`

## Link serial

- Taxa fixa documentada; nunca muda em runtime.
- `Serial.print` para depuração **fora** do caminho de evento; use buffer + dreno.
- Leitura sempre com contrato de tamanho: `while (Serial.available() > 0)` consumindo até
  completar o frame, nunca assumindo que veio inteiro.
- Heartbeat: se o Pi não pingar em `UK_LINK_TIMEOUT_MS`, o firmware libera tudo e pisca status.

## Build

```bash
arduino-cli compile --fqbn arduino:avr:uno --warnings all .
arduino-cli upload  --fqbn arduino:avr:uno --port /dev/ttyACM0 .
```

- `--fqbn` explícito sempre. Reporte uso de flash **e** RAM no resultado.
- Para AVR puro: `Makefile` com `avr-gcc -Os`.

## Interrupções

- `attachInterrupt` só para evento realmente urgente (ex.: frame start). Teclas: polling
  por timer.
- ISR registrada com `ISR(TIMER1_COMPA_vect)`, corpo mínimo, flag `volatile`.
- Nunca `Serial.*`, `malloc` ou `millis()` com lock dentro de ISR.

## Proibido

- `delay()` no `loop()`.
- `String` em caminho de evento.
- Pino mágico.
- Upload com `--fqbn` diferente do documentado no README.
- Firmware que assume link sempre presente.

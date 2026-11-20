---
description: 'Regras para C embarcado (AVR e núcleo portável): memória estática, ISR, tipos de largura fixa, máquinas de estado e disciplina de tempo.'
applyTo: '**/*.{c,h}'
---

# C embarcado

Alvo duplo: ATmega (RV de 2 KB) e biblioteca portável no Pi. Mesmo estilo; orçamento diferente.

## Padrão e tipos

- C11 (`-std=c11`). Sem extensão GNU exceto exigência do toolchain AVR.
- `<stdint.h>`: `uint8_t`/`int16_t`/`uint32_t`. `int`/`long` só para índice local de faixa
  conhecida.
- `bool` de `<stdbool.h>`. `size_t` para tamanho/índice.
- Proibido `float`/`double` em caminho determinístico de MCU.

## Memória

- Sem `malloc`/`calloc`/`realloc`/`free` após inicialização.
- Buffer de tamanho fixo com macro `UK_*_CAPACITY`; valide antes de escrever:

```c
if (idx >= cap) { return UK_ERR_RANGE; }
```

- Prefira `static` em escopo de arquivo. Estrutura compartilhada entre contextos: copie sob
  seção crítica, não compartilhe ponteiro solto.
- No ATmega328P (2 KB SRAM): contabilize cada buffer global. String literal em `PROGMEM`/`F()`.

## ISR

```c
/* Ruim: bloqueia e loga dentro da ISR. */
ISR(TIMER0_COMPA_vect) { printf("tick\n"); }

/* Bom: acumula e delega ao laco. */
ISR(TIMER1_COMPA_vect)
{
    g_tick_ms++;
    g_scan_due = true;
}
```

- Curta, sem chamada de biblioteca não reentrante, sem retorno de erro ignorado.
- Variável compartilhada: `volatile` + interrupção desabilitada para leitura multi-byte.

```c
static inline uint32_t critical_read_u32(volatile uint32_t *p)
{
    uint32_t v;
    const uint8_t sreg = SREG;
    cli();
    v = *p;
    SREG = sreg;
    return v;
}
```

## Tempo

- Base monotônica em `uint32_t` (`_ms`/`_us`). Compare por diferença, nunca por `==`.

```c
static bool elapsed_ms(uint32_t now, uint32_t start, uint32_t limit_ms)
{
    return (uint32_t)(now - start) >= limit_ms;   /* seguro no wrap */
}
```

- Sem espera ativa fora de init de hardware.
- Laço cooperativo: cada módulo expõe `*_poll(now_ms)` e retorna rápido.

## Máquinas de estado

- Estado explícito em `switch`, com `default` que vai para estado seguro.
- Sem `goto` para reiniciar máquina de estado; use retorno.
- Módulo não trivial documenta os estados no header.

## API e erros

```c
typedef enum {
    UK_OK = 0,
    UK_ERR_RANGE,
    UK_ERR_STATE,
    UK_ERR_TIMEOUT,
    UK_ERR_CRC,
    UK_ERR_NO_MEM,
} uk_status_t;
```

- Função que pode falhar retorna `uk_status_t`; nunca `-1` genérico.
- Entrada: `const` + ponteiro. Saída: ponteiro validado antes de escrever.
- Header público: guarda `#ifndef UK_MODULE_H`, `extern "C"` para consumo em C++.

## Qualificadores

- `const` em tudo que não é modificado.
- `volatile` **só** para o que muda fora do fluxo (registrador, ISR). Não é sincronização.
- `restrict` apenas quando comprovadamente sem sobreposição.

## Build limpo

`-Wall -Wextra -Werror -Wconversion -Wshadow -Wcast-align`. Sem conversão que estreita
valor sem cast justificado. Sem variável não usada.

## Proibido

- `strcpy`, `sprintf`, `gets`, `atoi` → variantes com limite.
- Retornar ponteiro para variável local.
- `#include` de header privado de outro repo.
- Comparar `enum` com valor fora da enumeração.

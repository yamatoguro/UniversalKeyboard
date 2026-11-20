---
name: embedded-c
description: |
  Procedimento para escrever C embarcado no UniversalKeyboard: firmware AVR da matriz de 112 teclas e biblioteca portável do protocolo. Memória estática, ISR curta, máquinas de estado, comparação de tempo segura no wrap.
  Triggers: "escrever C", "criar módulo", "ISR", "volatile", "seção crítica", "fila estática", "máquina de estados", "uint32 wrap", "AVR C", "código embarcado".
  NOT for: C++ do daemon (use cpp-daemon), Assembly (use assembly).
---

# C embarcado — procedimento

## Antes de escrever

1. Qual alvo? ATmega (RAM em KB, sem `malloc`) ou biblioteca portável no Pi (RAM folgada,
   mas ainda sem alocação em caminho de evento)?
2. Qual orçamento? RAM disponível, tempo por ciclo de scan, frequência de chamada.
3. Qual invariante está em jogo? (fail-safe, ISR, determinismo)

## Estrutura de um módulo

```c
/* key_matrix.h — API pública, sem detalhe de implementação. */
#ifndef UK_KEY_MATRIX_H
#define UK_KEY_MATRIX_H

#include <stdbool.h>
#include <stdint.h>

#include "uk_status.h"

#ifdef __cplusplus
extern "C" {
#endif

#define UK_KEY_COUNT        112u
#define UK_MATRIX_ROWS        8u
#define UK_MATRIX_COLS       14u
#define UK_DEBOUNCE_MS        5u

typedef struct {
    uint16_t key_idx;
    bool     pressed;
    uint32_t at_ms;
} key_event_t;

/* Retorna UK_OK ou UK_ERR_STATE se nao inicializado. */
uk_status_t matrix_init(void);

/* Avanca uma varredura. Deve retornar em < UK_SCAN_BUDGET_US. */
uk_status_t matrix_poll(uint32_t now_ms);

/* Copia ate capacity eventos. Retorna quantos copiou. */
size_t matrix_drain(key_event_t *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif /* UK_KEY_MATRIX_H */
```

## Checklist de implementação

- [ ] Estado em `static` de arquivo; nada exportado além do header.
- [ ] Todo buffer com `CAPACITY` nomeada e verificação de índice antes da escrita.
- [ ] Nenhum `malloc` após `init`.
- [ ] Tempo por diferença: `(uint32_t)(now - start) >= limit`, nunca `now == start + limit`.
- [ ] ISR só toca `volatile` e flags; corpo com poucas instruções.
- [ ] Leitura multi-byte compartilhada protegida (`cli`/restore de `SREG` no AVR, atomic no Pi).
- [ ] `switch` de estado com `default` que vai para estado seguro.
- [ ] Contador de erro para cada caminho de descarte.
- [ ] Nenhum `printf`/`Serial` no caminho de evento.

## Padrões que se repetem

**Fila estática com coalescing** (para eventos de tecla):

```c
typedef struct {
    key_event_t buf[UK_EVENT_QUEUE_CAPACITY];
    size_t      head;
    size_t      tail;
    size_t      count;
} event_queue_t;
```

Encher a fila é falha de projeto, não de execução: dimensione pela pior rajada esperada
(112 teclas simultâneas) e conte overflow.

**Debounce por timestamp:**

```c
typedef struct {
    uint32_t last_change_ms;
    bool     stable;
    bool     raw;
} debounce_t;

static void debounce_update(debounce_t *d, bool raw_now, uint32_t now_ms)
{
    if (raw_now != d->raw) {
        d->raw = raw_now;
        d->last_change_ms = now_ms;
        return;
    }
    if (d->raw != d->stable &&
        (uint32_t)(now_ms - d->last_change_ms) >= UK_DEBOUNCE_MS) {
        d->stable = d->raw;
    }
}
```

## Verificação

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"
cmake --build build && ctest --test-dir build --output-on-failure
cppcheck --enable=warning,style,performance,portability --error-exitcode=1 -Iinclude src
```

Teste host com tempo injetado, nunca `sleep()` real.

## Erros comuns a evitar

- `volatile` usado como sincronização.
- Debounce aplicado no firmware **e** no daemon.
- `int` onde precisa `uint32_t` (wrap em 49 dias é bug real em produto).
- ISR que chama função de biblioteca não reentrante.
- Buffer sem verificação de índice em caminho de entrada externa.

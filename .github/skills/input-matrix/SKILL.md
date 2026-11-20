---
name: input-matrix
description: |
  Procedimento para a malha de 120 teclas: matriz 6x23 com diodo por tecla, varredura por coluna, tempo de acomodação, debounce por timestamp, anti-ghosting, NKRO e emissão apenas de transições.
  Triggers: "malha de teclas", "matriz", "scan", "varredura", "debounce", "ghosting", "rollover", "NKRO", "6KRO", "diodo", "coluna", "linha", "tecla presa", "repetição".
  NOT for: protocolo serial (use serial-link), renderização da tecla (use key-rendering).
---

# Matriz de entrada — procedimento

## Geometria

120 teclas ⇒ **8 linhas × 14 colunas**. Com 1 diodo por tecla (cátodo na linha, ânodo na
coluna, ou o inverso conforme a placa), o ghosting clássico de matriz passiva desaparece e
NKRO é possível.

Sem diodo: no máximo 2–3 teclas simultâneas confiáveis. **Não** aceite matriz sem diodo em
produto que promete NKRO.

## Varredura

1. Desacionar todas as colunas.
2. Para cada coluna `c`: acionar `c`, esperar `UK_MATRIX_SETTLE_US`, ler as 8 linhas.
3. Acumular no bitmap de 120 bits (`uint8_t bits[14]`), um byte por coluna.
4. Comparar com o bitmap anterior; para cada bit que mudou, alimentar o debounce.
5. Emitir evento apenas quando o estado **estável** muda.

```c
/* Um byte por coluna cobre 8 linhas: 14 bytes = 120 teclas. */
static uint8_t g_raw[UK_MATRIX_COLS];
static uint8_t g_stable[UK_MATRIX_COLS];
```

## Tempo

- `UK_MATRIX_SETTLE_US`: medir na placa real com o pull-up escolhido. Cabo longo e
  capacitância alta aumentam esse número. Não chute.
- Varredura completa alvo: **≤ 1 ms**. Consequência: 14 colunas ⇒ ≤ 70 µs por coluna.
- Se não couber, aumente o intervalo entre varreduras (ex.: 2 ms), não reduza o settle.
- Nunca `delay()` entre colunas: use contador de fases no laço cooperativo.

## Debounce

- Por tecla, por timestamp: `UK_DEBOUNCE_MS` típico 5 ms.
- O debounce estabiliza ruído mecânico. **Não** confunda com dwell/atraso de acessibilidade —
  são features diferentes e vivem no perfil.
- Aplicar **uma vez**. Firmware **ou** daemon. Aplicar nos dois duplica latência e engole
  toque curto.
- Repetição (auto-repeat) é responsabilidade do host. Não reenvie keycode por conta própria,
  exceto se o perfil pedir.

## Perda e recuperação

- Link caiu, Pi reiniciou ou heartbeat expirou ⇒ **liberar todas as teclas** e limpar
  `g_stable`, senão a primeira varredura após reconexão emite um "release" fantasma.
- Após init, publicar o estado inicial como "todas liberadas" — não como transição.

## Teste sem hardware

- Abstraia o acesso a GPIO atrás de uma interface (`gpio_read_col/row`) e teste a lógica com
  um fake:

```c
matrix_test_set_column(3, 0b00010000);   /* linha 4 da coluna 3 pressionada */
matrix_poll(0);
matrix_poll(UK_DEBOUNCE_MS + 1);
assert(matrix_drain(ev, 8) == 1);
```

- Casos obrigatórios: tecla simples, rajada (bounce), 23 teclas simultâneas, todas as 120,
  transição durante troca de coluna, reconexão após perda de link.

## Métricas para registrar

- Duração da varredura completa (min/média/máx).
- Overflow da fila de eventos.
- Contagem de teclas instáveis por segundo (indica ruído elétrico).
- Quantas teclas NKRO simultâneas já foram vistas.

## Não faça

- Debounce em dois lugares.
- Assumir settle sem medir.
- Matriz sem diodo prometendo NKRO.
- Emitir evento por nível em vez de por transição.
- Manter `g_stable` após reconexão.

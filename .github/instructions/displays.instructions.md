---
description: 'Regras para o pipeline de exibição: 112 displays, orçamento de banda, atualização por tecla suja, fila com coalescing e degradação graciosa.'
applyTo: '**/display/**, **/render/**, **/*display*.{c,h,cpp,hpp}, **/*render*.{c,h,cpp,hpp}, **/display_driver*.{c,h,cpp,hpp}'
---

# Pipeline de exibição

## O orçamento, medido

| Operação | Dados | ~40 MHz SPI |
|---|---|---|
| 1 tecla (128×128 RGB565) | 32 KB | ~6,5 ms |
| 10 teclas | 320 KB | ~65 ms |
| 112 teclas (tela cheia) | 3,67 MB | **~730 ms** |

Regra derivada: **tela cheia só em troca de layout, tema ou boot — sempre em background.**

## Modelo de atualização

- O produtor **não desenha**: marca `dirty[key_idx] = true` e retorna.
- Uma thread de render consome a fila, compõe as teclas sujas e escreve no driver.
- Fila de tamanho fixo (`UK_RENDER_QUEUE_CAPACITY`). Cheia ⇒ **coalescing**: funde com a
  entrada pendente da mesma tecla; se não houver, descarta a mais antiga. Nunca bloqueia.
- Prioridade: tecla com foco/última acionada > visível alterada por modificador > resto.
- Orçamento por ciclo (`UK_RENDER_BUDGET_BYTES`): pare ao estourar e continue no próximo.

```c
/* Produtor: barato e sem I/O. */
void ui_mark_dirty(uint8_t key_idx)
{
    if (key_idx >= UK_KEY_COUNT) { return; }
    g_dirty_bits[key_idx >> 3] |= (uint8_t)(1u << (key_idx & 7u));
}
```

## Composição

- Framebuffer **por tecla**, reutilizado entre frames; sem realocação.
- Recompõe apenas a região alterada quando possível (dirty-rect dentro da tecla).
- Fundo estático (tema, moldura) em cache; só o conteúdo dinâmico é redesenhado.
- Fontes e ícones em **atlas** único carregado uma vez; nunca decodifique PNG/JPEG em
  runtime no Pi.
- Texto renderizado a partir de atlas de glifos; nada de `free`/Type1 em device.
- Cor: definir um único formato nativo (RGB565 é o candidato) e converter na borda.

## Driver de tela

- Interface abstrata (`display_driver_t`) com `init`, `write_region`, `flush`, `sleep`,
  `wake`, `get_caps`. O resto do código não conhece o barramento.
- `write_region` recebe retângulo + ponteiro + `stride`; nunca assume tela cheia.
- DMA/SPI assíncrono: manter fila de descritores; `flush` só sincroniza quando necessário.
- Tearing: sincronizar com o sinal de VSYNC/TE do painel quando existir; caso contrário,
  documentar a estratégia adotada.
- Timeout em toda operação de barramento. Barramento travado ⇒ não trava o daemon.

## Degradação graciosa

1. Falha de escrita ⇒ retry limitado; conta erro.
2. Falhas consecutivas acima do limite ⇒ desliga o render (economiza CPU), mantém o teclado.
3. Sinaliza estado degradado num LED/indicador ou numa tecla de status.
4. Nunca propaga a falha para o caminho de digitação.

## Proibido

- Redesenhar tudo por evento de tecla.
- `malloc` no caminho de render.
- Decodificar imagem comprimida em runtime.
- Bloquear o produtor de eventos esperando o barramento.
- `sleep()`/`delay()` para "dar tempo" ao painel — use sincronismo real ou timeout.
- Assumir taxa de barramento sem medir: registre a taxa obtida em log de boot.

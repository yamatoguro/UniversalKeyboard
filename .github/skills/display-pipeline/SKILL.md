---
name: display-pipeline
description: |
  Procedimento para levar imagem a 120 displays: orçamento de banda medido, atualização por tecla suja, fila com coalescing, driver abstraído, DMA/SPI e degradação graciosa quando o barramento falha.
  Triggers: "display", "tela", "painel", "driver de tela", "SPI", "I2C", "DMA", "framebuffer", "refresh", "dirty", "tearing", "VSYNC", "banda", "render".
  NOT for: composição visual da tecla (use key-rendering), HID (use hid-gadget).
---

# Pipeline de exibição — procedimento

## Comece pelo orçamento, não pelo código

| Operação | Dados | ~40 MHz SPI |
|---|---|---|
| 1 tecla 128×128 RGB565 | 32 KB | ~6,5 ms |
| 10 teclas | 320 KB | ~65 ms |
| 120 teclas | 3,93 MB | **~786 ms** |

**Primeiro passo obrigatório:** medir a vazão real do barramento no hardware. `dd` no
dispositivo, ou contador de bytes/segundo no driver. Registre o número em log de boot.
Sem esse número, qualquer promessa de frame rate é ficção.

## Arquitetura

```text
produtor de eventos ──► dirty[key_idx] = 1 ──► fila (fixa)
                                                │
                                     thread de render
                                                │
                                    compõe só a tecla suja
                                                │
                                    display_driver->write_region()
```

## Interface do driver

```c
typedef struct {
    const char *name;
    uint16_t    width;
    uint16_t    height;
    uint8_t     color_bytes;          /* 2 = RGB565 */
    uk_status_t (*init)(void);
    uk_status_t (*write_region)(uint8_t key_idx, uint16_t x, uint16_t y,
                               uint16_t w, uint16_t h, const void *px, size_t stride);
    uk_status_t (*flush)(uint32_t timeout_ms);
    uk_status_t (*sleep)(void);
    uk_status_t (*wake)(void);
} display_driver_t;
```

O resto do sistema nunca vê o barramento. Trocar o painel = trocar essa struct.

## Fila e coalescing

- Fila de capacidade fixa (`UK_RENDER_QUEUE_CAPACITY`), sem alocação.
- Cheia ⇒ funde com entrada pendente da mesma tecla; se não existir, **descarta a mais
  antiga**. Nunca bloqueia o produtor.
- Bitset `dirty` de 120 bits é a fonte de verdade; a fila é só ordenação de prioridade.
- Ao fim do ciclo, limpar apenas os bits efetivamente desenhados.

## Orçamento por ciclo

- `UK_RENDER_BUDGET_BYTES` por iteração (ex.: 64 KB ≈ 13 ms).
- Estourou: para, devolve o restante para o próximo ciclo, mantém o bit sujo.
- Nunca um ciclo pode durar mais que o intervalo de scan — senão a digitação sente.

## Sincronismo e tearing

- Se o painel tem pino TE/VSYNC: sincronizar a escrita da região com ele.
- Sem TE: escrever região completa por tecla reduz o artefato; documentar a estratégia.
- `flush` só quando o chamador precisa de garantia (troca de layout, desligar).

## Degradação

1. Erro de escrita ⇒ retry limitado, contador incrementado.
2. N erros consecutivos ⇒ desliga render, mantém teclado, sinaliza estado.
3. Barramento travado não pode travar o laço de eventos: toda operação tem timeout.
4. Recuperação: tentar reinicializar o driver em intervalo controlado, não em laço apertado.

## Ao implementar um driver novo

- [ ] `init` idempotente e verifica presença do controlador.
- [ ] `write_region` respeita `stride` e não assume largura = tela.
- [ ] Todas as operações têm timeout.
- [ ] Nenhum `sleep()` para "dar tempo".
- [ ] Mede e loga a vazão obtida.
- [ ] Testado com fake de barramento (host) + bancada (real).

## Não faça

- Redesenhar tudo por evento.
- Alocar no caminho de render.
- Decodificar imagem comprimida em runtime no Pi.
- Bloquear o produtor esperando o barramento.
- Assumir 40 MHz sem medir.

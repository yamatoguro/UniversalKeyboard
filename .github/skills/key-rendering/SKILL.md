---
name: key-rendering
description: |
  Procedimento para compor a imagem de cada keycap: modelo de dados da tecla, atlas de fontes e ícones, canvas por tecla, dirty-rect, estados visuais (normal, pressionada, modificador ativo) e custo por recomposição.
  Triggers: "renderizar tecla", "keycap", "legenda", "fonte", "glifo", "atlas", "ícone", "tema", "pressionada", "highlight", "composição", "canvas".
  NOT for: barramento e fila de envio (use display-pipeline), tabela de layout por SO (use layout-adaptation).
---

# Renderização da tecla — procedimento

## Modelo de dados

Uma tecla não é uma imagem; é um **estado** que produz uma imagem.

```c
typedef struct {
    uint16_t usage_id;        /* o que sera enviado ao host */
    uint16_t legend_glyph;    /* indice no atlas de fonte */
    uint16_t icon_id;         /* 0 = sem icone */
    uint8_t  modifiers_mask;  /* modificadores exigidos pela macro */
    bool     active;          /* tecla existe neste layout? */
    bool     pressed;
    bool     latched;         /* layer/macro travada */
} key_state_t;
```

- `active == false` ⇒ tecla apagada/neutra (layout atual não usa essa posição física).
- `pressed` e `latched` mudam o visual; `usage_id` **não** muda o visual sozinho.
- Se o layout muda `legend_glyph`, a tecla está suja.

## Camadas de composição

```text
fundo do tema (cacheado, por tecla ou por atlas de variantes)
  └─ moldura / borda de estado
      └─ ícone (opcional)
          └─ legenda principal
              └─ legenda secundária (Shift, AltGr) quando o perfil pedir
```

- Fundo é o item mais caro. Cacheie variantes (normal, pressionada, ativa) por tecla e só
  recombine o que muda.
- Texto sempre via atlas de glifos — nunca rasterize fonte em runtime no Pi.
- Legenda secundária depende do modificador: se Shift pressiona, várias teclas ficam sujas
  de uma vez. É aceitável: são 120 bits de dirty, não 120 renderizações obrigatórias.

## Dirty-rect dentro da tecla

- Guarde, por tecla, o retângulo da última composição.
- Se só a legenda mudou, reescreva só a caixa da legenda.
- Só promova para região maior (tecla inteira) quando o custo de várias pequenas passar do
  custo de uma grande. Meça, não intua.

## Custo de referência

| Item | Custo |
|---|---|
| Tecla completa 128×128 RGB565 | 32 KB de escrita |
| Só a caixa da legenda (ex. 64×32) | 4 KB |
| Recompilar glifo | nunca em runtime |

Escrever 4 KB em vez de 32 KB é 8× menos banda. É a otimização que mais rende.

## Estados visuais

Defina explicitamente, no tema, como cada combinação aparece:

| Estado | Requisito |
|---|---|
| normal | legenda legível sobre fundo |
| pressionada | mudança perceptível sem depender de cor apenas (daltonismo) |
| latched / camada ativa | distintivo persistente |
| inativa | visivelmente apagada, não invisível |
| erro / link perdido | indicador global, não por tecla |

Contraste mínimo: garanta legibilidade real; não confie em "parece bom na minha tela".

## Ao implementar

- [ ] `key_state_t` é a única fonte de verdade; a imagem é derivada.
- [ ] Nenhuma chamada de I/O dentro da composição; ela devolve um ponteiro para o canvas.
- [ ] Canvas por tecla reutilizado; sem `malloc`.
- [ ] Atlas carregado uma vez, em formato nativo (sem decode em runtime).
- [ ] Mudança de tema ⇒ marcar todas as teclas sujas, em background.
- [ ] Teste host com canvas fake: dado `key_state_t`, verificar pixels de amostra.

## Não faça

- Guardar imagem como estado (a verdade é o estado; imagem é cache).
- Recompilar fonte no device.
- Reordenar a tabela de glifos sem versionar (quebra perfis salvos).
- Usar só cor para distinguir estado.

---
name: workflow-bugfix
description: |
  Workflow de correção de defeito em embarcados: reprodução obrigatória, teste que falha antes da correção, análise de causa raiz em camadas, correção mínima, verificação de regressão e registro.
  Triggers: "bug", "defeito", "corrigir", "falha", "não funciona", "tecla presa", "modificador travado", "tecla fantasma", "layout errado", "tela não atualiza", "CRC", "regressão".
  NOT for: funcionalidade nova (use workflow-feature), investigação sem reprodução (comece por reproduzir).
---

# Workflow — correção de defeito

## 0. Regra

**Sem reprodução não há correção.** Se não consegue reproduzir, o objetivo passa a ser
reproduzir — com instrumentação, não com tentativa e erro.

## 1. Reproduzir

- Qual é o comportamento observado vs esperado? Uma frase cada.
- Qual o caminho mínimo que dispara?
- É determinístico? Se não, qual a frequência estimada?
- Ocorre no host, no Pi, no firmware ou na integração?
- Sob qual layout/SO/host? (layout é fonte comum de falso bug)

Registre a reprodução: comando, entrada, hardware, versão.

## 2. Localizar a camada

Use os contadores de erro antes de adivinhar. Cada camada tem sua assinatura:

| Sintoma | Camada provável | Primeiro sinal |
|---|---|---|
| Tecla não chega | matriz/firmware | bit não muda no bitmap bruto |
| Tecla chega errada | protocolo/firmware | índice fora de faixa, frame com CRC ok |
| Caractere errado para a tecla certa | layout/`uk-gui` | layout ativo diverge |
| Tecla presa | HID/daemon | release não enviado |
| Legenda errada | render/layout | `legend_glyph` correto, layout errado |
| Tela não atualiza | display/render | fila cheia, driver com timeout |
| Tela atualiza devagar | orçamento | banda medida abaixo do previsto |
| Link instável | serial | CRC/timoout contando |

Não "corrija" no daemon um defeito da matriz.

## 3. Escrever o teste que falha

Antes da correção, um teste que reproduz:

```c
/* Falha antes da correcao: release perdido quando a fila enche. */
test_queue_full_preserves_release();
```

Se for hardware puro, o "teste" é um roteiro de bancada reproduzível, com o mesmo resultado
antes e depois.

## 4. Causa raiz

Pergunte "por quê" até chegar a uma causa que, se removida, faz o sintoma desaparecer.

Causas comuns neste projeto:

- release descartado por fila cheia;
- `g_stable` não limpo após reconexão;
- debounce aplicado duas vezes;
- `volatile` como sincronização;
- `LEN` não validado → escrita fora do buffer;
- CRC validado mas payload copiado antes;
- render síncrono no caminho de evento;
- layout não reavaliado em troca de janela;
- settle da matriz insuficiente para o cabo usado;
- perfil salvo com tabela de glifos antiga.

## 5. Corrigir minimamente

- Menor diff que remove a causa.
- Não misture refactor.
- Se a correção exige mudar contrato → ADR + bump de versão + os dois lados no mesmo PR.
- Se a correção é um band-aid, registre a causa raiz num `TODO(tau)` com a condição de
  remoção.

## 6. Verificar

- [ ] Teste novo passa.
- [ ] Teste antigo continua passando.
- [ ] Sanitizer limpo.
- [ ] Análise estática limpa.
- [ ] Cenário de bancada original não reproduz mais.
- [ ] Cenários vizinhos testados (a correção não criou novo caminho de erro).

## 7. Registrar

- `CHANGELOG.md`: seção `Corrigido`.
- Commit `fix(escopo): ...`.
- Se o bug foi possível por lacuna de teste, adicione o teste, não só a correção.
- Se revelou invariante não documentado, atualize o context map.

## Não faça

- Corrigir sem reproduzir.
- "Consertar" desligando o debounce, o CRC ou o validador de tamanho.
- Corrigir no consumidor um defeito do contrato.
- Fechar bug de hardware sem bancada.

---
name: code-review
description: |
  Revisão técnica antes de commit ou PR: invariantes, caminho de erro, ISR, concorrência, orçamento de render, fronteira entre repos, testes e convenções. Produz veredito com bloqueios explícitos.
  Triggers: "revisar", "code review", "antes do commit", "antes do PR", "checar mudança", "revisão de código", "self review", "veredito".
  NOT for: escrever o código (use a skill da área), rodar build (use cross-build).
---

# Code review — procedimento

## Ordem de leitura

1. Qual repo? A fronteira foi respeitada?
2. Qual invariante este diff pode quebrar?
3. Qual é o caminho de erro? Ele foi tratado?
4. O que mudou em orçamento (RAM, banda, latência)?

## Perguntas obrigatórias

**P0 — travamento do usuário**

- [ ] Existe caminho em que um modificador fica preso? (erro, timeout, sinal, reconexão)
- [ ] `SIGTERM`/`SIGINT` libera tudo antes de sair?
- [ ] Perda de link entra em `SAFE`?
- [ ] Reconexão emite release fantasma?

**P0 — corrupção e memória**

- [ ] Todo índice é validado antes da escrita?
- [ ] Todo `LEN`/tamanho vindo de fora é validado contra a capacidade?
- [ ] CRC é verificado antes de copiar payload?
- [ ] Buffer estático dimensionado para o pior caso (120 teclas simultâneas)?

**P1 — tempo real**

- [ ] Alguma ISR ficou mais longa, chamou biblioteca ou logou?
- [ ] Dado compartilhado com ISR tem `volatile` + seção crítica?
- [ ] `volatile` foi usado como sincronização em C++?
- [ ] Alguma alocação entrou no caminho de evento ou de render?
- [ ] Algum `delay()`/`sleep()` no caminho de evento?

**P1 — orçamento**

- [ ] O diff faz atualização de tela cheia em resposta a evento?
- [ ] A fila de render ganhou limite superior e coalescing?
- [ ] Foi medida a banda do barramento, ou assumida?
- [ ] A RAM do MCU cresceu? Quanto?

**P1 — fronteira**

- [ ] `uk-gui` linkou ou incluiu algo de `uk-pi0`/`uk-sc-integration`?
- [ ] O frame serial foi redefinido fora de `uk-sc-integration`?
- [ ] Header privado vazou entre repos?
- [ ] Mudança de contrato veio com ADR e bump de versão?

**P2 — qualidade**

- [ ] Função pública tem contrato (pré/pós/erros)?
- [ ] `uk_status_t` usado em vez de `-1`?
- [ ] Contador de erro adicionado para novo caminho de descarte?
- [ ] Comentário explica **por quê**, não **o quê**?
- [ ] Código morto/comentado foi removido?
- [ ] Warnings continuam como erro; nenhum `#pragma` silenciador novo?

**P2 — teste**

- [ ] Defeito corrigido veio com teste que falha sem a correção?
- [ ] Vetores de borda cobertos (vazio, máximo, truncado, corrompido)?
- [ ] Teste usa tempo injetado, sem `sleep()`?

## Formato do veredito

```text
Veredito: BLOQUEADO | APROVADO COM RESSALVAS | APROVADO

Bloqueios (P0):
- <arquivo:linha> — <invariante violado> — <correção necessária>

Ressalvas (P1/P2):
- ...

Não verificado:
- <o que precisa de bancada>
```

## Critérios de bloqueio

Bloqueia sempre:

- caminho que prende modificador;
- escrita fora de buffer possível;
- frame definido em dois lugares;
- render síncrono no caminho de evento;
- teste removido ou enfraquecido;
- `-Werror` rebaixado ou analisador desligado.

## Não faça

- Aprovar "parece certo".
- Reescrever o diff no review — aponte a correção.
- Bloquear por gosto pessoal de estilo que o `clang-format` já resolve.
- Aprovar hardware sem bancada: marque "não verificado".

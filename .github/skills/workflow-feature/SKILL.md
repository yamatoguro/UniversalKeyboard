---
name: workflow-feature
description: |
  Workflow para funcionalidade nova ponta a ponta: entender, decidir (ADR se aplicável), implementar na ordem de dependência entre repos, testar no host, validar em bancada e registrar.
  Triggers: "nova funcionalidade", "implementar feature", "adicionar suporte", "criar recurso", "feature ponta a ponta", "adicionar layout", "adicionar macro", "nova tecla".
  NOT for: correção de defeito (use workflow-bugfix), release (use workflow-release).
---

# Workflow — funcionalidade nova

## 1. Entender (antes de qualquer código)

Responda por escrito, curto:

1. Qual comportamento observável aparece para o usuário?
2. Qual repo é o **dono** da mudança? Quais repos são afetados?
3. Toca contrato? (frame serial, protocolo vendor, formato de perfil)
4. Qual invariante pode quebrar? (modificador preso, boot protocol, orçamento de render)
5. Depende de decisão pendente do context map? Se sim → **pare e pergunte**.

Se a resposta 5 for positiva, listar a decisão e as opções. Não invente.

## 2. Decidir

Crie ADR em `docs/adr/` se a mudança:

- altera contrato (frame, vendor protocol, formato de perfil);
- introduz dependência, biblioteca ou versão de linguagem;
- muda fronteira entre repos;
- tem custo de reversão alto.

ADR curto. Uma decisão. Alternativas com prós/contras.

## 3. Implementar na ordem

```text
uk-sc-integration  →  firmware AVR  →  uk-pi0  →  uk-gui
```

Motivo: contrato antes de produtor, produtor antes de consumidor, consumidor antes do
cliente externo. Inverter gera retrabalho.

Ordem interna por repo:

1. Header/contrato (API pública, tipos, erros).
2. Implementação.
3. Teste que falha sem a implementação.
4. Integração com o resto do módulo.
5. Instrumentação (contadores de erro, métricas).

## 4. Testar no host

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"
cmake --build build
ctest --test-dir build --output-on-failure
cppcheck --enable=warning,style,performance,portability --error-exitcode=1 -Iinclude src
```

Casos mínimos: caminho feliz, entrada inválida, limite (0 e máximo), timeout, e
comportamento após falha.

## 5. Validar em bancada (se toca hardware)

Use a skill `bench-test`. Se não houver bancada:

> "Implementado e testado no host; **não validado em bancada**. Falta verificar: <lista>."

Nunca declare pronto o que não foi executado.

## 6. Registrar

- ADR criado/atualizado.
- `CHANGELOG.md` do repo com entrada em `Adicionado`.
- `docs/context-map.md` se mudou fronteira, contrato, stack ou estado das decisões.
- Commit com `feat(escopo): ...` e `Refs: ADR-NNNN`.
- Um commit por repo.

## Checklist final

- [ ] Requisito reformulado em uma frase.
- [ ] Ordem de repos respeitada.
- [ ] Contrato versionado, se mudou.
- [ ] Teste cobre o comportamento novo e falha sem ele.
- [ ] Sanitizer limpo.
- [ ] Análise estática limpa.
- [ ] Bancada: executada ou declarada como pendente.
- [ ] ADR / CHANGELOG / context map atualizados.

## Não faça

- Começar pelo `uk-gui` e adaptar o firmware depois.
- Mudar o frame serial e "ajustar" os dois lados com strings mágicas.
- Fechar sem teste.
- Declarar bancada sem ter bancada.

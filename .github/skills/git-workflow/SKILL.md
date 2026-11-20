---
name: git-workflow
description: |
  Procedimento de git no workspace multi-repo: um repo por componente, convenção de branch e commit, versionamento semântico, changelog e relação entre mudanças que atravessam repositórios.
  Triggers: "git", "branch", "commit", "merge", "tag", "versão", "semver", "changelog", "multi-repo", "PR", "rebase", "release".
  NOT for: empacotamento e publicação (use workflow-release).
---

# Git — procedimento

## Topologia

Três repositórios git independentes, sem submódulo e sem monorepo:

```text
uk-gui/            um repo
uk-pi0/            um repo
uk-sc-integration/ um repo
```

A raiz `UniversalKeyboard/` **não** é repositório. Não tente commitar nela.

## Regra de ouro multi-repo

Mudança que atravessa repos gera **um commit por repo**, na ordem de dependência:

```text
uk-sc-integration  (contrato + firmware)
      ↓
uk-pi0             (consumidor)
      ↓
uk-gui             (cliente externo)
```

Cada mensagem referencia as outras: `ver uk-sc-integration@abc1234`.

## Branch

```text
main                 ← sempre construível
feat/<escopo>-<slug>
fix/<escopo>-<slug>
perf/<escopo>-<slug>
```

- Escopo = módulo (`matrix`, `hid`, `render`, `proto`, `layout`, `gui`).
- Sem branch de release por enquanto; tag em `main`.

## Commit

```text
tipo(escopo): descrição no imperativo

corpo opcional: por que, não o que.
Refs: ADR-0003
```

| Tipo | Uso |
|---|---|
| `feat` | comportamento novo |
| `fix` | defeito |
| `perf` | performance sem mudar comportamento |
| `refactor` | estrutura sem mudar comportamento |
| `test` | teste |
| `docs` | documentação |
| `build` | build, toolchain, CI |
| `chore` | manutenção |

- Um commit = uma intenção. Não misture refactor com feat.
- Corpo explica **por quê**; o diff já mostra o quê.
- Nunca commite: `build/`, `*.o`, `*.elf`, `*.hex`, `.env`, credencial, dump.

## Tag e versão

Semver: `vMAJOR.MINOR.PATCH`.

| Componente | MAJOR muda quando |
|---|---|
| `uk-sc-integration` | layout de frame serial ou API pública quebra |
| `uk-pi0` | protocolo vendor ou formato de perfil quebra |
| `uk-gui` | formato de perfil salvo quebra |

- Tag anotada: `git tag -a v1.2.0 -m "..."`.
- Tag só em `main`, após CI verde.
- Versão de protocolo é **separada** da versão do pacote: `VER` no frame tem seu próprio ciclo.

## Rebase e limpeza

- `git pull --rebase` em branch própria.
- Nunca force-push em `main`.
- Squash antes do merge se o branch tiver ruído (`wip`, `fix typo`).
- Não reescreva histórico já publicado.

## Antes de commitar

```bash
git status --short
git diff --stat
# revisar o diff real, não a memoria do que foi feito
git diff
```

- Confirme que o build e os testes rodaram **neste** estado.
- Confirme que nenhum arquivo gerado entrou.

## Não faça

- `git add .` sem olhar.
- Commitar em dois repos com a mesma mensagem quando são mudanças diferentes.
- Commitar direto em `main` em mudança não trivial.
- Force-push em `main`.
- Tag antes do CI verde.

---
description: 'Regras para build, teste e CI: CMake/Ninja por repo, cross-compile ARM, AVR, sanitizers, análise estática e comportamento dos workflows.'
applyTo: '**/CMakeLists.txt, **/*.cmake, **/CMakePresets.json, **/Makefile, **/Makefile.*, **/platformio.ini, **/arduino-cli.yaml, **/.github/workflows/*.yml, **/tests/**, **/test/**'
---

# Build, testes e CI

## Princípio

CI existe para detectar quebra antes do usuário. Workflow que passa sem compilar nada é pior
que nenhum: cria confiança falsa.

## Build por repo

| Repo | Build |
|---|---|
| `uk-sc-integration` | CMake (biblioteca portável + testes host) + `arduino-cli` para firmware |
| `uk-pi0` | CMake (binário Linux) + testes host |
| `uk-gui` | **stack em aberto** — não presumir; detectar e reportar |

Nunca crie build raiz unificado. Cada repo é independente.

## CMake

- `cmake_minimum_required(VERSION 3.20)`; gerador Ninja.
- Warnings como erro via alvo `INTERFACE`, nunca `add_compile_options` global:

```cmake
add_library(uk_warnings INTERFACE)
target_compile_options(uk_warnings INTERFACE
    -Wall -Wextra -Werror -Wconversion -Wshadow -Wcast-align -Wpedantic)
```

- `target_include_directories` com `PUBLIC`/`PRIVATE` corretos.
- Toolchain file em `cmake/toolchains/`; nunca sobrescrever `CC` no shell.
- Opções via `option(UK_BUILD_TESTS "..." ON)`.

## Testes

- `ctest --test-dir build --output-on-failure`.
- Todo defeito corrigido ganha teste que **falha antes** da correção.
- Teste de protocolo cobre: frame válido, CRC inválido, truncado, `LEN` máximo, `0xA5` no
  payload, ruído antes do SOF, timeout intra-frame.
- Teste de driver usa fake de I/O. Teste que exige hardware vai para bancada.
- Sem `sleep()` real: injete o relógio.

```c
key_matrix_init(&m, fake_io(), 5u /* debounce_ms */);
fake_io_set_pressed(0, true);
matrix_poll(&m, 10u);
assert(fifo_count(&m.events) == 0);   /* ainda em debounce */
matrix_poll(&m, 30u);
assert(fifo_count(&m.events) == 1);
```

- Sanitizers no job de teste: `-fsanitize=address,undefined -fno-omit-frame-pointer`.

## Análise estática

```bash
cppcheck --enable=warning,style,performance,portability \
         --error-exitcode=1 --inline-suppr --std=c11 -Iinclude src
clang-tidy -p build src/*.c src/*.cpp
```

- Supressão exige comentário com justificativa e dono.
- Nunca supressão global de categoria.

## Firmware

- `arduino-cli compile --fqbn "$UK_FQBN" --warnings all`.
- Reportar flash **e** RAM no log.
- Upload nunca no CI: é passo de bancada.

## Workflows

- Um workflow por repo: `<repo>/.github/workflows/ci.yml`.
- `permissions: contents: read` no topo.
- Actions fixadas por major (`@v4`), nunca `@master`.
- Auto-detecta o build; repo sem build passa com **aviso explícito**, não em silêncio.
- Sem segredo; sem `pull_request_target` com checkout de código do PR.
- Sem `|| true` e sem `continue-on-error` no job principal.

## Proibido

- Workflow que não compila código existente sem avisar.
- Ignorar falha de teste.
- `-w`/`-Wno-error` adicionado só para o CI passar.
- Commitar artefato de build (`build/`, `*.o`, `*.elf`, `*.hex`).

---
name: cross-build
description: |
  Procedimento de build e análise estática: CMake/Ninja por repo, cross-compile para ARM (armhf/arm64), toolchain AVR, sanitizers, cppcheck e clang-tidy.
  Triggers: "build", "compilar", "cmake", "ninja", "cross-compile", "toolchain", "armhf", "arm64", "aarch64", "avr-gcc", "sanitizer", "ASan", "UBSan", "clang-tidy", "cppcheck", "warnings".
  NOT for: comportamento de CI (use workflow-release), validação em hardware (use bench-test).
---

# Build e análise — procedimento

## Regra

Cada repo tem build próprio. **Não existe build raiz.**

## Build nativo (host / Pi)

```bash
cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-Wall -Wextra -Werror -Wconversion -Wshadow" \
      -DCMAKE_CXX_FLAGS="-Wall -Wextra -Werror -Wconversion -Wshadow -Wold-style-cast"
cmake --build build
ctest --test-dir build --output-on-failure
```

- Warnings como erro em alvo de biblioteca via `INTERFACE`, não `add_compile_options` global.
- `RelWithDebInfo` para bancada; `Debug` para testar com sanitizer.

## Cross-compile para o Pi Zero 2W

Download a decisão 32/64-bit antes:

| SO do Pi | Toolchain | Triple |
|---|---|---|
| 64-bit | `gcc-aarch64-linux-gnu` | `aarch64-linux-gnu` |
| 32-bit | `gcc-arm-linux-gnueabihf` | `arm-linux-gnueabihf` |

`cmake/toolchains/aarch64.cmake`:

```cmake
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
```

```bash
cmake -S . -B build-arm64 -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/aarch64.cmake
cmake --build build-arm64
```

- Teste de unidade roda no host; binário cross é para bancada.
- Nunca sobrescreva `CC`/`CXX` no shell como atalho — use toolchain file.

## AVR

```bash
avr-gcc -mmcu=atmega328p -DF_CPU=16000000UL -Os -std=c11 \
        -Wall -Wextra -Werror -flto -o fw.elf src/*.c
avr-size --format=avr --mcu=atmega328p fw.elf
avr-objcopy -O ihex -R .eeprom fw.elf fw.hex
```

- Reporte **flash e RAM** sempre.
- `-flto` só depois de validar que o timing crítico não mudou.

## Sanitizers

```bash
cmake -S . -B build-asan -G Ninja -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -g" \
      -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -g"
```

- Obrigatório no build de teste host.
- TSan quando houver concorrência real (daemon).
- Sanitizer não roda em cross para AVR.

## Análise estática

```bash
cppcheck --enable=warning,style,performance,portability \
         --error-exitcode=1 --inline-suppr --std=c11 -Iinclude src

clang-tidy -p build src/*.c src/*.cpp
```

- Supressão exige comentário com justificativa e dono.
- Nunca supressão global de categoria.

## Ordem de diagnóstico quando o build quebra

1. Erro de compilação → corrija a causa, não desligue o warning.
2. Aviso novo → entenda antes de silenciar.
3. Erro de link → verifique fronteira de repo (header privado vazando).
4. Falha de teste → reproduza isolado, com `-DCMAKE_BUILD_TYPE=Debug`.
5. Só então considere mudar flags — e registre o motivo.

## Não faça

- Build raiz unificado.
- `-w` para "passar".
- Cross-compile sem toolchain file.
- Rodar binário cross no host e chamar de teste.
- Ignorar aviso de uso de RAM no AVR.

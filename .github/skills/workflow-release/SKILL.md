---
name: workflow-release
description: |
  Workflow de release e CI: pré-condições de tag, build reprodutível dos três repos, artefatos permitidos, atualização de firmware, changelog, versionamento de protocolo e checklist de empacotamento.
  Triggers: "release", "lançar versão", "tag", "empacotar", "build reproduzível", "artefato", "atualizar firmware", "CI", "workflow", "pipeline", "publicar".
  NOT for: git do dia a dia (use git-workflow), validar hardware (use bench-test).
---

# Workflow — release e CI

## Ordem de release

```text
1. uk-sc-integration  (contrato + firmware)
2. uk-pi0             (daemon)
3. uk-gui             (painel)
```

Um consumidor nunca é publicado antes do contrato que ele consome.

## Pré-condições

- [ ] `main` verde nos três repos.
- [ ] CHANGELOG atualizado em cada repo tocado.
- [ ] Nenhuma decisão pendente do context map bloqueando o artefato.
- [ ] Versão de protocolo decidida (pode não mudar).
- [ ] Bancada executada para o que toca hardware — ou release marcada como `alpha`.
- [ ] Nenhum `TODO` bloqueante sem dono.
- [ ] Teste de modificador preso executado e registrado.

## Build reprodutível

```bash
# uk-sc-integration
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build && ctest --test-dir build --output-on-failure

# firmware
arduino-cli compile --fqbn "$UK_FQBN" --warnings all firmware/
avr-size --format=avr --mcu="$UK_MCU" firmware/build/*/*.elf

# uk-pi0 (cross)
cmake -S . -B build-arm64 -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/aarch64.cmake
cmake --build build-arm64
```

- Versões de toolchain registradas no release notes.
- `SOURCE_DATE_EPOCH` definido se o build embutir data.
- Nenhum passo depende de rede além de baixar toolchain.

## Artefatos permitidos

| Repo | Artefatos |
|---|---|
| `uk-sc-integration` | `fw.hex`, `fw.elf` (debug), `libuk_sc.a`, headers públicos |
| `uk-pi0` | binário `uk-pi0`, unit systemd, config de exemplo |
| `uk-gui` | pacote da plataforma (quando a stack for decidida) |

Nunca publique: `build/`, objeto solto, dump, arquivo de credencial, `.env`.

## Versionamento

- Tag semver `vMAJOR.MINOR.PATCH`, anotada, em `main`.
- Versão de **protocolo** é independente da versão de pacote. Registre as duas no release note.
- Firmware e daemon que falam o mesmo `VER` de frame devem ser publicados juntos.

## Atualização de firmware

`[A VALIDAR]` — decisão pendente no context map.

Enquanto não decidido:

- documente o método usado manualmente (ICSP, bootloader, via Pi);
- nunca publique firmware que exija desmontar o teclado sem avisar;
- inclua o procedimento de recuperação (como voltar se a atualização falhar).

## CI por repo

Cada repo tem `<repo>/.github/workflows/ci.yml` que:

- auto-detecta o build (CMake, `platformio.ini`, `arduino-cli.yaml`);
- se não houver build no repo, **passa com aviso explícito** — não finge que compilou;
- roda warnings como erro, teste e análise estática;
- tem `permissions: contents: read` e actions fixadas por major.

Ver os workflows criados em `uk-*/.github/workflows/ci.yml`.

## Checklist de publicação

- [ ] Build nos três repos, na ordem.
- [ ] Tag criada com anotação.
- [ ] Release notes com: versão de protocolo, versão de firmware, versão de daemon,
      versões de toolchain, limitações conhecidas.
- [ ] Artefatos anexados e verificados por download.
- [ ] Procedimento de rollback escrito.
- [ ] Context map atualizado se o estado das decisões mudou.

## Não faça

- Publicar consumidor antes do contrato.
- Taggear com CI vermelho.
- Publicar binário sem registrar a toolchain.
- Fingir release estável sem bancada.
- Incluir `build/` no artefato.

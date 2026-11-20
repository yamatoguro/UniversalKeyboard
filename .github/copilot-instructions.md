# UniversalKeyboard — instruções do projeto

Teclado físico full-size de **120 teclas, cada keycap com sua própria tela**, cujo layout
exibido se adapta ao host (ABNT2, ANSI US, …). Três repositórios: `uk-gui` (painel no host),
`uk-pi0` (daemon no Pi Zero 2W), `uk-sc-integration` (contrato Pi↔Arduino + firmware).

Leia [`docs/context-map.md`](../docs/context-map.md) antes de qualquer alteração estrutural.

## O fato que governa o projeto

HID transporta **usage IDs**, não caracteres. O SO do host aplica o layout. A legenda
correta de uma tecla depende do layout ativo do host — informação que **não existe no
protocolo HID** e chega ao teclado pelo canal vendor-specific, enviada pelo `uk-gui`.

Não tente inferir o layout dentro do firmware nem do daemon.

## Prioridade de falha (nesta ordem)

1. **Modificador não pode travar.** Tecla presa inutiliza a máquina do usuário.
2. **Digitar não depende de desenhar.** Falha de render degrada a aparência, nunca o teclado.
3. **Digitar não depende do `uk-gui`.** Sem painel, opera com o último perfil persistido.
4. **Boot protocol funciona sempre.** BIOS, UEFI, KVM, instalador.

## Invariantes

- Link perdido, timeout, exceção, `SIGTERM`/`SIGINT` ou watchdog ⇒ liberar todas as
  teclas/modificadores, entrar em `SAFE`.
- **Nunca** redesenhar as 120 teclas por evento de tecla; atualização é por tecla suja.
- Sem alocação dinâmica após init no MCU.
- ISR curta: sem log, sem bloqueio, sem `malloc`, sem espera ativa.
- Dado compartilhado com ISR: `volatile` + seção crítica (ou atômico).
- Toda entrada externa é hostil: validar tamanho, faixa e CRC antes de usar.

## Fronteiras entre repositórios

- `uk-gui` é cliente externo: fala **somente** pelo protocolo HID vendor-specific. Não
  linka biblioteca de `uk-pi0` nem de `uk-sc-integration`.
- `uk-sc-integration` é dono exclusivo do frame serial. Mudança de frame ⇒ ADR + bump de
  versão de protocolo.
- `uk-pi0` consome o contrato; nunca redefine o layout de frame localmente.
- Nenhum repo inclui header privado de outro.

## Idioma

| Artefato | Idioma |
|---|---|
| Identificadores, API pública, log técnico | Inglês |
| Comentários de intenção, ADR, README, commit | Português (pt-BR) |
| Texto na tela do usuário | Localizável, nunca hardcoded na lógica |

## Build

Cada repo tem build próprio. Não existe build raiz.

```bash
# uk-pi0 / uk-sc-integration (quando houver CMakeLists.txt)
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build
ctest --test-dir build --output-on-failure

# firmware AVR
arduino-cli compile --fqbn arduino:avr:uno --warnings all .

# estático
cppcheck --enable=warning,style,performance,portability --error-exitcode=1 -Iinclude src
clang-tidy -p build src/*.c
```

Se o build ainda não existe no repo, diga isso em vez de inventar comandos.

## Commits

`tipo(escopo): descrição no imperativo`

```text
feat(matrix): adiciona debounce por timestamp
fix(hid): libera modificadores ao receber SIGTERM
perf(render): reduz recomposicao a teclas sujas
docs(adr): registra escolha de CRC16-CCITT
test(proto): cobre resync apos frame corrompido
```

Tipos: `feat`, `fix`, `docs`, `test`, `build`, `refactor`, `perf`, `chore`.
Escopo = módulo, não repo.

## Nunca

- Baixar `-Werror`, desligar `clang-tidy`/`cppcheck` ou apagar teste para passar.
- Commitar binário, `.elf`, `.hex`, dump ou credencial.
- Introduzir dependência grande em MCU sem ADR.
- Usar `delay()`/`sleep()` no caminho de evento.
- Assumir pinagem ou part number de display. Perguntar.
- Presumir a stack do `uk-gui` — está em aberto.

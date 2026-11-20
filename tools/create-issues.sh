#!/usr/bin/env bash
#
# Cria o backlog inicial do UniversalKeyboard como issues no GitHub.
#
# Pre-requisito (uma vez):
#   gh auth login          # https://cli.github.com
#
# Uso:
#   ./tools/create-issues.sh             # cria o que faltar (idempotente)
#   DRY_RUN=1 ./tools/create-issues.sh   # so lista o que faria
#   UK_OWNER=outro ./tools/create-issues.sh
#
# Reexecutar e seguro: issues com o mesmo titulo sao ignoradas.

set -euo pipefail

OWNER="${UK_OWNER:-yamatoguro}"
DRY_RUN="${DRY_RUN:-0}"

HAVE_GH=0
command -v gh >/dev/null 2>&1 && HAVE_GH=1

if [ "$HAVE_GH" = 0 ] && [ "$DRY_RUN" = 0 ]; then
    echo "erro: gh nao encontrado. Instale https://cli.github.com e rode 'gh auth login'." >&2
    exit 1
fi

declare -A EXISTING=()
CREATED=0
SKIPPED=0

label_color() {
    case "$1" in
        adr)      echo "5319e7" ;;
        bench)    echo "0e8a16" ;;
        firmware) echo "1d76db" ;;
        protocol) echo "bfd4f2" ;;
        daemon)   echo "c5def5" ;;
        core)     echo "006b75" ;;
        panel)    echo "d4c5f9" ;;
        render)   echo "f9d0c4" ;;
        hid)      echo "fef2c0" ;;
        test)     echo "bfdadc" ;;
        scaffold) echo "ededed" ;;
        blocked)  echo "b60205" ;;
        *)        echo "ededed" ;;
    esac
}

label_desc() {
    case "$1" in
        adr)      echo "Decisao arquitetural que exige ADR" ;;
        bench)    echo "Validacao em hardware real" ;;
        firmware) echo "Firmware AVR / Arduino" ;;
        protocol) echo "Contrato serial ou HID vendor" ;;
        daemon)   echo "Daemon uk-pi0" ;;
        core)     echo "Nucleo do daemon: estado, laco, sinais" ;;
        panel)    echo "Painel uk-gui no host" ;;
        render)   echo "Pipeline de exibicao e composicao" ;;
        hid)      echo "USB HID gadget" ;;
        test)     echo "Testes automatizados" ;;
        scaffold) echo "Estrutura inicial do repositorio" ;;
        blocked)  echo "Bloqueado por decisao pendente" ;;
        *)        echo "" ;;
    esac
}

ensure_label() {
    local repo="$1" name="$2"
    [ "$HAVE_GH" = 0 ] && return 0
    gh label create "$name" --repo "$OWNER/$repo" \
       --color "$(label_color "$name")" \
       --description "$(label_desc "$name")" >/dev/null 2>&1 || true
}

load_existing() {
    local repo="$1"
    [ "$HAVE_GH" = 0 ] && return 0
    while IFS= read -r t; do
        [ -n "$t" ] && EXISTING["$repo::$t"]=1
    done < <(gh issue list --repo "$OWNER/$repo" --state all --limit 500 \
                     --json title --jq '.[].title' 2>/dev/null || true)
}

create() {
    local repo="$1" title="$2" label="$3" body="$4"

    if [ -n "${EXISTING["$repo::$title"]:-}" ]; then
        echo "  = ja existe   [$repo] $title"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    if [ "$DRY_RUN" = 1 ]; then
        echo "  + [dry]       [$repo] $title"
        CREATED=$((CREATED + 1))
        return 0
    fi

    ensure_label "$repo" "$label"
    local url
    if url=$(gh issue create --repo "$OWNER/$repo" --title "$title" \
                             --body "$body" --label "$label"); then
        echo "  + criado      [$repo] $title"
        CREATED=$((CREATED + 1))
        if [ -n "${UK_PROJECT:-}" ] && [ -n "$url" ]; then
            gh project item-add "$UK_PROJECT" --owner "$OWNER" --url "$url" >/dev/null 2>&1 \
                && echo "    -> projeto $UK_PROJECT" \
                || echo "    ! nao entrou no projeto $UK_PROJECT" >&2
        fi
    else
        echo "  ! falhou      [$repo] $title" >&2
    fi
}

# issue <repo> <titulo> <label> <<'EOF' ... EOF
issue() {
    local repo="$1" title="$2" label="$3"
    local body
    body="$(cat)"
    create "$repo" "$title" "$label" "$body"
}

for r in UniversalKeyboard uk-sc-integration uk-pi0 uk-gui; do
    load_existing "$r"
done

# ---------------------------------------------------------------------------
# Raiz: decisoes que bloqueiam os repos de produto
# ---------------------------------------------------------------------------

echo "Decisoes (UniversalKeyboard)"

issue UniversalKeyboard "[ADR-0001] Decidir stack do uk-gui" adr <<'EOF'
## Contexto

O ADR-0001 propoe Rust com nucleo `uk-host` independente de toolkit, e separa o caminho de I/O (precisa ser nativo) do caminho de UI (nao precisa).

Status `Proposto`. **Bloqueia todo o repositorio `uk-gui`.**

## O que fazer

- [ ] Revisar as quatro alternativas: Rust + UI nativa, Rust + Tauri, C++/Qt 6, C + toolkit por SO
- [ ] Confirmar ou trocar a recomendacao
- [ ] Preencher decisores e mudar o status para `Aceito`
- [ ] Se aceito: abrir os itens de scaffold no `uk-gui`

## Pronto quando

ADR com status `Aceito`, decisores preenchidos e metricas de verificacao acordadas.

## Referencias

- https://github.com/yamatoguro/UniversalKeyboard/blob/main/docs/adr/0001-stack-do-uk-gui.md
- Context map, secoes 5 e 12
EOF

issue UniversalKeyboard "[ADR-0002] Ratificar frame do link serial v1" adr <<'EOF'
## Contexto

O ADR-0002 fixa CRC16-CCITT-FALSE, stuffing de `0xA5`, `UK_PROTO_MAX_PAYLOAD=32` e deriva o buffer de TX (75 B) do formato.

Status `Proposto`. Bloqueia `uk-sc-integration`, firmware e o parser do daemon.

## O que fazer

- [ ] Revisar o formato de frame e os tipos de mensagem
- [ ] Confirmar stuffing vs COBS
- [ ] Confirmar heartbeat 100 ms / timeout 250 ms
- [ ] Mudar o status para `Aceito`

## Pronto quando

Frame v1 congelado como contrato, com vetor de teste `CRC("123456789") == 0x29B1` registrado.

## Referencias

- https://github.com/yamatoguro/UniversalKeyboard/blob/main/docs/adr/0002-frame-do-link-serial.md
EOF

issue UniversalKeyboard "[ADR-0003] Ratificar protocolo HID vendor-specific" adr <<'EOF'
## Contexto

O ADR-0003 define report de 64 B, mensagens com `MAGIC/VER/OPCODE/SEQ/LEN/PAYLOAD/CRC16` e transferencia transacional.

Conclusao central: o canal transporta **configuracao semantica**, nao framebuffer (112 telas por HID levariam ~56 s).

## O que fazer

- [ ] Revisar os opcodes e o conjunto de erros
- [ ] Confirmar o limite de 57 B de payload por mensagem
- [ ] Definir o limite de `total_len` por blob
- [ ] Mudar o status para `Aceito`

## Pronto quando

Opcode e formato congelados; `uk-gui` e `uk-pi0` implementam contra o mesmo documento.

## Referencias

- https://github.com/yamatoguro/UniversalKeyboard/blob/main/docs/adr/0003-protocolo-hid-vendor.md
EOF

issue UniversalKeyboard "[ADR] Escolher display: part number, resolucao e barramento" adr <<'EOF'
## Contexto

O orcamento do projeto depende disso: 128x128 RGB565 custa 32 KB por tecla, 3,67 MB para as 112. A vazao real do barramento define o que e viavel.

Nenhum part number foi definido. **Nao assumir modelo nem pinagem.**

## O que fazer

- [ ] Levantar candidatos (controlador por tecla, shift-register, SPI direto, DSI)
- [ ] Comparar custo, vazao e complexidade de fiacao para 112 unidades
- [ ] Medir vazao de um prototipo
- [ ] Registrar decisao em ADR

## Pronto quando

ADR `Aceito` com part number, resolucao, barramento e vazao medida.

## Referencias

- Context map, secao 4 (orcamento) e decisao 4
- Skill `display-pipeline`
EOF

issue UniversalKeyboard "[ADR] Escolher AVR: ATmega328P ou ATmega32U4" adr <<'EOF'
## Contexto

A matriz 8x14 exige 22 GPIOs. O ATmega328P tem 2 KB de SRAM e UART; o ATmega32U4 tem USB nativo, o que muda o link com o Pi.

## O que fazer

- [ ] Confirmar requisito de GPIO (22 para a matriz + link + status)
- [ ] Comparar 328P vs 32U4 para RAM, USB e custo
- [ ] Decidir o transporte com o Pi (UART vs USB CDC)
- [ ] Registrar em ADR

## Pronto quando

ADR `Aceito` com o MCU escolhido e o transporte definido.

## Referencias

- Context map, decisao 6
- Skill `arduino-firmware`
EOF

issue UniversalKeyboard "[ADR] Escolher SO do Pi: armhf (32-bit) ou arm64 (64-bit)" adr <<'EOF'
## Contexto

A escolha define o toolchain de cross-compile, a unit do systemd e a ABI do Assembly.

## O que fazer

- [ ] Verificar disponibilidade de `dwc2`/`libcomposite` em cada versao
- [ ] Comparar RAM disponivel (o Pi Zero 2W tem 512 MB)
- [ ] Decidir e registrar em ADR

## Pronto quando

ADR `Aceito`; `cmake/toolchains/` com o arquivo correspondente.

## Referencias

- Context map, decisao 5
- Skill `cross-build`
EOF

issue UniversalKeyboard "[ADR] Definir pinagem da matriz 8x14 e do barramento de display" adr <<'EOF'
## Contexto

Pinagem errada queima hardware. Toda a pinagem precisa estar em `board_pins.h`, verificada em tempo de compilacao.

## O que fazer

- [ ] Definir mapa pino -> linha/coluna para as 112 teclas
- [ ] Definir pinos do barramento de display e do link com o Pi
- [ ] Reservar e documentar pinos de UART/SPI/I2C/status
- [ ] Adicionar `static_assert` de conflito

## Pronto quando

`board_pins.h` versionado, com comentario do conector fisico, e build falhando em conflito.

## Referencias

- Skill `input-matrix`
- `.github/instructions/arduino.instructions.md`
EOF

issue UniversalKeyboard "[ADR] Definir layouts suportados no v1" adr <<'EOF'
## Contexto

A legenda exibida depende do layout ativo do host. Cada layout suportado exige uma tabela `usage_id -> legenda` validada.

## O que fazer

- [ ] Definir o conjunto minimo (ABNT2 e ANSI US sao candidatos obvios)
- [ ] Levantar as teclas problematicas: `AltGr`, teclas mortas, `c` cedilha, `ABNT_C1/C2`, Enter ISO vs ANSI
- [ ] Definir o comportamento para teclas inexistentes no layout ativo

## Pronto quando

Lista fechada, com tabela versionada e caso de teste por layout.

## Referencias

- Skill `layout-adaptation`
- Context map, secao 7
EOF

issue UniversalKeyboard "[ADR] Definir protocolo de update de firmware" adr <<'EOF'
## Contexto

Atualizar 112 teclas montadas nao pode exigir desmontar o teclado. Sem decisao, o release nao tem procedimento de rollback.

## O que fazer

- [ ] Comparar ICSP, bootloader serial, DFU e update via Pi
- [ ] Definir como recuperar um update que falhou
- [ ] Registrar em ADR

## Pronto quando

Procedimento reproduzivel, com recuperacao documentada.

## Referencias

- Skill `workflow-release`
- Context map, decisao 9
EOF

# ---------------------------------------------------------------------------
# Raiz: validacao em bancada (transversal aos repos)
# ---------------------------------------------------------------------------

echo "Bancada (UniversalKeyboard)"

issue UniversalKeyboard "[bench] Bring-up eletrico: alimentacao, matriz completa e brownout" bench <<'EOF'
## Contexto

112 displays podem derrubar a alimentacao no boot. Antes de qualquer software, o hardware precisa ser medido.

## O que fazer

- [ ] Medir tensao em carga maxima dos 112 displays
- [ ] Verificar corrente de pico no boot
- [ ] Testar cada uma das 112 teclas individualmente
- [ ] Testar pares e triades simultaneas (verifica diodo)

## Pronto quando

Medicoes registradas com foto do setup e valores, nao impressao.

## Referencias

- Skill `bench-test`
EOF

issue UniversalKeyboard "[bench] Medir banda real do barramento de display" bench <<'EOF'
## Contexto

O orcamento de ~730 ms por tela cheia assume ~40 MHz SPI (~5 MB/s). Se a vazao real for menor, todo o orcamento muda.

## O que fazer

- [ ] Medir bytes/s reais no barramento escolhido
- [ ] Medir tempo de atualizacao de 1, 10 e 112 teclas
- [ ] Registrar a vazao no log de boot do daemon

## Pronto quando

Numero medido, comparado ao orcamento, e registrado no context map.

## Referencias

- Context map, secao 4
- Skill `display-pipeline`
EOF

issue UniversalKeyboard "[bench] Medir latencia de evento ate relatorio HID" bench <<'EOF'
## Contexto

Latencia previsivel importa mais que throughput. Precisa ser medida, nao estimada.

## O que fazer

- [ ] Instrumentar com pino de GPIO no inicio e no fim do caminho
- [ ] Medir com analisador logico: acionamento -> frame serial -> relatorio HID
- [ ] Registrar p50 e p99

## Pronto quando

Numero medido e documentado; regressao futura comparavel.

## Referencias

- Skill `bench-test`
EOF

issue UniversalKeyboard "[bench] Validar HID em BIOS/UEFI/KVM e nos tres SO" bench <<'EOF'
## Contexto

O teclado precisa funcionar antes de existir driver ou SO. Se o boot protocol falhar, o resto e irrelevante.

## O que fazer

- [ ] Enumera e digita em BIOS/UEFI real
- [ ] Funciona em IP-KVM
- [ ] Funciona no instalador de SO
- [ ] Windows, Linux e macOS com ABNT2 e ANSI US

## Pronto quando

Checklist completo com evidencia por item.

## Referencias

- Skill `hid-gadget`
- `.github/instructions/hid-usb.instructions.md`
EOF

issue UniversalKeyboard "[bench] Teste de modificador preso em todos os cenarios" bench <<'EOF'
## Contexto

Modificador preso inutiliza a maquina do usuario. E o pior defeito possivel do projeto.

## O que fazer

- [ ] Segurar Shift e enviar `SIGTERM` ao daemon: Shift e liberado?
- [ ] Repetir com perda de link serial
- [ ] Repetir com desconexao do USB do host
- [ ] Repetir com reboot do Pi e com watchdog

## Pronto quando

Todos os cenarios liberam o modificador, com evidencia registrada por cenario.

## Referencias

- Context map, invariante 1
- Skill `bench-test`
EOF

# ---------------------------------------------------------------------------
# uk-sc-integration: contrato serial + firmware AVR
# ---------------------------------------------------------------------------

echo "uk-sc-integration"

issue uk-sc-integration "[scaffold] Estrutura CMake, include/src/tests e .clang-format" scaffold <<'EOF'
## Contexto

O repo ainda so tem README. O CI ja detecta CMake e passa sem compilar nada quando ele nao existe.

## O que fazer

- [ ] `CMakeLists.txt` com `cmake_minimum_required(3.20)`, C11 e alvo `INTERFACE` de warnings
- [ ] Arvore `include/`, `src/`, `tests/`, `firmware/`, `tools/`
- [ ] `.clang-format` e teste de fumaca com `ctest`
- [ ] `option(UK_BUILD_TESTS ON)`

## Pronto quando

`cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build` passa.

## Referencias

- `.github/instructions/build-and-tests.instructions.md`
- Skill `cross-build`
EOF

issue uk-sc-integration "[proto] Implementar CRC16-CCITT-FALSE com vetor 0x29B1" protocol <<'EOF'
## Contexto

O ADR-0002 fixa poly `0x1021`, init `0xFFFF`, sem reflexao. O vetor de teste protege contra implementacao quase-correta.

## O que fazer

- [ ] `uk_crc16_ccitt_false()` em `src/proto/`
- [ ] Teste: `CRC("123456789") == 0x29B1`
- [ ] Teste: payload vazio e payload de 32 B
- [ ] Definir e documentar a ordem dos bytes (little-endian)

## Pronto quando

Teste passa e o vetor esta no codigo como constante nomeada.

## Referencias

- ADR-0002
EOF

issue uk-sc-integration "[proto] Implementar de-framing com stuffing, resync e timeout intra-frame" protocol <<'EOF'
## Contexto

Entrada serial e externa hostil. Um byte perdido nao pode travar o parser para sempre.

## O que fazer

- [ ] Maquina de estados `RX_WAIT_SOF` ate `RX_CRC_HI`
- [ ] Destuffing de `A5 00` para `A5`
- [ ] `LEN > UK_PROTO_MAX_PAYLOAD` descarta sem overflow
- [ ] Timeout intra-frame volta para `RX_WAIT_SOF`
- [ ] CRC errado descarta e continua (nao derruba o link)
- [ ] Contadores: crc_err, len_err, timeout_err

## Pronto quando

Testes de frame valido, truncado, corrompido, ruido antes do SOF e `A5` no payload passam.

## Referencias

- ADR-0002
- Skill `serial-link`
EOF

issue uk-sc-integration "[proto] Fuzzer do parser de frame" test <<'EOF'
## Contexto

O CI tem um job de fuzz que hoje sai com aviso porque `tests/fuzz_deframe.c` nao existe.

## O que fazer

- [ ] Fuzzer com `-fsanitize=fuzzer,address,undefined`
- [ ] Semente com frame valido
- [ ] Rodar 60 s no CI sem crash e sem escrita fora do buffer

## Pronto quando

Job `fuzz-parser` do CI executa de verdade e falha em regressao.

## Referencias

- `.github/workflows/ci.yml`
EOF

issue uk-sc-integration "[fw] board_pins.h com conflito de pino verificado em compilacao" firmware <<'EOF'
## Contexto

Pino magico espalhado pelo codigo e fonte classica de defeito intermitente.

## O que fazer

- [ ] Um unico `board_pins.h` com comentario do conector fisico
- [ ] `static_assert` para cada pino reservado (UART, SPI, I2C, status)
- [ ] Nenhum numero de pino no corpo do codigo

## Pronto quando

Build falha ao duplicar um pino, e a pinagem esta revisada contra o esquematico.

## Referencias

- `.github/instructions/arduino.instructions.md`
EOF

issue uk-sc-integration "[fw] Varredura 8x14 com tempo de acomodacao medido" firmware <<'EOF'
## Contexto

O tempo de acomodacao depende do pull-up e da capacitancia do cabo. Chutar o valor gera tecla fantasma.

## O que fazer

- [ ] Acionar uma coluna por vez, ler as 8 linhas
- [ ] `UK_MATRIX_SETTLE_US` medido no hardware real
- [ ] Bitmap de 112 bits (14 bytes)
- [ ] Varredura completa em ate 1 ms

## Pronto quando

Duracao da varredura medida e registrada; nenhuma tecla fantasma em teste de conjunto.

## Referencias

- Skill `input-matrix`
EOF

issue uk-sc-integration "[fw] Debounce por timestamp por tecla" firmware <<'EOF'
## Contexto

Debounce e por tecla e por tempo. Aplicar em dois lugares (firmware e daemon) dobra a latencia.

## O que fazer

- [ ] Estado por tecla: `raw`, `stable`, `last_change_ms`
- [ ] `UK_DEBOUNCE_MS` configuravel, nunca `delay()`
- [ ] Emitir evento apenas na transicao de estado estavel
- [ ] Documentar que o daemon nao repete o debounce

## Pronto quando

Teste com rajada de ruido produz uma unica transicao.

## Referencias

- Skill `input-matrix`
EOF

issue uk-sc-integration "[fw] Emitir KEY_EVENT, KEY_SNAPSHOT e heartbeat" firmware <<'EOF'
## Contexto

Transicoes em regime normal; snapshot para rajada e para reconexao; heartbeat para detectar perda.

## O que fazer

- [ ] `KEY_EVENT` com `count` + pares `{key_idx, flags}`, maximo 15 por frame
- [ ] `KEY_SNAPSHOT` de 14 bytes
- [ ] Heartbeat a cada 100 ms
- [ ] Snapshot na reconexao **antes** de qualquer evento real

## Pronto quando

O Pi reconstroi o estado correto apos reconexao, sem release fantasma.

## Referencias

- ADR-0002
EOF

issue uk-sc-integration "[fw] Buffer de TX com prioridade de release e contador de overflow" firmware <<'EOF'
## Contexto

Perder um `press` engole um acionamento; perder um `release` **prende a tecla**. O buffer nao pode bloquear o scan.

## O que fazer

- [ ] Buffer circular de 96 B (pior caso do frame com stuffing)
- [ ] Prioridade: release > press
- [ ] Buffer cheio descarta o `press` mais antigo e incrementa `tx_overflow`
- [ ] Nunca descarta release

## Pronto quando

Teste de buffer cheio preserva todos os releases.

## Referencias

- ADR-0002
EOF

issue uk-sc-integration "[fw] Tratar perda de link e enviar snapshot na reconexao" firmware <<'EOF'
## Contexto

Sem heartbeat, o firmware nao sabe que o Pi sumiu e continua acumulando estado inconsistente.

## O que fazer

- [ ] Timeout de 250 ms sem heartbeat: zerar estado e piscar status
- [ ] Ao reconectar, publicar estado "todas liberadas" antes de eventos reais
- [ ] Limpar `g_stable` na perda

## Pronto quando

Teste de bancada: desligar e religar o Pi nao gera tecla presa nem evento fantasma.

## Referencias

- ADR-0002
EOF

issue uk-sc-integration "[test] Testes host da matriz com GPIO fake" test <<'EOF'
## Contexto

Testar matriz exige hardware; a logica pode ser testada no host com I/O injetado.

## O que fazer

- [ ] Interface `gpio_read/write` atras de ponteiro
- [ ] Fake que simula coluna/linha pressionada
- [ ] Casos: tecla simples, rajada, 14 teclas, 112 teclas, reconexao

## Pronto quando

`ctest` cobre a matriz sem hardware.

## Referencias

- Skill `embedded-c`
EOF

# ---------------------------------------------------------------------------
# uk-pi0: daemon
# ---------------------------------------------------------------------------

echo "uk-pi0"

issue uk-pi0 "[scaffold] CMake, systemd unit e config de exemplo" scaffold <<'EOF'
## Contexto

O repo ainda so tem README e CI. Sem CMake, o job de build sai com aviso e nada e compilado.

## O que fazer

- [ ] `CMakeLists.txt` C++17 com warnings como erro
- [ ] `packaging/uk-pi0.service` com `Type=notify`, `Restart=always`, `WatchdogSec=`
- [ ] `config/uk-pi0.toml` de exemplo
- [ ] Teste de fumaca com `ctest`

## Pronto quando

Build e `ctest` passam no host.

## Referencias

- Skill `cpp-daemon`
EOF

issue uk-pi0 "[core] Laco epoll com signalfd e timeout derivado do heartbeat" core <<'EOF'
## Contexto

O laco principal precisa de timeout finito: `epoll_wait(-1)` cego impede o watchdog de funcionar.

## O que fazer

- [ ] `epoll` com timeout maximo nomeado
- [ ] `signalfd` em vez de handler de sinal (evita corrida entre threads)
- [ ] Watchdog notificado do laco
- [ ] Encerramento limpo com join e timeout

## Pronto quando

`SIGTERM` encerra em tempo limitado e o watchdog reinicia o servico quando o laco trava.

## Referencias

- Skill `cpp-daemon`
EOF

issue uk-pi0 "[link] Consumir uk-sc-integration e publicar eventos tipados" core <<'EOF'
## Contexto

O daemon nao pode redefinir o frame localmente: ele consome o contrato do `uk-sc-integration`.

## O que fazer

- [ ] Linkar a biblioteca portavel do contrato
- [ ] Abrir a serial com `O_NONBLOCK`
- [ ] Publicar eventos tipados para a camada de estado
- [ ] Contadores: crc_err, len_err, timeout, resync

## Pronto quando

Frames reais do Arduino reconstroem o bitmap de 112 bits corretamente.

## Referencias

- ADR-0002
- Skill `serial-link`
EOF

issue uk-pi0 "[safety] release_all_keys em SIGTERM, watchdog e perda de link" core <<'EOF'
## Contexto

Inverter a prioridade aqui significa deixar a maquina do usuario com um modificador preso. E o invariante numero 1 do projeto.

## O que fazer

- [ ] `release_all_keys()` que zera modificadores e keycodes
- [ ] Chamar em `SIGTERM`, `SIGINT`, perda de link e watchdog
- [ ] Confirmar escrita com timeout curto e logar falha
- [ ] Ordem: liberar teclas -> parar render -> fechar gadget

## Pronto quando

Teste automatizado verifica que o relatorio enviado no shutdown tem modificadores zerados.

## Referencias

- Context map, invariante 1
- Skill `hid-gadget`
EOF

issue uk-pi0 "[hid] Script idempotente de gadget em configfs" hid <<'EOF'
## Contexto

Recriar o gadget a cada boot sem depender de estado sujo de execucao anterior.

## O que fazer

- [ ] Script cria o gadget se ausente; se existente, apenas valida e religa o `UDC`
- [ ] `dwc2` em modo peripheral e `libcomposite` carregado
- [ ] Strings do dispositivo e `MaxPower` definidos
- [ ] Recuperacao quando o host desconecta sem reiniciar o daemon

## Pronto quando

Rodar o script duas vezes seguidas nao gera erro e o host enumera.

## Referencias

- `.github/instructions/hid-usb.instructions.md`
EOF

issue uk-pi0 "[hid] Interface boot keyboard 6KRO" hid <<'EOF'
## Contexto

BIOS, UEFI, KVM e instalador usam boot protocol: 8 bytes, 6 keycodes. Se isso falhar, nada mais importa.

## O que fazer

- [ ] Descritor de teclado boot
- [ ] Relatorio `modifiers + reserved + 6 keycodes`
- [ ] Escrita em `O_NONBLOCK` com retry e timeout
- [ ] Nao reenviar relatorio identico

## Pronto quando

Enumera e digita em BIOS/UEFI real.

## Referencias

- Skill `hid-gadget`
EOF

issue uk-pi0 "[hid] Interface NKRO com bitmap de 112 bits" hid <<'EOF'
## Contexto

NKRO coexiste com boot protocol; nunca o substitui. Host antigo pode nao entender bitmap.

## O que fazer

- [ ] Descritor de report com bitmap
- [ ] Manter os dois relatorios coerentes com o mesmo estado
- [ ] Detectar protocolo ativo por `SET_PROTOCOL`/`GET_PROTOCOL`
- [ ] Fallback automatico para 6KRO

## Pronto quando

Teste com mais de 6 teclas simultaneas passa, e host sem NKRO continua funcionando.

## Referencias

- Skill `hid-gadget`
EOF

issue uk-pi0 "[hid] Interface vendor-specific conforme ADR-0003" hid <<'EOF'
## Contexto

Canal de controle do `uk-gui`. Precisa validar toda mensagem e nunca bloquear a digitacao.

## O que fazer

- [ ] Parser de mensagem `MAGIC/VER/OPCODE/SEQ/LEN/PAYLOAD/CRC16`
- [ ] `TX_BEGIN`/`TX_DATA`/`TX_COMMIT`/`TX_ABORT` com `crc32` e expiracao de sessao
- [ ] `SET_HOST_LAYOUT` idempotente
- [ ] `GET_INFO` com versao e capabilities
- [ ] Processar fora da thread de scan

## Pronto quando

Transferencia abortada deixa o estado anterior intacto e o teste de idempotencia passa.

## Referencias

- ADR-0003
EOF

issue uk-pi0 "[render] Thread de render com fila dirty e coalescing" render <<'EOF'
## Contexto

Tela cheia custa ~730 ms. Atualizar tudo por evento de tecla e inaceitavel.

## O que fazer

- [ ] Bitset `dirty` de 112 bits como fonte de verdade
- [ ] Fila de capacidade fixa com coalescing e descarte da mais antiga
- [ ] Orcamento por ciclo (`UK_RENDER_BUDGET_BYTES`)
- [ ] Prioridade para a tecla em foco
- [ ] Nunca bloquear o produtor de eventos

## Pronto quando

Um evento de tecla nunca dispara atualizacao de tela cheia.

## Referencias

- `.github/instructions/displays.instructions.md`
- Skill `display-pipeline`
EOF

issue uk-pi0 "[render] Driver de display abstrato e fake para teste host" render <<'EOF'
## Contexto

O resto do sistema nao pode conhecer o barramento. Trocar o painel deve ser trocar uma struct.

## O que fazer

- [ ] `display_driver_t` com `init`, `write_region`, `flush`, `sleep`, `wake`, `get_caps`
- [ ] `write_region` recebe retangulo, ponteiro e `stride`
- [ ] Timeout em toda operacao
- [ ] Fake para teste host

## Pronto quando

Teste host compoe uma tecla e valida pixels de amostra sem hardware.

## Referencias

- Skill `display-pipeline`
EOF

issue uk-pi0 "[ops] Contadores de erro e GET_STATS no journald" core <<'EOF'
## Contexto

Contador que nao pode ser lido nao existe. Sem observabilidade, a bancada vira adivinhacao.

## O que fazer

- [ ] Contadores: frames descartados, profundidade da fila, duracao do render, vazao do barramento, reconexoes
- [ ] Expor por `GET_STATS` e por journald
- [ ] Sem alocacao ao incrementar

## Pronto quando

Uma sessao de estresse produz numeros que explicam o comportamento observado.

## Referencias

- Context map, secao de invariantes
EOF

# ---------------------------------------------------------------------------
# uk-gui: painel no host
# ---------------------------------------------------------------------------

echo "uk-gui"

issue uk-gui "[blocked] Scaffold do projeto apos ADR-0001" blocked <<'EOF'
## Contexto

Nao e possivel escolher estrutura de projeto, gerenciador de dependencias e build sem a stack definida.

**Bloqueado por:** `[ADR-0001] Decidir stack do uk-gui`.

## O que fazer

- [ ] Definir layout de diretorios conforme a stack escolhida
- [ ] Configurar build e testes
- [ ] Separar o nucleo de I/O (`uk-host`) da UI
- [ ] Atualizar o job de build do CI

## Pronto quando

CI do `uk-gui` compila e roda teste de verdade, sem o aviso de stack indefinida.

## Referencias

- ADR-0001
- `uk-gui/.github/workflows/ci.yml`
EOF

issue uk-gui "[detect] Deteccao de layout no Windows" panel <<'EOF'
## Contexto

Layout e por thread no Windows: trocar de janela pode trocar o layout. Avaliar so no arranque esta errado.

## O que fazer

- [ ] `GetForegroundWindow` -> `GetWindowThreadProcessId` -> `GetKeyboardLayout`
- [ ] Reavaliar em `WM_INPUTLANGCHANGE` e em mudanca de foco
- [ ] Mapear `HKL` para `uk_layout_id_t` (ABNT2 `0x0416`, US `0x0409`)
- [ ] Tratar layout desconhecido sem quebrar

## Pronto quando

Trocar de janela com layouts diferentes atualiza o layout detectado em menos de 50 ms.

## Referencias

- Skill `layout-adaptation`
- `.github/instructions/host-panel.instructions.md`
EOF

issue uk-gui "[detect] Deteccao de layout no X11" panel <<'EOF'
## Contexto

No X11 o grupo de teclado tambem muda por janela.

## O que fazer

- [ ] `xkbcommon` / `XkbGetState` para obter o grupo ativo
- [ ] Converter keysym para o identificador do projeto
- [ ] Reavaliar no evento de grupo

## Pronto quando

Dois terminais com layouts diferentes reportam valores distintos ao trocar o foco.

## Referencias

- Skill `layout-adaptation`
EOF

issue uk-gui "[detect] Deteccao de layout no macOS" panel <<'EOF'
## Contexto

O macOS expoe o input source atual, com identificador estavel por layout.

## O que fazer

- [ ] `TISCopyCurrentKeyboardInputSource` + `kTISPropertyInputSourceID`
- [ ] Observar `kTISNotifySelectedKeyboardInputSourceChanged`
- [ ] Mapear `com.apple.keylayout.*` para `uk_layout_id_t`

## Pronto quando

Alternar o input source no menu do macOS reflete no teclado sem reiniciar o painel.

## Referencias

- Skill `layout-adaptation`
EOF

issue uk-gui "[detect] Wayland: limitacao documentada e integracao por compositor" panel <<'EOF'
## Contexto

Wayland nao expoe layout global por design. Fingir que existe e pior que declarar a limitacao.

## O que fazer

- [ ] GNOME: `gsettings get org.gnome.desktop.input-sources`
- [ ] KDE: D-Bus `org.kde.keyboard`
- [ ] Documentar a limitacao na UI e oferecer selecao manual
- [ ] Detectar o compositor antes de tentar

## Pronto quando

A UI informa honestamente o modo de deteccao e o usuario pode fixar o layout manualmente.

## Referencias

- Skill `layout-adaptation`
- Context map, secao 7
EOF

issue uk-gui "[fingerprint] Identidade de maquina por SO" panel <<'EOF'
## Contexto

O perfil e salvo por maquina. Fingerprint identifica a maquina, **nao** o layout.

## O que fazer

- [ ] Windows: `MachineGuid` + versao
- [ ] Linux: `/etc/machine-id` + `ID` de `/etc/os-release`
- [ ] macOS: `IOPlatformUUID`
- [ ] Hash local; nunca enviar para a rede
- [ ] Sem correspondencia: usar layout padrao e sinalizar que e palpite

## Pronto quando

Dois perfis distintos coexistem para duas maquinas e nao vazam entre si.

## Referencias

- `.github/instructions/host-panel.instructions.md`
EOF

issue uk-gui "[hid] Cliente vendor com SET_HOST_LAYOUT idempotente" panel <<'EOF'
## Contexto

Unico caminho do painel para o teclado. Precisa reenviar ao reconectar sem causar redesenho.

## O que fazer

- [ ] Cliente do protocolo do ADR-0003
- [ ] `GET_INFO` antes de usar opcode opcional
- [ ] Fatiamento com `seq`/`offset` e `COMMIT` transacional
- [ ] Reenvio automatico na reconexao
- [ ] `SET_HOST_LAYOUT` idempotente

## Pronto quando

Reenviar o mesmo layout nao gera trafego de render no teclado.

## Referencias

- ADR-0003
EOF

issue uk-gui "[ui] Editor de macros e preview das 120 teclas" panel <<'EOF'
## Contexto

O painel precisa mostrar o resultado real: keycode, nao apenas caractere. A tabela de mapeamento nao pode ser duplicada.

## O que fazer

- [ ] Editor de macro exibindo os keycodes resultantes
- [ ] Preview das 112 teclas com o mesmo `key_idx` e `usage_id` do teclado
- [ ] Reaproveitar a tabela `usage -> legenda` do layout detectado
- [ ] Avisar quando o layout detectado nao for suportado

## Pronto quando

O que aparece no preview e identico ao que aparece na tecla fisica para o mesmo layout.

## Referencias

- Skill `key-rendering`
- Skill `layout-adaptation`
EOF

# ---------------------------------------------------------------------------

echo
echo "Criados: $CREATED   ja existentes: $SKIPPED"
if [ "$DRY_RUN" = 1 ]; then
    echo "(modo dry-run: nada foi enviado ao GitHub)"
fi

# ---------------------------------------------------------------------------
# Hardware: decisoes e execucao abertas pelo redesenho 6x23
# ---------------------------------------------------------------------------

echo "Hardware (UniversalKeyboard)"

issue UniversalKeyboard "[ADR-0002] Revisar taxa do link: 57600 (3V3) vs 921600 (5V)" adr <<'EOF'
## Contexto

O ADR-0002 propõe **921600 baud**, que exige ATmega a 16 MHz / 5 V.

O hardware foi definido em **rail único de 3,3 V**, porque o Pi Zero 2W não tolera 5 V em
GPIO. Isso limita o clock a 8 MHz e a taxa viável a **57600 baud** (erro de 2,1 %).

Com 8 MHz:

| Baud | UBRR | Erro | Veredito |
|---|---:|---:|---|
| 921600 | 0,08 | — | **impossível** |
| 115200 | 7,68 | 3,5 % | marginal |
| 57600 | 16,36 | 2,1 % | recomendado |

**Bloqueia firmware e daemon** — os dois lados precisam concordar.

## O que fazer

- [ ] Decidir: 57600 em 3,3 V, ou 5 V/16 MHz com level shifter no UART
- [ ] Se 5 V: reavaliar o risco de 5 V chegar em GPIO do Pi (o shifter pode ser montado errado)
- [ ] Atualizar o ADR-0002 com a taxa final e o `VER` do frame
- [ ] Mudar o status para `Aceito`

## Pronto quando

Taxa fechada, ADR `Aceito`, e `UK_BAUD` definido nos dois lados.

## Referencias

- `docs/adr/0002-frame-do-link-serial.md` (campo "Revisão pendente")
- `docs/hardware/matriz-e-link.md` §3
EOF

issue UniversalKeyboard "[hw] Rotear as duas PCBs no Pcbnew" bench <<'EOF'
## Contexto

As placas existem, abrem no KiCad e passam DRC **sem curtos**, mas estão **sem roteamento**:
362 conexões não-roteadas na matriz e 109 na placa de controle.

## O que fazer

- [ ] Roteamento da matriz (prioridade: linhas de COL/ROW folgadas, sobra área)
- [ ] Plano de GND nas duas faces com via stitching
- [ ] Roteamento da placa de controle com atenção a `3V3`/`GND`
- [ ] Revisar o texto não espelhado no lado B (199 avisos cosméticos)
- [ ] Rodar DRC até zero erros de geometria

## Pronto quando

DRC com 0 curtos e 0 não-roteadas nas duas placas.

## Referencias

- `docs/hardware/matriz-e-link.md` §6 e §8
- `tools/gen_kicad_pcb.py`
EOF

issue UniversalKeyboard "[hw] Prototipo de 1 coluna (6 teclas) antes das 120" bench <<'EOF'
## Contexto

Validar 120 teclas de uma vez é caro em tempo e em dinheiro. Uma coluna exercita toda a
cadeia: shift register, diodo, debounce, frame serial e integração com o Pi.

## O que fazer

- [ ] Montar 6 switches + 6 diodos + 1× 74HC595 + 1× 74HC165
- [ ] Medir `UK_MATRIX_SETTLE_US` no cabo real
- [ ] Medir corrente por coluna com 6 teclas pressionadas
- [ ] Validar frame serial com o Pi
- [ ] Confirmar o passo de 19,05 mm com o keycap e a tela montados

## Pronto quando

Uma coluna funciona ponta a ponta e os números estão registrados.

## Referencias

- `docs/hardware/matriz-e-link.md` §9
EOF

issue UniversalKeyboard "[hw] Escolher display e medir o consumo real" bench <<'EOF'
## Contexto

O orçamento de energia é o maior risco do projeto. 120 displays de 1,3" com backlight
consomem **~2,4 A** — acima de qualquer porta USB.

| Carga | Corrente |
|---|---:|
| Pi Zero 2W | 120–250 mA |
| ATmega + 4 CIs | ~9 mA |
| 120 displays (~20 mA cada) | ~2 400 mA |

## O que fazer

- [ ] Levantar candidatos: TFT SPI com/sem backlight, e-paper, memory-in-pixel
- [ ] Medir corrente real de um display aceso e apagado
- [ ] Decidir a fonte externa (≥ 3 A) e o método de não retroalimentar o VBUS do host
- [ ] Registrar em ADR

## Por que importa

e-paper gasta quase nada em imagem estática, o que combina com keycap que muda pouco.
A escolha muda o produto, não só a BOM.

## Pronto quando

ADR `Aceito` com part number, consumo medido e arquitetura de energia definida.

## Referencias

- `docs/hardware/matriz-e-link.md` §7
EOF

issue UniversalKeyboard "[hw] Adicionar TVS e capacitor de reset ao netlist" bench <<'EOF'
## Contexto

As linhas da matriz ficam expostas ao usuário. Não há proteção ESD nem filtro no reset.

## O que fazer

- [ ] TVS nas linhas de coluna e linha que chegam aos conectores
- [ ] 100 nF de RESET para GND
- [ ] Verificar se o conector J3/J4 precisa de proteção adicional
- [ ] Regerar netlist, esquema e PCBs

## Pronto quando

Proteção no netlist, ERC limpo e BOM atualizada.

## Referencias

- `docs/hardware/matriz-e-link.md` §7
EOF

issue UniversalKeyboard "[hw] Definir a tela unica opcional abaixo das teclas" bench <<'EOF'
## Contexto

Requisito declarado: possivelmente uma **tela única** abaixo das teclas, no estilo
Stream Deck, além (ou no lugar) das telas por keycap.

## O que fazer

- [ ] Definir se é adicional ou substitui as 120 telas — muda o orçamento inteiro
- [ ] Escolher tamanho, resolução e barramento
- [ ] Verificar o orçamento de banda junto com os displays por tecla
- [ ] Reservar área na PCB e no gabarito

## Pronto quando

Decisão registrada e a área reservada na placa.

## Referencias

- `docs/hardware/matriz-e-link.md` §7
- ADR de display
EOF

issue uk-pi0 "[link] Configurar baud conforme ADR-0002 revisado" core <<'EOF'
## Contexto

Depende da taxa final decidida no issue de revisão do ADR-0002.

O daemon precisa abrir a serial na taxa fechada e **rejeitar** configuração incompatível em
vez de falhar silenciosamente.

## O que fazer

- [ ] `UK_BAUD` como constante nomeada, não literal
- [ ] Falha de `termios` tratada e logada
- [ ] Timeout de leitura derivado do frame máximo na taxa escolhida
- [ ] Teste host com pty fake

## Pronto quando

Daemon e firmware conversam na taxa acordada, com teste automatizado.

## Referencias

- `docs/adr/0002-frame-do-link-serial.md`
EOF

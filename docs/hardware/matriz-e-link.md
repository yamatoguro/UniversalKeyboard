# Esboço — matriz de 112 teclas e link com o Pi Zero 2W

> **Status:** esboço para revisão. **Não** foi simulado nem montado em bancada. O esquema
> KiCad **abre, plota e passa ERC** (0 erros elétricos), mas não foi roteado nem conferido
> por um humano. Trate como ponto de partida, não como projeto validado.
>
> Artefatos, todos **gerados** — não edite à mão:
>
> | Artefato | Gerado por | O que é |
> |---|---|---|
> | [`universal-keyboard.kicad_sch`](universal-keyboard.kicad_sch) | [`tools/gen_kicad_sch.py`](../../tools/gen_kicad_sch.py) | **esquema KiCad** com 249 símbolos |
> | [`svg/universal-keyboard.svg`](svg/universal-keyboard.svg) | `kicad-cli` | plot do esquema (A0) |
> | [`matrix-link.net`](matrix-link.net) | [`tools/gen_hw_netlist.py`](../../tools/gen_hw_netlist.py) | netlist |
> | [`bom.csv`](bom.csv) | idem | lista de materiais (249 itens) |
> | [`matrix-link-*.dot`/`.svg`](matrix-link-block.dot) | [`tools/netlist_to_dot.py`](../../tools/netlist_to_dot.py) | diagramas de visão geral |
>
> Como abrir, editar e validar: §10.

## 1. A decisão que governa o desenho: quantos GPIO

A malha 8×14 usa **8 linhas + 14 colunas = 22 pinos**, não 112. Somando UART e LED de
status, são **25 GPIO**.

| Alvo | GPIO livres | Fiação direta | Observação |
|---|---|---|---|
| ATmega328P DIP-28 **com cristal** | 21 | ✗ faltam 4 | PB6/PB7 viram cristal |
| ATmega328P DIP-28, RC interno | 23 | ✗ faltam 2 | baud impreciso |
| Arduino Uno (header) | 20 | ✗ faltam 5 | PB6/PB7 no header, sem cristal |
| ATmega32U4 TQFP-44 | 26 | ✓ sobra 1 | USB nativo, exige PCB |
| Arduino Leonardo (header) | 20 | ✗ faltam 5 | |
| ATmega2560 (Mega) | 54 | ✓ sobra 29 | placa grande |
| **Raspberry Pi Zero 2W** | **26** | **✓ sobra 1** | GPIO0/1 = ID EEPROM |

### Consequência

Um Uno **não** cabe com fiação direta. Três caminhos:

| Opção | Como | Custo | Determinismo | Comentário |
|---|---|---|---|---|
| **A. Shift registers** (recomendada) | 74HC595 ×2 + 74HC165 → **5 GPIO** | ~R$ 8 | ✓ tempo real | cabe em qualquer AVR, sobra 16 pinos |
| **B. Pi Zero 2W direto** | 22 pinos da matriz + UART | ~R$ 250 | ✗ Linux | caberia, mas veja §6 |
| **C. ATmega2560** | fiação direta | ~R$ 60 | ✓ tempo real | 54 GPIO, sobra 29 |

**Recomendação: Opção A.** Ela resolve o problema de pinos sem trocar o MCU, mantém a
varredura determinística (invariante 6 do projeto) e custa menos que qualquer alternativa.
Trocar o Arduino por outra Pi resolve o pinos, mas troca determinismo por jitter de Linux e
multiplica o consumo (§6) — não é necessário.

---

## 2. Arquitetura elétrica

```text
                        +3V3 rail unico
                              │
   ┌──────────────────────────┴──────────────────────────┐
   │                                                     │
   │   ┌──────────────┐         SPI-like            ┌────┴─────┐
   │   │ ATmega328P   │  DS/CLK/LATCH/LOAD/DATA      │ 74HC595  │
   │   │  8 MHz       │─────────────────────────────►│  U2      │
   │   │  3V3         │                              └────┬─────┘
   │   │              │                              QH'  │
   │   │              │                              ┌────▼─────┐
   │   │              │                              │ 74HC595  │
   │   │              │                              │  U3      │
   │   │              │◄──── Q7 ─────────────────────┤          │
   │   │              │                              └──────────┘
   │   │              │                                   │ COL0..13
   │   │              │                                   ▼
   │   │              │                          ┌──────────────────┐
   │   │              │◄── Q7 ──┐                │  matriz 8 x 14   │
   │   │              │         │                │  112 x (SW+D)    │
   │   │              │   ┌─────┴────┐           └────────┬─────────┘
   │   │              │   │ 74HC165  │◄───── ROW0..7 ─────┘
   │   │              │   │  U4      │        (pull-down 10k)
   │   └──────┬───────┘   └──────────┘
   │          │ UART 3V3 direto
   │   ┌──────▼───────┐
   │   │ J1 → Pi Zero │  USB gadget → host
   │   └──────────────┘
   └──────────────────────────────────────────────────────
```

### Por que rail único de 3,3 V

O Pi Zero 2W tem GPIO **3,3 V e não tolera 5 V**. Um AVR em 5 V exigiria level shifter no
UART, e um erro de montagem levaria 5 V a um pino do Pi. Com tudo em 3,3 V:

- **não existe** level shifter para errar;
- o risco de queimar o Pi desaparece por construção;
- o ATmega328P roda a 8 MHz (o datasheet permite até 10 MHz em 3,3 V — 16 MHz exige ≥4,5 V);
- 74HC595 e 74HC165 operam de 2 V a 6 V, então funcionam em 3,3 V.

**Custo:** com 8 MHz o baud máximo confiável cai. Ver §5.

---

## 3. Matriz 8 × 14

### Conexão de uma tecla

```text
COL{c} ──────┐
             │
          ┌──┴──┐
          │ SW  │  acionador físico
          └──┬──┘
             │
            ─┴─  ►│  D  (BAT54: anodo no switch, catodo na linha)
            ─┬─
             │
ROW{r} ──────┴──────┬──── 74HC165 D{r}
                    │
                  ┌─┴─┐
                  │10k│  pull-down
                  └─┬─┘
                   GND
```

- Coluna é **saída** (driven high pelo 595); linha é **entrada** com pull-down.
- O diodo impede ghosting: sem ele, três teclas pressionadas criam um caminho falso.
- **BAT54** (Schottky, queda ~0,3 V) em vez de 1N4148 (~0,7 V): em 3,3 V a linha sobe para
  3,0 V contra 2,6 V. Ambos passam no VIH do 74HC165 (0,7 × 3,3 = 2,31 V), mas o BAT54 dá
  margem de 0,69 V contra 0,29 V — relevante com ruído de cabo longo.

### Índice da tecla

`key_idx = coluna * 8 + linha`, então `COL0` contém as teclas 0–7, `COL1` as teclas 8–15, e
assim por diante. Isso faz o byte lido do 165 para uma coluna ser exatamente o bitmap das
8 linhas daquela coluna.

### Varredura

```text
para cada coluna c em 0..13:
    deslocar 16 bits para os 595, com apenas o bit c em 1
    pulsar STCP (latch)           -> coluna c em nivel alto
    aguardar UK_MATRIX_SETTLE_US  -> medir na placa, nao chutar
    pulsar SH/LD (load) no 165    -> captura as 8 linhas
    deslocar 8 bits do Q7         -> bitmap da coluna c
```

Custo por varredura: 14 × (16 + 8) = 336 bits de shift. A 8 MHz isso é dezenas de
microssegundos — folga confortável dentro do orçamento de 1 ms.

---

## 4. Pinagem do ATmega328P (DIP-28)

| Pino | Porta | Função | Net |
|---:|---|---|---|
| 1 | PC6 | RESET | `RESET` |
| 2 | PD0 | RXD | `PI_TX` |
| 3 | PD1 | TXD | `PI_RX` |
| 4 | PD2 | saída | `SR_DS` |
| 5 | PD3 | saída | `SR_CLK` |
| 6 | PD4 | saída | `SR_LATCH` |
| 7 | VCC | — | `3V3` |
| 8 | GND | — | `GND` |
| 9 | PB6 | XTAL1 | `XTAL1` |
| 10 | PB7 | XTAL2 | `XTAL2` |
| 11 | PD5 | saída | `SR_LOAD` |
| 12 | PD6 | entrada | `SR_DATA_IN` |
| 13 | PD7 | livre | — |
| 14 | PB0 | saída | `STATUS_LED` |
| 15–18 | PB1–PB4 | livres | — |
| 19 | PB5 | livre (LED da placa) | — |
| 20 | AVCC | — | `3V3` |
| 21 | AREF | — | `3V3` |
| 22 | GND | — | `GND` |
| 23–28 | PC0–PC5 | livres (ADC/I2C) | — |

Sobram **13 GPIO** para o barramento das telas, botão de reset extra, sensor etc.

---

## 5. Link Pi ↔ Arduino

```text
   Pi Zero 2W                          ATmega328P
   ┌──────────┐                        ┌──────────┐
   │ GPIO14 TX├───────────────────────►│ PD0 RXD  │
   │ GPIO15 RX│◄───────────────────────┤ PD1 TXD  │
   │ GND      ├────────────────────────┤ GND      │
   │ 3V3      ├────────────────────────┤ VCC      │
   └──────────┘                        └──────────┘
        │                                    │
        └──────── J1 (1x06) ─────────────────┘
```

- **Sem level shifter**: os dois lados são 3,3 V.
- No Pi, use o **PL011** em GPIO14/15 (`enable_uart=1`, `dtoverlay=disable-bt`) para não
  herdar o miniUART, cujo baud depende do clock da GPU.
- GND comum obrigatório. Sem ele, o UART funciona mal ou não funciona.

### Consequência para o ADR-0002

O ADR-0002 propõe **921600 baud**, que exige 16 MHz @ 5 V. Com 8 MHz @ 3,3 V:

| Baud | UBRR (U2X) | Erro | Veredito |
|---|---:|---:|---|
| 921600 | 0,08 | — | **impossível** |
| 230400 | 3,34 | 8,5 % | inaceitável |
| 115200 | 8,68 | 3,5 % | marginal |
| **57600** | **17,36** | **2,1 %** | **recomendado** |

O volume real do projeto é transições de tecla (dezenas por segundo) e frames de 75 B no
pior caso. **57600 baud é mais que suficiente** — a escolha de 921600 no ADR era margem, não
necessidade.

**Ação:** o ADR-0002 precisa ser revisado para 57600 (3,3 V) **ou** para 5 V/16 MHz com level
shifter. Não deixe as duas coisas inconsistentes.

---

## 6. Orçamento de energia — o problema maior

Isto não é detalhe do esquema: define se o projeto é viável.

| Carga | Corrente típica | Observação |
|---|---:|---|
| Pi Zero 2W (sem WiFi) | 120–250 mA | picos de 700 mA com WiFi |
| ATmega328P 8 MHz @3V3 | ~6 mA | |
| 74HC595 ×2 + 74HC165 | ~3 mA | |
| **112 displays 1,3" com backlight** | **~2,2 A** | ~20 mA cada |
| **Total estimado** | **~2,5 A @ 5 V (12,5 W)** | |

Porta USB 2.0 fornece **500 mA**; USB 3.0, **900 mA**. Só o backlight das telas consome
~2,2 A.

### Consequências obrigatórias

1. **O teclado não pode ser alimentado pelo barramento USB do host.** Fonte externa de 5 V
   com ≥ 3 A.
2. Ao usar fonte externa, **não** retroalimente o VBUS do host: use diodo ideal, ou corte o
   VBUS do cabo, ou um carregador com dados. Retroalimentar VBUS queima o host.
3. Considere displays **sem backlight** (e-paper ou memory-in-pixel) se quiser viabilidade
   de consumo — e-paper tem consumo quase zero em imagem estática, o que combina com um
   teclado que muda pouco.
4. Backlight PWM por coluna reduz consumo, mas cria flicker perceptível. Medir antes.

Isso reforça que a **ADR de display é a decisão mais crítica do projeto** — mais que a de
MCU.

---

## 7. Proteção e robustez

| Item | Providência |
|---|---|
| ESD nas teclas | diodo série já limita; adicionar TVS nas linhas expostas ao usuário |
| Coluna em curto | 595 tolera ~35 mA por pino; corrente real por coluna ≈ 2,4 mA com 8 teclas |
| Ruído no cabo do link | par trançado TX/RX + GND, ou cabo blindado se > 30 cm |
| Brownout no boot | 1000 µF na rail 5 V das telas; 10 µF junto ao AVR |
| Reset acidental | pull-up 10 kΩ + 100 nF para GND (não incluído no netlist: adicionar) |
| Hot-plug do link | AVR detecta heartbeat ausente (§ ADR-0002) e libera teclas |

---

## 8. Lista de conexões (resumo)

| Net | Origem | Destino |
|---|---|---|
| `SR_DS` | U1 pino 4 | U2 pino 14 |
| `SR_CLK` | U1 pino 5 | U2/U3 pino 11, U4 pino 2 |
| `SR_LATCH` | U1 pino 6 | U2/U3 pino 12 |
| `SR_LOAD` | U1 pino 11 | U4 pino 1 |
| `SR_DATA_IN` | U1 pino 12 | U4 pino 9 |
| `SR_CASCADE` | U2 pino 9 | U3 pino 14 |
| `COL0..7` | U2 Q0..Q7 | teclas |
| `COL8..13` | U3 Q0..Q5 | teclas |
| `ROW0..7` | U4 D0..D7 | teclas + RN1 pull-down |
| `PI_TX` / `PI_RX` | J1 pino 3/4 | U1 pino 2/3 |
| `3V3` / `GND` | J1 | todas as alimentações |

Mapa completo e verificável: [`matrix-link.net`](matrix-link.net).

---

## 9. O que falta para virar projeto de verdade

- [ ] Confirmar a decisão de MCU (ADR pendente, issue no `UniversalKeyboard`)
- [ ] Medir `UK_MATRIX_SETTLE_US` em bancada com o cabo real
- [ ] Escolher o acionador (switch) e confirmar força/curso
- [ ] Definir o display — **bloqueia o orçamento de energia**
- [ ] Adicionar TVS e o capacitor de reset ao netlist
- [ ] Abrir no KiCad e rotear; validar ERC
- [ ] Protótipo de 1 coluna (8 teclas) antes das 112
- [ ] Medir corrente real e comparar com a tabela de §6

Nenhum destes itens foi verificado. O documento descreve um desenho coerente, não um
desenho testado.

---

## 10. Como visualizar e validar

### Opção 1 — KiCad (completo)

```bash
sudo pacman -S kicad kicad-library
kicad docs/hardware/universal-keyboard.kicad_sch
```

Dentro do KiCad: **Inspecionar → Regras de projeto (ERC)**. Resultado atual: **0 erros
elétricos**, 2 avisos cosméticos (`lib_symbol_mismatch` em U1 e U4, porque esses símbolos
`extends` outro na biblioteca).

Validação por CLI, sem abrir a interface:

```bash
kicad-cli sch erc  docs/hardware/universal-keyboard.kicad_sch -o erc.rpt
kicad-cli sch export svg docs/hardware/universal-keyboard.kicad_sch -o docs/hardware/svg
```

### Opção 2 — VS Code

| Extensão | ID | Para quê |
|---|---|---|
| KiCad Studio Kit | `oaslananka.kicadstudiokit` | visualizar `.kicad_sch`, rodar DRC/ERC |
| Graphviz Interactive Preview | `tintinweb.graphviz-interactive-preview` | visualizar os `.dot` com preview ao vivo |
| Mermaid | `bierner.markdown-mermaid` | renderiza diagramas Mermaid no preview do Markdown |
| Draw.io | `hediet.vscode-drawio` | desenhar à mão quando quiser anotar |

Instalação:

```bash
code --install-extension oaslananka.kicadstudiokit
code --install-extension tintinweb.graphviz-interactive-preview
code --install-extension bierner.markdown-mermaid
code --install-extension hediet.vscode-drawio
```

> **Limite honesto:** nenhuma extensão desenha um esquema a partir do `.net`. O `.net` é
> netlist — lista de conexões, não desenho. Para ver um esquema é preciso o `.kicad_sch`
> (que existe) ou o KiCad.

### Regenerar depois de mudar o hardware

```bash
python3 tools/gen_hw_netlist.py     # netlist + BOM
python3 tools/gen_kicad_sch.py      # esquema + plot + ERC
python3 tools/netlist_to_dot.py --mode block  --render
python3 tools/netlist_to_dot.py --mode matrix --render
```

Como os três scripts são determinísticos, o diff mostra exatamente o que mudou no hardware.

⚠️ Se você editar o `.kicad_sch` dentro do KiCad, a próxima execução do gerador
**sobrescreve** suas alterações. Nesse caso, mova a fonte da verdade para o esquema e pare
de gerá-lo — ou registre a mudança em `gen_hw_netlist.py` primeiro.

---

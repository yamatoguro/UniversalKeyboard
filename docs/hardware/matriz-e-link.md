# Hardware — matriz 6×23, link com o Pi e placas

> **Status:** esboço geométrico e elétrico. O esquema **passa ERC** (0 erros) e as duas
> placas **abrem, plotam e rendem em 3D**, mas **nada foi roteado, simulado ou montado**.
>
> Tudo é **gerado** por script; não edite os artefatos à mão.

| Artefato | Gerado por | O que é |
|---|---|---|
| [`universal-keyboard.kicad_sch`](universal-keyboard.kicad_sch) | [`tools/gen_kicad_sch.py`](../../tools/gen_kicad_sch.py) | esquema, 267 símbolos |
| [`main-board.kicad_pcb`](main-board.kicad_pcb) | [`tools/gen_kicad_pcb.py`](../../tools/gen_kicad_pcb.py) | placa da matriz, 492,2 × 153,8 mm |
| [`control-board.kicad_pcb`](control-board.kicad_pcb) | idem | placa de controle, 120 × 90 mm |
| [`pcb/*.step`](pcb/) | `kicad-cli` | modelo 3D sólido |
| [`pcb/*-3d-top.png`](pcb/), `*-3d-bottom.png` | `kicad-cli` | render 3D |
| [`matrix-link.net`](matrix-link.net), [`bom.csv`](bom.csv) | [`tools/gen_hw_netlist.py`](../../tools/gen_hw_netlist.py) | netlist e BOM (267 itens) |
| [`matrix-link-*.dot`](matrix-link-block.dot) | [`tools/netlist_to_dot.py`](../../tools/netlist_to_dot.py) | diagramas de visão geral |

---

## 1. Geometria confirmada

Requisitos definidos pelo autor do projeto:

- matriz **6 linhas × 23 colunas** (138 posições)
- **120 teclas**: 104 do padrão full-size + 12 macro + 4 de mídia
- distribuição no estilo **Keychron V6**, base declarada do projeto
- coluna macro de **1u em cada lado**, alinhada às 6 linhas
- teclas largas reservam a largura real (Backspace 2u, Space 6,25u, Enter 2,25u…)
- 1u = **19,05 mm**

| Linha | Teclas | Conteúdo |
|---|---:|---|
| 0 | 22 | M1 · Esc F1–F12 · PrtSc ScrLk Pause · Mute Vol− Vol+ Play · M7 |
| 1 | 23 | M2 · ` 1–0 − = Backspace · Ins Home PgUp · NumLock / * − · M8 |
| 2 | 23 | M3 · Tab QWERTY [ ] \ · Del End PgDn · 7 8 9 + · M9 |
| 3 | 18 | M4 · Caps ASDF… · 4 5 6 · M10 |
| 4 | 19 | M5 · LShift ZXCV… RShift · Up · 1 2 3 Enter · M11 |
| 5 | 15 | M6 · Ctrl Win Alt Space Alt Win Menu Ctrl · ← ↓ → · 0 . · M12 |

**18 posições da matriz ficam livres** (linhas 3, 4 e 5 usam menos de 23 colunas).

Placa: **492,2 × 153,8 mm**, com 4 furos M3 e faixa inferior para o conector J3.

---

## 2. Por que shift registers

A malha 6×23 usa **6 + 23 = 29 pinos** — acima dos 21 úteis do ATmega328P com cristal.

| Solução | GPIO |
|---|---:|
| Direto no MCU | 29 ✗ |
| **3× 74HC595 (colunas) + 1× 74HC165 (linhas)** | **5** ✓ |

- 3× 595 = 24 saídas ≥ 23 colunas.
- 1× 165 = 8 entradas ≥ 6 linhas.
- Sobram **13 GPIO** no ATmega para o barramento de display, status e I²C.

```text
U1 PD2 → SR_DS ─┬─ U2 SER ─→ QA..QH = COL0..7
                └─ U2 QH' → U3 SER ─→ QA..QH = COL8..15
                             U3 QH' → U4 SER ─→ QA..QG = COL16..22
U1 PD3 → SR_CLK    (595 SRCLK + 165 CP, compartilhado)
U1 PD4 → SR_LATCH  (595 RCLK)
U1 PD5 → SR_LOAD   (165 SH/LD)
U1 PD6 ← SR_DATA_IN (165 Q7)
```

---

## 3. Rail único de 3,3 V

O Pi Zero 2W **não tolera 5 V** em GPIO. Em vez de level shifter (que pode ser montado
errado e queimar o Pi), MCU, shift registers e Pi compartilham 3,3 V.

| Consequência | Valor |
|---|---|
| Clock máximo do ATmega em 3,3 V | 8 MHz (16 MHz exige ≥ 4,5 V) |
| Baud viável a 8 MHz | **57600** (2,1 % de erro) |
| Baud que o ADR-0002 propunha | 921600 — **impossível** a 8 MHz |

> **Ação pendente:** o ADR-0002 precisa ser revisto para 57600 baud (3,3 V) **ou** para
> 5 V/16 MHz com level shifter. Hoje o documento e o hardware estão inconsistentes.

---

## 4. Matriz elétrica

```text
COL{c} ──► SW{k} ──► ânodo D{k} (cátodo) ──► ROW{r} ──► 74HC165 D{r}
                                                    └──► pull-down 10k ──► GND
```

- Coluna é **saída** acionada em nível alto pelo 595; linha é **entrada** no 165.
- Um **diodo por tecla** elimina ghosting.
- **BAT54 em SOD-123, montado no lado B (embaixo da tecla)** — como em teclados
  comerciais. Diodo THT compartilharia os furos do switch e curto-circuitaria as redes;
  o SMD resolve isso por construção.
- `key_idx` da matriz: `coluna × 6 + linha`, com atribuição sequencial na ordem física.

---

## 5. Duas placas

A separação foi decisão do projeto: a eletrônica de controle não fica sob as teclas.

| Placa | Conteúdo | Dimensões |
|---|---|---|
| **matriz** | 120 switches MX + 120 diodos + J3 + 4 furos M3 + área reservada por tecla | 492,2 × 153,8 mm |
| **controle** | ATmega328P, 3× 595, 1× 165, cristal 8 MHz, passivos, J1 (Pi), J2 (ICSP), J4 | 120 × 90 mm |

Interligação: **2×17 (34 vias)** carregando `COL0..22`, `ROW0..5`, 3V3 e 4× GND.

---

## 6. Validação executada

| Verificação | Comando | Resultado |
|---|---|---|
| Esquema abre e plota | `kicad-cli sch export svg` | ✓ |
| **ERC do esquema** | `kicad-cli sch erc` | **0 erros** · 6 avisos `multiple_net_names`, 2 `lib_symbol_mismatch` |
| PCB matriz abre e plota | `kicad-cli pcb export svg` | ✓ |
| PCB controle abre e plota | idem | ✓ |
| STEP 3D | `kicad-cli pcb export step` | ✓ (ver §8) |
| Render 3D top/bottom | `kicad-cli pcb render` | ✓ |
| DRC matriz | `kicad-cli pcb drc` | 0 curtos · 362 não-roteadas · 199 texto não espelhado (cosmético) |
| DRC controle | idem | 0 curtos · 109 não-roteadas |

### Bug real encontrado pelo ERC

A primeira versão ligava `GND` nos pinos **3 e 4** do 74HC165 — que são `D4` e `D5`, ou
seja, **ROW4 e ROW5**. Isso curto-circuitaria duas linhas da matriz e produziria teclas
fantasma. Corrigido: `GND` só em `CE`, `SER`, `D6` e `D7`.

Sem ERC, esse defeito teria ido para a bancada.

---

## 7. Orçamento de energia — o risco maior

| Carga | Corrente |
|---|---:|
| Pi Zero 2W (sem WiFi) | 120–250 mA |
| ATmega + 4 CIs lógicos | ~9 mA |
| **120 displays 1,3" com backlight (~20 mA cada)** | **~2 400 mA** |
| **Total** | **~2,5–2,7 A @ 5 V (13 W)** |

USB 2.0 fornece 500 mA; USB 3.0, 900 mA. **Só o backlight consome 2,4 A.**

Obrigatório:

1. Fonte externa de 5 V com ≥ 3 A.
2. **Nunca** retroalimentar o VBUS do host (diodo ideal, ou cabo sem VBUS).
3. Avaliar display **sem backlight** (e-paper / memory-in-pixel) se o consumo importar —
   e-paper gasta quase nada em imagem estática, o que combina com keycap que muda pouco.

A decisão de display continua sendo a mais crítica do projeto, mais que a de MCU.

---

## 8. Limitações conhecidas

| Item | Situação |
|---|---|
| Roteamento | **não existe** — as placas saem com ratsnest |
| STEP sem os keycaps | o KiCad **não converte VRML → STEP**; os corpos dos switches são um WRML gerado aqui |
| Render 3D | completo, porque usa o WRML |
| Modelo do switch | bloco de 15,6 × 15,6 × 11,4 mm, não é o modelo mecânico real |
| Texto no lado B | não espelhado (199 avisos cosméticos de DRC) |
| `lib_symbol_mismatch` | U1 e U5 usam `extends`; a cópia embarcada difere em metadados |
| Display | sem part number; a área por tecla está reservada, o footprint não existe |
| `multiple_net_names` | consequência de rotular os dois pinos do diodo; inofensivo |

---

## 9. O que falta para virar projeto de verdade

- [ ] Revisar o ADR-0002 (57600 baud) — **bloqueia** firmware e daemon
- [ ] Escolher o display e medir o consumo real
- [ ] Rotear as duas placas no Pcbnew
- [ ] Adicionar TVS nas linhas expostas e capacitor de reset
- [ ] Protótipo de **1 coluna (6 teclas)** antes das 120
- [ ] Medir `UK_MATRIX_SETTLE_US` no cabo real
- [ ] Validar o passo de 19,05 mm com o keycap e a tela montados

---

## 10. Como visualizar e regenerar

```bash
sudo pacman -S kicad kicad-library kicad-library-3d

# esquema completo
kicad docs/hardware/universal-keyboard.kicad_sch

# 3D interativo
kicad docs/hardware/main-board.kicad_pcb      # Ver → Visualizador 3D
```

Regenerar tudo, na ordem:

```bash
python3 tools/gen_hw_netlist.py                 # netlist + BOM
python3 tools/gen_kicad_sch.py                  # esquema + ERC
python3 tools/gen_kicad_pcb.py --render         # 2 PCBs + STEP + SVG + PNG 3D
python3 tools/netlist_to_dot.py --mode block --render
```

No VS Code: `oaslananka.kicadstudiokit` visualiza `.kicad_sch`/`.kicad_pcb`;
`tintinweb.graphviz-interactive-preview` visualiza os `.dot`.

⚠️ Editar o `.kicad_sch`/`.kicad_pcb` dentro do KiCad e depois rodar o gerador
**sobrescreve** tudo. Nesse caso, a fonte da verdade passa a ser o arquivo editado.

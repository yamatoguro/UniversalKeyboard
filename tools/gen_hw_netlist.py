#!/usr/bin/env python3
"""Gera o netlist KiCad e o BOM do esboco matriz + link do UniversalKeyboard.

Artefatos de build: nao editar a mao. A fonte da verdade e este script, que declara
o mapa de conexoes explicitamente em vez de espalhar fios num desenho.

Arquitetura do esboco (ver docs/hardware/matriz-e-link.md):
  - rail unico 3V3: MCU, shift registers e Pi no mesmo nivel logico
  - sem level shifter: elimina o risco de 5V chegar num GPIO do Pi
  - matriz 8x14 via 74HC595 x2 (colunas) + 74HC165 (linhas)

Uso:
    python3 tools/gen_hw_netlist.py

Saida:
    docs/hardware/matrix-link.net   (KiCad legacy netlist)
    docs/hardware/bom.csv           (lista de materiais)

Nao inventa part number de display: o barramento das 112 telas fica fora deste
esboco, conforme ADR pendente.
"""

from __future__ import annotations

import csv
import pathlib
import sys

ROWS = 8
COLS = 14
KEYS = ROWS * COLS

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "hardware"

components: list[tuple[str, str, str, str]] = []


def add_comp(ref: str, value: str, footprint: str, desc: str) -> None:
    components.append((ref, value, footprint, desc))


add_comp("U1", "ATmega328P-PU", "Package_DIP:DIP-28_W7.62mm",
         "MCU AVR 32KB @ 3V3/8MHz (cristal)")
add_comp("U2", "74HC595", "Package_DIP:DIP-16_W7.62mm", "Colunas 0-7")
add_comp("U3", "74HC595", "Package_DIP:DIP-16_W7.62mm", "Colunas 8-13")
add_comp("U4", "74HC165", "Package_DIP:DIP-16_W7.62mm", "Linhas 0-7")

add_comp("Y1", "8MHz", "Crystal:Crystal_HC49-U_Vertical", "Cristal 8MHz")
add_comp("C1", "22pF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Carga do cristal")
add_comp("C2", "22pF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Carga do cristal")
add_comp("C3", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Desacoplamento U1")
add_comp("C4", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Desacoplamento U2")
add_comp("C5", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Desacoplamento U3")
add_comp("C6", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Desacoplamento U4")
add_comp("C7", "10uF", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm", "Bulk da rail 3V3")

add_comp("R1", "10k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm",
         "Pull-up de RESET")
add_comp("R2", "330R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm",
         "Serie do LED de status")
add_comp("RN1", "8x10k", "Resistor_THT:R_Array_SIP9", "Pull-down das linhas 0-7")
add_comp("LED1", "LED", "LED_THT:LED_D3.0mm", "Status do link")

add_comp("J1", "Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
         "Link Pi: 3V3, GND, PiTX, PiRX, spare, GND")
add_comp("J2", "Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
         "ICSP: RESET, 3V3, GND e debug")

for k in range(KEYS):
    add_comp(f"SW{k}", f"K_{k:03d}", "Switch:SW_Push", f"Tecla r{k % ROWS} c{k // ROWS}")
for k in range(KEYS):
    add_comp(f"D{k}", "BAT54", "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
             f"Anti-ghosting da tecla {k}")

nets: dict[str, list[tuple[str, str]]] = {}


def connect(net: str, ref: str, pin: str) -> None:
    node = (ref, pin)
    bucket = nets.setdefault(net, [])
    if node not in bucket:
        bucket.append(node)


# 74HC595: 1 QB 2 QC 3 QD 4 QE 5 QF 6 QG 7 QH 8 GND 9 QH'
#          10 SRCLR 11 SRCLK 12 RCLK 13 OE 14 SER 15 QA 16 VCC
SR595_OUT = {"15": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}

# 74HC165: 1 SH/LD 2 CP 3 D4 4 D5 5 D6 6 D7 7 Q7' 8 GND
#          9 Q7 10 SER 11 D0 12 D1 13 D2 14 D3 15 CE 16 VCC
SR165_IN = {"11": 0, "12": 1, "13": 2, "14": 3, "3": 4, "4": 5, "5": 6, "6": 7}

for ref in ("U2", "U3", "U4"):
    connect("3V3", ref, "16")
    connect("GND", ref, "8")

# ATmega328P DIP-28: 7=VCC, 8=GND, 20=AVCC, 21=AREF, 22=GND
for pin in ("7", "20", "21"):
    connect("3V3", "U1", pin)
for pin in ("8", "22"):
    connect("GND", "U1", pin)

for cap in ("C3", "C4", "C5", "C6"):
    connect("3V3", cap, "1")
    connect("GND", cap, "2")
connect("3V3", "C7", "1")
connect("GND", "C7", "2")

connect("XTAL1", "U1", "9")
connect("XTAL1", "Y1", "1")
connect("XTAL1", "C1", "1")
connect("XTAL2", "U1", "10")
connect("XTAL2", "Y1", "2")
connect("XTAL2", "C2", "1")
connect("GND", "C1", "2")
connect("GND", "C2", "2")

connect("RESET", "U1", "1")
connect("RESET", "R1", "2")
connect("RESET", "J2", "1")
connect("3V3", "R1", "1")
connect("3V3", "J2", "2")
connect("GND", "J2", "3")

# U1: PD2=4 DS, PD3=5 SHCP, PD4=6 STCP, PD5=11 SH/LD, PD6=12 Q7
connect("SR_DS", "U1", "4")
connect("SR_DS", "U2", "14")
connect("SR_CLK", "U1", "5")
connect("SR_CLK", "U2", "11")
connect("SR_CLK", "U3", "11")
connect("SR_CLK", "U4", "2")
connect("SR_LATCH", "U1", "6")
connect("SR_LATCH", "U2", "12")
connect("SR_LATCH", "U3", "12")
connect("SR_LOAD", "U1", "11")
connect("SR_LOAD", "U4", "1")
connect("SR_DATA_IN", "U1", "12")
connect("SR_DATA_IN", "U4", "9")

connect("SR_CASCADE", "U2", "9")
connect("SR_CASCADE", "U3", "14")

for ref in ("U2", "U3"):
    connect("3V3", ref, "10")
    connect("GND", ref, "13")

connect("GND", "U4", "15")
connect("GND", "U4", "10")

for c in range(COLS):
    unit = "U2" if c < 8 else "U3"
    pin = next(p for p, i in SR595_OUT.items() if i == (c % 8))
    connect(f"COL{c}", unit, pin)

for r in range(ROWS):
    pin = next(p for p, i in SR165_IN.items() if i == r)
    connect(f"ROW{r}", "U4", pin)
    connect(f"ROW{r}", "RN1", str(r + 2))
connect("GND", "RN1", "1")

# Matriz: COL -> SW -> anodo D -> catodo D -> ROW
for c in range(COLS):
    for r in range(ROWS):
        k = c * ROWS + r
        connect(f"COL{c}", f"SW{k}", "1")
        connect(f"KEY{k}", f"SW{k}", "2")
        connect(f"KEY{k}", f"D{k}", "2")
        connect(f"ROW{r}", f"D{k}", "1")

# Link com o Pi: UART 3V3 direto
connect("3V3", "J1", "1")
connect("GND", "J1", "2")
connect("PI_TX", "J1", "3")
connect("PI_RX", "J1", "4")
connect("GND", "J1", "6")
connect("PI_TX", "U1", "2")
connect("PI_RX", "U1", "3")

connect("STATUS_LED", "U1", "14")
connect("STATUS_LED", "R2", "1")
connect("LED_A", "R2", "2")
connect("LED_A", "LED1", "2")
connect("GND", "LED1", "1")

# --------------------------------------------------------------------------
# Validacao
# --------------------------------------------------------------------------

errors: list[str] = []
refs = [c[0] for c in components]

if len(refs) != len(set(refs)):
    dup = sorted({r for r in refs if refs.count(r) > 1})
    errors.append(f"referencias duplicadas: {dup}")

refset = set(refs)
for net, nodes in nets.items():
    for ref, _pin in nodes:
        if ref not in refset:
            errors.append(f"rede {net}: referencia desconhecida {ref}")
    if len(nodes) < 2:
        errors.append(f"rede {net}: menos de 2 nos {nodes}")

used = {ref for nodes in nets.values() for ref, _ in nodes}
for ref in refs:
    if ref not in used:
        errors.append(f"componente {ref} sem conexao")

for k in range(KEYS):
    key_net = nets.get(f"KEY{k}", [])
    pairs = {ref for ref, _ in key_net}
    if f"SW{k}" not in pairs or f"D{k}" not in pairs:
        errors.append(f"tecla {k}: cadeia SW/D incompleta em KEY{k}")

if errors:
    for e in errors:
        print(f"erro: {e}", file=sys.stderr)
    sys.exit(1)

# --------------------------------------------------------------------------
# Escrita
# --------------------------------------------------------------------------

OUT_DIR.mkdir(parents=True, exist_ok=True)


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


lines: list[str] = [
    "(export (version D)",
    "  (design",
    '    (source "matrix-link")',
    '    (tool "tools/gen_hw_netlist.py")',
    "  )",
    "  (components",
]
for ref, value, footprint, _desc in components:
    lines.append(f'    (comp (ref "{esc(ref)}") (value "{esc(value)}") '
                 f'(footprint "{esc(footprint)}"))')
lines.append("  )")
lines.append("  (nets")
for code, net in enumerate(sorted(nets), start=1):
    lines.append(f'    (net (code {code}) (name "{esc(net)}")')
    for ref, pin in sorted(nets[net]):
        lines.append(f'      (node (ref "{esc(ref)}") (pin "{esc(pin)}"))')
    lines.append("    )")
lines.append("  )")
lines.append(")")

net_path = OUT_DIR / "matrix-link.net"
net_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

bom_path = OUT_DIR / "bom.csv"
with bom_path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh, lineterminator="\n")
    writer.writerow(["ref", "value", "footprint", "description"])
    writer.writerows(components)

print(f"componentes : {len(components)}")
print(f"redes       : {len(nets)}")
print(f"teclas      : {KEYS} ({ROWS}x{COLS})")
print(f"netlist     : {net_path}")
print(f"bom         : {bom_path}")

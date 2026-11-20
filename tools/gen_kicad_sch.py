#!/usr/bin/env python3
"""Gera o esquema KiCad (.kicad_sch) do UniversalKeyboard a partir do netlist.

O .net e netlist; este script produz o esquema de verdade, editavel no Eeschema,
com simbolos das bibliotecas oficiais do KiCad, conectividade por label e ERC
executavel.

Estrategia: cada pino recebe um stub de fio e um label com o nome da net. Assim a
conectividade vem do netlist (fonte de verdade) e nao do desenho, que vira apenas
cosmetico -- o que permite posicionar os 242 componentes em grade sem rotear.

Requer KiCad instalado (bibliotecas em /usr/share/kicad/symbols).

Uso:
    python3 tools/gen_kicad_sch.py
    kicad-cli sch export svg docs/hardware/universal-keyboard.kicad_sch -o docs/hardware/svg
"""

from __future__ import annotations

import argparse
import math
import pathlib
import re
import subprocess
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
HW = HERE / "docs" / "hardware"
NET_PATH = HW / "matrix-link.net"
SCH_PATH = HW / "universal-keyboard.kicad_sch"

SYMBOL_DIR = pathlib.Path("/usr/share/kicad/symbols")

# ref -> lib_id
LIB_MAP = {
    "U1": "MCU_Microchip_ATmega:ATmega328P-P",
    "U2": "74xx:74HC595",
    "U3": "74xx:74HC595",
    "U4": "74xx:74HC165",
    "J1": "Connector_Generic:Conn_01x06",
    "J2": "Connector_Generic:Conn_01x06",
    "Y1": "Device:Crystal",
    "R1": "Device:R",
    "R2": "Device:R",
    "LED1": "Device:LED",
}
LIB_MAP_SW = "Switch:SW_Push"
LIB_MAP_D = "Device:D_Schottky"
LIB_MAP_C = "Device:C"

POWER_NETS = {"3V3", "GND", "+5V", "+3V3", "VCC", "VSS"}

COMP_RE = re.compile(r'\(comp \(ref "([^"]+)"\) \(value "([^"]*)"\)')
NET_RE = re.compile(r'\(net \(code \d+\) \(name "([^"]+)"\)')
NODE_RE = re.compile(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)')

PIN_RE = re.compile(
    r'\(pin\s+(\S+)\s+(\S+)\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)'
    r'\s*\(length\s+([-\d.]+)\)',
    re.S,
)


# --------------------------------------------------------------------------
# S-expression
# --------------------------------------------------------------------------


def sexpr_slice(text: str, start: int) -> str:
    """Retorna o s-expr balanceado que comeca em start."""
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    raise ValueError("s-expr nao balanceado")


def find_symbol(lib_text: str, name: str) -> str | None:
    for pattern in (f'(symbol "{name}"', f'(symbol "{name}" '):
        i = lib_text.find(pattern)
        if i >= 0:
            return sexpr_slice(lib_text, i)
    # sufixo de unidade: (symbol "R_0_1"
    i = lib_text.find(f'(symbol "{name}_0_1"')
    if i >= 0:
        return sexpr_slice(lib_text, i)
    return None


def extract_pins(symbol_src: str) -> list[tuple[str, float, float, float, float]]:
    """Retorna (numero, x, y, angulo, comprimento) em coordenadas do simbolo."""
    pins: list[tuple[str, float, float, float, float]] = []
    pos = 0
    while True:
        m = PIN_RE.search(symbol_src, pos)
        if not m:
            break
        block = sexpr_slice(symbol_src, m.start())
        num = re.search(r'\(number "([^"]+)"', block)
        if num:
            pins.append((num.group(1), float(m.group(3)), float(m.group(4)),
                         float(m.group(5)), float(m.group(6))))
        pos = m.end()
    return pins


def resolve_symbol(lib_id: str) -> tuple[str, list[tuple[str, float, float, float, float]]]:
    """Carrega o simbolo e devolve (s-expr com nome qualificado, pinos).

    Resolve `extends`, renomeando o simbolo pai para o nome do filho e ajustando
    os sub-simbolos (que no .kicad_sch usam o nome base, sem o prefixo da lib).
    """
    lib, name = lib_id.split(":", 1)
    path = SYMBOL_DIR / f"{lib}.kicad_sym"
    if not path.exists():
        raise FileNotFoundError(f"biblioteca ausente: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")

    src = find_symbol(text, name)
    if src is None:
        raise LookupError(f"simbolo {name} nao encontrado em {path}")

    m = re.search(r'\(extends "([^"]+)"', src)
    if m:
        parent = m.group(1)
        parent_src = find_symbol(text, parent)
        if parent_src is None:
            raise LookupError(f"extends {parent} nao resolvido para {name}")
        base = parent_src
        # nome do filho nos sub-simbolos
        parent_src = parent_src.replace(f'(symbol "{parent}_', f'(symbol "{name}_')
        # nome qualificado na raiz
        parent_src = parent_src.replace(f'(symbol "{parent}"',
                                        f'(symbol "{lib}:{name}"', 1)
        # propriedades do filho sobrescrevem as do pai
        for prop in ("Reference", "Value"):
            child = re.search(rf'\(property "{prop}" "([^"]*)"', src)
            if child:
                parent_src = re.sub(rf'\(property "{prop}" "[^"]*"',
                                    f'(property "{prop}" "{child.group(1)}"',
                                    parent_src, count=1)
        return parent_src, extract_pins(base)

    qualified = src.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    return qualified, extract_pins(src)


# --------------------------------------------------------------------------
# Netlist
# --------------------------------------------------------------------------


def parse_netlist(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    comps = {m.group(1): m.group(2) for m in COMP_RE.finditer(text)}

    nets: dict[str, list[tuple[str, str]]] = {}
    current = None
    for line in text.splitlines():
        s = line.strip()
        m = NET_RE.search(s)
        if m:
            current = m.group(1)
            nets.setdefault(current, [])
            continue
        m = NODE_RE.search(s)
        if m and current is not None:
            nets[current].append((m.group(1), m.group(2)))
            continue
        if s == ")" and current is not None:
            current = None

    pin_net: dict[tuple[str, str], str] = {}
    for net, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[(ref, pin)] = net
    return comps, nets, pin_net


def lib_id_for(ref: str) -> str:
    if ref in LIB_MAP:
        return LIB_MAP[ref]
    if ref.startswith("SW"):
        return LIB_MAP_SW
    if re.fullmatch(r"D\d+", ref):
        return LIB_MAP_D
    if re.fullmatch(r"C\d+", ref):
        return LIB_MAP_C
    if re.fullmatch(r"R\d+", ref):
        return "Device:R"
    raise KeyError(f"sem lib_id para {ref}")


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def layout(comps: dict[str, str]) -> dict[str, tuple[float, float]]:
    pos: dict[str, tuple[float, float]] = {}

    # bloco de controle no topo
    pos["J1"] = (60.0, 60.0)
    pos["J2"] = (60.0, 100.0)
    pos["U1"] = (170.0, 95.0)
    pos["Y1"] = (110.0, 140.0)
    pos["R1"] = (95.0, 60.0)
    pos["R2"] = (250.0, 45.0)
    pos["LED1"] = (280.0, 45.0)
    pos["U2"] = (330.0, 80.0)
    pos["U3"] = (390.0, 80.0)
    pos["U4"] = (330.0, 140.0)

    for i, ref in enumerate(sorted(r for r in comps if re.fullmatch(r"C\d+", r))):
        pos[ref] = (440.0 + (i % 4) * 22.0, 60.0 + (i // 4) * 28.0)

    # pull-downs discretos das linhas
    for i, ref in enumerate(sorted((r for r in comps if re.fullmatch(r"R\d+", r)),
                                   key=lambda r: int(r[1:]))):
        if ref in pos:
            continue
        pos[ref] = (470.0 + (i % 4) * 22.0, 150.0 + (i // 4) * 26.0)

    # matriz: 14 colunas x 8 linhas de (SW, D)
    x0, y0 = 40.0, 230.0
    for c in range(14):
        for r in range(8):
            k = c * 8 + r
            pos[f"SW{k}"] = (x0 + c * 82.0, y0 + r * 46.0)
            pos[f"D{k}"] = (x0 + c * 82.0 + 26.0, y0 + r * 46.0)

    missing = [r for r in comps if r not in pos]
    if missing:
        raise KeyError(f"sem posicao para: {missing[:5]}")
    return pos


# --------------------------------------------------------------------------
# Escrita do esquema
# --------------------------------------------------------------------------


GRID = 1.27


def snap(v: float) -> float:
    """Alinha ao grid de 1.27 mm (50 mil), exigido pelo KiCad para conexoes."""
    return round(v / GRID) * GRID


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def new_uuid() -> str:
    return str(uuid.uuid4())


def build(comps: dict[str, str], pin_net: dict[tuple[str, str], str]) -> str:
    pos = layout(comps)

    # simbolos unicos usados
    lib_ids = sorted({lib_id_for(r) for r in comps}) + ["power:PWR_FLAG"]
    resolved: dict[str, tuple[str, list]] = {}
    for lid in lib_ids:
        resolved[lid] = resolve_symbol(lid)

    out: list[str] = []
    out.append("(kicad_sch")
    out.append("\t(version 20250114)")
    out.append('\t(generator "eeschema")')
    out.append('\t(generator_version "10.0")')
    out.append(f'\t(uuid "{new_uuid()}")')
    out.append('\t(paper "A0")')
    out.append("\n\t(lib_symbols")
    for lid in lib_ids:
        src, _pins = resolved[lid]
        out.append("\t\t" + src.replace("\n", "\n\t\t"))
    out.append("\t)")

    out.append(f'\t(text "UniversalKeyboard - matriz 8x14 + link Pi"')
    out.append(f'\t\t(at 40 24 0)')
    out.append('\t\t(effects (font (size 3 3) bold) (justify left bottom))')
    out.append(f'\t\t(uuid "{new_uuid()}")')
    out.append("\t)")

    wires: list[str] = []
    labels: list[str] = []
    noconnects: list[str] = []

    for ref in sorted(comps, key=lambda r: (r[0], int(re.sub(r"\D", "", r) or 0))):
        lid = lib_id_for(ref)
        _src, pins = resolved[lid]
        x, y = snap(pos[ref][0]), snap(pos[ref][1])
        value = comps[ref]

        out.append(f'\t(symbol (lib_id "{lid}") (at {x:.2f} {y:.2f} 0) (unit 1)')
        out.append("\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)")
        out.append(f'\t\t(uuid "{new_uuid()}")')
        out.append(f'\t\t(property "Reference" "{esc(ref)}" (at {x:.2f} {y - 2.54:.2f} 0)')
        out.append("\t\t\t(effects (font (size 1.27 1.27)))")
        out.append("\t\t)")
        out.append(f'\t\t(property "Value" "{esc(value)}" (at {x:.2f} {y + 2.54:.2f} 0)')
        out.append("\t\t\t(effects (font (size 1.27 1.27)))")
        out.append("\t\t)")
        out.append(f'\t\t(property "Footprint" "" (at {x:.2f} {y:.2f} 0)')
        out.append("\t\t\t(effects (font (size 1.27 1.27)) hide)")
        out.append("\t\t)")
        for num, _px, _py, _ang, _ln in pins:
            out.append(f'\t\t(pin "{esc(num)}" (uuid "{new_uuid()}"))')
        out.append("\t\t(instances")
        out.append('\t\t\t(project ""')
        out.append(f'\t\t\t\t(path "/" (reference "{esc(ref)}") (unit 1))')
        out.append("\t\t\t)")
        out.append("\t\t)")
        out.append("\t)")

        # stub + label por pino
        for num, px, py, ang, _ln in pins:
            sx = x + px
            sy = y - py          # simbolo e Y-up; esquema e Y-down
            rad = math.radians(ang)
            ox, oy = -math.cos(rad), math.sin(rad)   # para fora, ja em coords de esquema
            stub = 3.81
            ex, ey = sx + ox * stub, sy + oy * stub
            if abs(ox) > abs(oy):
                ex = sx + (stub if ox > 0 else -stub)
                ey = sy
            else:
                ex = sx
                ey = sy + (stub if oy > 0 else -stub)

            sx, sy, ex, ey = snap(sx), snap(sy), snap(ex), snap(ey)
            net = pin_net.get((ref, num))
            if net is None:
                # pino sem net no netlist: marca explicitamente para o ERC
                noconnects.append(f'\t(no_connect (at {sx:.2f} {sy:.2f})'
                                  f' (uuid "{new_uuid()}"))')
                continue

            wires.append(f'\t(wire (pts (xy {sx:.2f} {sy:.2f}) (xy {ex:.2f} {ey:.2f}))')
            wires.append("\t\t(stroke (width 0) (type default))")
            wires.append(f'\t\t(uuid "{new_uuid()}")')
            wires.append("\t)")

            if net:
                just = "left" if ox >= 0 else "right"
                labels.append(f'\t(label "{esc(net)}" (at {ex:.2f} {ey:.2f} 0)')
                labels.append("\t\t(effects (font (size 1.27 1.27))"
                              f" (justify {just} bottom))")
                labels.append(f'\t\t(uuid "{new_uuid()}")')
                labels.append("\t)")

    out.extend(wires)
    out.extend(noconnects)
    out.extend(labels)

    # PWR_FLAG para o ERC reconhecer as rails como alimentadas
    for i, rail in enumerate(("3V3", "GND")):
        px, py = snap(560.0), snap(60.0 + i * 30.0)
        out.append(f'\t(symbol (lib_id "power:PWR_FLAG") (at {px:.2f} {py:.2f} 0) (unit 1)')
        out.append("\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)")
        out.append(f'\t\t(uuid "{new_uuid()}")')
        out.append(f'\t\t(property "Reference" "#FLG{i + 1:02d}" (at {px:.2f} {py - 2.54:.2f} 0)')
        out.append("\t\t\t(effects (font (size 1.27 1.27)) hide)")
        out.append("\t\t)")
        out.append(f'\t\t(property "Value" "PWR_FLAG" (at {px:.2f} {py + 5.08:.2f} 0)')
        out.append("\t\t\t(effects (font (size 1.27 1.27)))")
        out.append("\t\t)")
        out.append(f'\t\t(pin "1" (uuid "{new_uuid()}"))')
        out.append("\t\t(instances")
        out.append('\t\t\t(project ""')
        out.append(f'\t\t\t\t(path "/" (reference "#FLG{i + 1:02d}") (unit 1))')
        out.append("\t\t\t)")
        out.append("\t\t)")
        out.append("\t)")
        out.append(f'\t(wire (pts (xy {px:.2f} {py:.2f}) (xy {px:.2f} {py + 2.54:.2f}))')
        out.append("\t\t(stroke (width 0) (type default))")
        out.append(f'\t\t(uuid "{new_uuid()}")')
        out.append("\t)")
        out.append(f'\t(label "{rail}" (at {px:.2f} {py + 2.54:.2f} 0)')
        out.append("\t\t(effects (font (size 1.27 1.27)) (justify left bottom))")
        out.append(f'\t\t(uuid "{new_uuid()}")')
        out.append("\t)")
    out.append('\n\t(sheet_instances (path "/" (page "1")))')
    out.append(")")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-verify", action="store_true", help="nao roda kicad-cli")
    args = ap.parse_args()

    if not NET_PATH.exists():
        print(f"erro: {NET_PATH} ausente; rode tools/gen_hw_netlist.py", file=sys.stderr)
        return 1
    if not SYMBOL_DIR.exists():
        print(f"erro: bibliotecas KiCad ausentes em {SYMBOL_DIR}. "
              "Instale o pacote kicad-library.", file=sys.stderr)
        return 1

    comps, nets, pin_net = parse_netlist(NET_PATH)
    print(f"componentes : {len(comps)}")
    print(f"redes       : {len(nets)}")
    print(f"pinos       : {len(pin_net)}")

    text = build(comps, pin_net)
    SCH_PATH.write_text(text, encoding="utf-8")
    print(f"esquema     : {SCH_PATH}  ({SCH_PATH.stat().st_size} bytes)")

    if args.no_verify:
        return 0

    # validacao real: o KiCad precisa conseguir abrir e plotar
    svg_dir = HW / "svg"
    svg_dir.mkdir(exist_ok=True)
    r = subprocess.run(["kicad-cli", "sch", "export", "svg", str(SCH_PATH),
                        "-o", str(svg_dir), "--no-background-color"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("FALHA ao plotar:", r.stdout, r.stderr, sep="\n", file=sys.stderr)
        return 1
    print(f"plot        : {svg_dir}  verificacao OK")

    # sym-lib-table evita o aviso lib_symbol_issues (libs nao configuradas)
    libs = sorted({lid.split(":")[0] for lid in
                   {"Device", "Switch", "74xx", "Connector_Generic",
                    "MCU_Microchip_ATmega", "power"} | {lib_id_for(r).split(":")[0] for r in comps}})
    table = ["(sym_lib_table", "\t(version 7)"]
    for lib in libs:
        table.append(f'\t(lib (name "{lib}")(type "KiCad")'
                     f'(uri "${{KICAD10_SYMBOL_DIR}}/{lib}.kicad_sym")'
                     f'(options "")(descr ""))')
    table.append(")")
    (HW / "sym-lib-table").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"sym-lib-table: {HW / 'sym-lib-table'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

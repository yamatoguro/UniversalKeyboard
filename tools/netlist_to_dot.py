#!/usr/bin/env python3
"""Converte o netlist KiCad em grafos Graphviz legiveis para o VS Code.

O .net e netlist, nao esquema: nenhuma extensao desenha um esquema a partir dele.
Este script deriva a conectividade real do arquivo e produz grafos que o Graphviz
(ou a extensao Graphviz Interactive Preview) renderiza nativamente.

Modos:
    block   blocos funcionais ligados por nets de sinal (sem GND/3V3)
    matrix  detalhe eletrico de uma coluna (8 teclas com diodo)
    nets    grafo bipartido componente <-> net compartilhado

Uso:
    python3 tools/netlist_to_dot.py --render
    python3 tools/netlist_to_dot.py --mode matrix --render

Saida em docs/hardware/: matrix-link-<modo>.dot e .svg
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
NET_DIR = HERE / "docs" / "hardware"
NET_PATH = NET_DIR / "matrix-link.net"

POWER_NETS = {"3V3", "+5V", "GND", "+3V3", "VCC", "VSS"}

COMP_RE = re.compile(r'\(comp \(ref "([^"]+)"\) \(value "([^"]*)"\)')
NET_RE = re.compile(r'\(net \(code \d+\) \(name "([^"]+)"\)')
NODE_RE = re.compile(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)')


def parse_netlist(path: pathlib.Path) -> tuple[dict[str, str], dict[str, list[tuple[str, str]]]]:
    text = path.read_text(encoding="utf-8")

    comps: dict[str, str] = {m.group(1): m.group(2) for m in COMP_RE.finditer(text)}

    nets: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
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
    return comps, nets


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def head(title: str, rankdir: str = "LR", kind: str = "digraph") -> list[str]:
    return [
        f"{kind} g {{",
        f'  graph [rankdir={rankdir}, fontname="Helvetica", fontsize=11, bgcolor="white",',
        "         pad=0.5, nodesep=0.45, ranksep=1.0,",
        f'         label="{esc(title)}", labelloc=t, fontsize=15];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];',
        '  edge [fontname="Helvetica", fontsize=8, color="#475569"];',
        "",
    ]


# --------------------------------------------------------------------------
# modo block: blocos funcionais, apenas nets de sinal
# --------------------------------------------------------------------------

BLOCKS = [
    ("cluster_host", "Link com o Pi", ["J1"]),
    ("cluster_mcu", "MCU (3V3)", ["U1"]),
    ("cluster_sr", "Shift registers", ["U2", "U3", "U4"]),
    ("cluster_clock", "Clock e reset", ["Y1", "C1", "C2", "R1", "J2"]),
    ("cluster_status", "Status", ["LED1", "R2"]),
]


def build_block(comps: dict[str, str], nets: dict[str, list[tuple[str, str]]]) -> str:
    placed = {ref for _, _, refs in BLOCKS for ref in refs}

    out = head("UniversalKeyboard — blocos funcionais (nets de sinal, sem alimentacao)")

    for cid, label, refs in BLOCKS:
        present = [r for r in refs if r in comps]
        if not present:
            continue
        out.append(f"  subgraph {cid} {{")
        out.append(f'    label="{esc(label)}"; style="rounded,dashed"; color="#94a3b8";')
        for ref in present:
            out.append(f'    "{esc(ref)}" [label="{esc(ref)}\\n{esc(comps[ref])}"];')
        out.append("  }")
    out.append("")

    # arestas: nets de sinal entre componentes posicionados
    seen: set[tuple[str, str, str]] = set()
    for net, nodes in sorted(nets.items()):
        if net in POWER_NETS:
            continue
        refs = sorted({r for r, _ in nodes if r in placed})
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                key = (refs[i], refs[j], net)
                if key in seen:
                    continue
                seen.add(key)
                out.append(f'  "{esc(refs[i])}" -> "{esc(refs[j])}" '
                           f'[label="{esc(net)}", dir=none, penwidth=1.3];')
    out.append("")

    # nets de sinal que saem para a matriz
    out.append('  "COL0..13" [shape=box, style="rounded,filled", fillcolor="#ecfdf5",'
               ' color="#065f46", label="COL0..13\\npara a matriz"];')
    out.append('  "ROW0..7" [shape=box, style="rounded,filled", fillcolor="#ecfdf5",'
               ' color="#065f46", label="ROW0..7\\npara a matriz"];')
    out.append('  "U2" -> "COL0..13" [dir=none, color="#065f46", style=dashed];')
    out.append('  "U3" -> "COL0..13" [dir=none, color="#065f46", style=dashed];')
    out.append('  "ROW0..7" -> "U4" [dir=none, color="#065f46", style=dashed];')
    out.append("}")

    # remove componentes nao posicionados que sobraram (passivos)
    return "\n".join(out)


# --------------------------------------------------------------------------
# modo matrix: detalhe de uma coluna
# --------------------------------------------------------------------------


def build_matrix(comps: dict[str, str], nets: dict[str, list[tuple[str, str]]], col: int = 0) -> str:
    keys: list[tuple[int, str, str]] = []   # (row, sw, diode)
    for net, nodes in nets.items():
        if net != f"COL{col}":
            continue
        for ref, pin in nodes:
            if ref.startswith("SW") and pin == "1":
                sw = ref
                di = "D" + ref[2:]
                row = None
                for n2, nodes2 in nets.items():
                    m = re.fullmatch(r"ROW(\d+)", n2)
                    if m and any(r == di and p == "1" for r, p in nodes2):
                        row = int(m.group(1))
                if row is not None:
                    keys.append((row, sw, di))
    keys.sort()

    out = head(f"Matriz 8x14 — detalhe da COL{col}", rankdir="TB")
    out.append('  "COL" [shape=box, style="rounded,filled", fillcolor="#dbeafe",'
               f' color="#1e40af", label="COL{col}\\n(saida do 74HC595)"];')
    out.append('  "GND" [shape=box, style="rounded,filled", fillcolor="#f1f5f9",'
               ' color="#475569", label="pull-down 10k\\n+ entrada do 74HC165"];')
    out.append("")
    out.append("  { rank=same;")
    for _, sw, di in keys:
        out.append(f'    "{esc(sw)}" [label="{esc(sw)}\\nchave", fillcolor="#ecfdf5",'
                   ' color="#065f46"];')
    out.append("  }")
    out.append("  { rank=same;")
    for _, sw, di in keys:
        out.append(f'    "{esc(di)}" [label="{esc(di)}\\nBAT54", fillcolor="#fef3c7",'
                   ' color="#92400e"];')
    out.append("  }")
    out.append("")
    for row, sw, di in keys:
        out.append(f'  "COL" -> "{esc(sw)}";')
        out.append(f'  "{esc(sw)}" -> "{esc(di)}" [label="R{row}"];')
        out.append(f'  "{esc(di)}" -> "GND";')
    out.append("")
    out.append('  "note" [shape=note, style=filled, fillcolor="#fffbeb", color="#d97706",')
    out.append('          label="key_idx = coluna * 8 + linha\\l'
               'Fluxo: COL alto -> SW fechada -> diodo -> ROW sobe (3,0V)\\l'
               'Diodo impede ghosting com 3+ teclas\\l"];')
    out.append("}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# modo nets: bipartido
# --------------------------------------------------------------------------


def build_nets(comps: dict[str, str], nets: dict[str, list[tuple[str, str]]]) -> str:
    shared = {n: v for n, v in nets.items()
              if n not in POWER_NETS and len({r for r, _ in v}) >= 3}

    out = head(f"Nets compartilhados ({len(shared)} de {len(nets)}; alimentacao omitida)",
               kind="graph")
    refs = sorted({r for v in shared.values() for r, _ in v})
    out.append("  { rank=same;")
    for ref in refs:
        out.append(f'    "{esc(ref)}" [label="{esc(ref)}"];')
    out.append("  }")
    out.append("")
    for net in sorted(shared):
        out.append(f'  "{esc(net)}" [shape=ellipse, fillcolor="#e0f2fe", color="#0369a1",'
                   ' fontsize=9];')
    out.append("")
    for net in sorted(shared):
        for ref, _pin in sorted(shared[net]):
            out.append(f'  "{esc(net)}" -- "{esc(ref)}";')
    out.append("}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("block", "matrix", "nets"), default="block")
    ap.add_argument("--render", action="store_true", help="gera SVG via dot")
    args = ap.parse_args()

    if not NET_PATH.exists():
        print(f"erro: {NET_PATH} nao existe. Rode tools/gen_hw_netlist.py antes.", file=sys.stderr)
        return 1

    comps, nets = parse_netlist(NET_PATH)
    if not comps or not nets:
        print("erro: netlist vazio ou ilegivel", file=sys.stderr)
        return 1

    builders = {"block": build_block, "matrix": build_matrix, "nets": build_nets}
    dot_text = builders[args.mode](comps, nets)

    dot_path = NET_DIR / f"matrix-link-{args.mode}.dot"
    dot_path.write_text(dot_text + "\n", encoding="utf-8")
    print(f"componentes : {len(comps)}")
    print(f"redes       : {len(nets)}")
    print(f"dot         : {dot_path}")

    if args.render:
        if not shutil.which("dot"):
            print("aviso: graphviz ausente; SVG nao gerado", file=sys.stderr)
            return 0
        svg = dot_path.with_suffix(".svg")
        r = subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(svg)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"erro do dot: {r.stderr}", file=sys.stderr)
            return 1
        print(f"svg         : {svg}  ({svg.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

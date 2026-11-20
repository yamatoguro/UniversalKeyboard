#!/usr/bin/env python3
"""Gera as PCBs (.kicad_pcb) do UniversalKeyboard a partir do netlist.

Duas placas, conforme decisao do projeto:
  1. placa da matriz  - 120 switches MX + 120 diodos + conector J3 + furos
  2. placa de controle - MCU, 3x 74HC595, 1x 74HC165, clock, passivos, J1/J2/J4

Nao ha roteamento: a placa sai com ratsnest, pronta para rotear no Pcbnew.
A conectividade vem do netlist (fonte da verdade), nao do desenho.

Requer KiCad instalado (footprints em /usr/share/kicad/footprints).

Uso:
    python3 tools/gen_kicad_pcb.py
    python3 tools/gen_kicad_pcb.py --render   # exporta STEP e SVG
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
HW = HERE / "docs" / "hardware"
NET_PATH = HW / "matrix-link.net"

FP_DIR = pathlib.Path("/usr/share/kicad/footprints")

sys.path.insert(0, str(HERE / "tools"))
from layout_fullsize import positions as key_positions, board_size  # noqa: E402

COMP_RE = re.compile(r'\(comp \(ref "([^"]+)"\) \(value "([^"]*)"\)')
NET_RE = re.compile(r'\(net \(code \d+\) \(name "([^"]+)"\)')
NODE_RE = re.compile(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)')

MARGIN = 8.0

# O KiCad nao publica modelo 3D do Cherry MX (peca mecanica). Sem isso o render
# 3D mostraria so a placa. Geramos um bloco de 15.6 x 15.6 x 11.4 mm.
SW_BODY_MM = (15.6, 15.6, 11.4)
SW_WRL_REL = "3d/switch_1u.wrl"


def write_switch_wrl(dest: pathlib.Path) -> None:
    """WRL usa 1 unidade = 2.54 mm (0.1 in) e eixo Y para cima."""
    w, d, h = (v / 2.54 for v in SW_BODY_MM)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "#VRML V2.0 utf8\n"
        "# Placeholder do switch Cherry MX 1u: 15.6 x 15.6 x 11.4 mm\n"
        "Transform {\n"
        f"  translation 0 {h / 2:.4f} 0\n"
        "  children [\n"
        "    Shape {\n"
        "      appearance Appearance {\n"
        "        material Material { diffuseColor 0.22 0.22 0.26 ambientIntensity 0.35 }\n"
        "      }\n"
        f"      geometry Box {{ size {w:.4f} {h:.4f} {d:.4f} }}\n"
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )

# pegada por referencia
def footprint_for(ref: str) -> str:
    table = {
        "U1": "Package_DIP:DIP-28_W7.62mm:Package_DIP",
        "U2": "Package_DIP:DIP-16_W7.62mm:Package_DIP",
        "U3": "Package_DIP:DIP-16_W7.62mm:Package_DIP",
        "U4": "Package_DIP:DIP-16_W7.62mm:Package_DIP",
        "U5": "Package_DIP:DIP-16_W7.62mm:Package_DIP",
        "J1": "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical:Connector_PinHeader_2.54mm",
        "J2": "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical:Connector_PinHeader_2.54mm",
        "J3": "Connector_PinHeader_2.54mm:PinHeader_2x17_P2.54mm_Vertical:Connector_PinHeader_2.54mm",
        "J4": "Connector_PinHeader_2.54mm:PinHeader_2x17_P2.54mm_Vertical:Connector_PinHeader_2.54mm",
        "Y1": "Crystal:Crystal_HC49-U_Vertical:Crystal",
        "LED1": "LED_THT:LED_D3.0mm:LED_THT",
    }
    if ref in table:
        return table[ref]
    if ref.startswith("SW"):
        return "Button_Switch_Keyboard:SW_Cherry_MX_1.00u_PCB:Button_Switch_Keyboard"
    if re.fullmatch(r"D\d+", ref):
        return "Diode_SMD:D_SOD-123:Diode_SMD"
    if re.fullmatch(r"C\d+", ref):
        return "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm:Capacitor_THT"
    if re.fullmatch(r"R\d+", ref):
        return "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal:Resistor_THT"
    raise KeyError(f"sem footprint para {ref}")


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
            if net == "GND":
                pin_net[(ref, pin)] = "GND"
            else:
                pin_net[(ref, pin)] = net
    return comps, nets, pin_net


# --------------------------------------------------------------------------
# Footprints
# --------------------------------------------------------------------------


def balanced(text: str, start: int) -> str:
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
    raise ValueError("nao balanceado")


def inject_nets(src: str, pad_nets: dict[str, tuple[int, str]]) -> str:
    """Adiciona (net N "NOME") em cada pad com numero conhecido."""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r'\(pad "([^"]*)"', src):
        if m.start() < pos:
            continue
        block = balanced(src, m.start())
        num = m.group(1)
        out.append(src[pos : m.start()])
        if num in pad_nets:
            nid, nname = pad_nets[num]
            body = block[:-1]
            block = f'{body}\n\t\t(net {nid} "{nname}")\n\t)'
        out.append(block)
        pos = m.start() + len(block) if num in pad_nets else m.start() + len(block)
        pos = m.start() + len(balanced(src, m.start()))
    out.append(src[pos:])
    return "".join(out)



def pad_centroid(src: str) -> tuple[float, float]:
    """Centro da caixa dos pads, em coordenadas locais do footprint.

    Os footprints DIP do KiCad tem origem no pino 1, nao no centro; sem isso o
    componente e desenhado deslocado do ponto pedido.
    """
    xs: list[float] = []
    ys: list[float] = []
    for m in re.finditer(r'\(pad "[^"]*"', src):
        block = balanced(src, m.start())
        at = re.search(r"\(at ([+-]?[\d.]+) ([+-]?[\d.]+)", block)
        if at:
            xs.append(float(at.group(1)))
            ys.append(float(at.group(2)))
    if not xs:
        return 0.0, 0.0
    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


def centered_at(x: float, y: float, rot: float, cx: float, cy: float) -> tuple[float, float]:
    """Posicao do footprint para que o centro dos pads caia em (x, y)."""
    import math as _m
    th = _m.radians(rot)
    c, s = _m.cos(th), _m.sin(th)
    return (x - (cx * c + cy * s), y + (cx * s - cy * c))


def make_footprint(ref: str, value: str, lib_id: str, x: float, y: float,
                   pin_net: dict[tuple[str, str], str], net_ids: dict[str, int],
                   rot: float = 0.0, side: str = "F") -> str:
    lib, name, libdir = lib_id.split(":")
    path = FP_DIR / f"{libdir}.pretty" / f"{name}.kicad_mod"
    if not path.exists():
        raise FileNotFoundError(path)
    src = path.read_text(encoding="utf-8")

    src = src.replace(f'(footprint "{name}"', f'(footprint "{lib}:{name}"', 1)
    src = re.sub(r"\n\t\(version [^)]*\)", "", src)
    src = re.sub(r"\n\t\(generator \"[^\"]*\"\)", "", src)
    src = re.sub(r"\n\t\(generator_version \"[^\"]*\"\)", "", src)

    # uuid + at logo apos a layer do footprint
    cx, cy = pad_centroid(src)
    ax, ay = centered_at(x, y, rot, cx, cy)
    uid = str(uuid.uuid4())
    src = re.sub(r'\n\t\(layer "([^"]+)"\)',
                 lambda m: f'\n\t(layer "{m.group(1)}")\n\t(uuid "{uid}")\n\t(at {ax:.3f} {ay:.3f} {rot:g})',
                 src, count=1)

    # Reference / Value
    src = re.sub(r'(\(property "Reference" )"REF\*\*"', lambda m: f'{m.group(1)}"{ref}"', src, count=1)
    src = re.sub(r'(\(property "Value" )"[^"]*"', lambda m: f'{m.group(1)}"{value}"', src, count=1)

    if side == "B":
        # Espelha para o lado inferior trocando as camadas numa unica passada:
        # trocar em sequencia faria "F.Cu" -> "B.Cu" -> "F.Cu" e desfaria a troca.
        _flip = {"F.Cu": "B.Cu", "B.Cu": "F.Cu",
                 "F.SilkS": "B.SilkS", "B.SilkS": "F.SilkS",
                 "F.Mask": "B.Mask", "B.Mask": "F.Mask",
                 "F.Paste": "B.Paste", "B.Paste": "F.Paste",
                 "F.Fab": "B.Fab", "B.Fab": "F.Fab",
                 "F.CrtYd": "B.CrtYd", "B.CrtYd": "F.CrtYd",
                 "F.Adhes": "B.Adhes", "B.Adhes": "F.Adhes"}
        _pat = "|".join(re.escape(k) for k in _flip)
        src = re.sub(r'"(' + _pat + r')"', lambda m: f'"{_flip[m.group(1)]}"', src)

    if ref.startswith("SW"):
        src = re.sub(
            r'\(model "[^"]*"\)',
            f'(model "${{KIPRJMOD}}/{SW_WRL_REL}")',
            src,
        )
        src = re.sub(
            r'\(model "[^"]*"',
            f'(model "${{KIPRJMOD}}/{SW_WRL_REL}"',
            src,
        )

    pad_nets: dict[str, tuple[int, str]] = {}
    for (r, pin), net in pin_net.items():
        if r == ref and net in net_ids:
            pad_nets[pin] = (net_ids[net], net)
    return inject_nets(src, pad_nets)


def write_board(path: pathlib.Path, comps: dict[str, str],
                placements: dict[str, tuple[float, float, float]],
                pin_net: dict[tuple[str, str], str], nets: dict[str, list[tuple[str, str]]],
                size: tuple[float, float], keepouts: list[tuple[float, float, float, float]],
                holes: list[tuple[float, float]]) -> None:
    used_refs = sorted(placements)
    used_nets = sorted({pin_net[(r, p)] for r in used_refs
                        for (rr, p) in pin_net if rr == r})
    net_ids = {n: i for i, n in enumerate(used_nets, start=1)}

    out = [
        "(kicad_pcb",
        "\t(version 20250114)",
        '\t(generator "pcbnew")',
        '\t(generator_version "10.0")',
        "\t(general (thickness 1.6) (legacy_teardrops no))",
        '\t(paper "A2")',
        "\t(layers",
        '\t\t(0 "F.Cu" signal)',
        '\t\t(31 "B.Cu" signal)',
        '\t\t(32 "B.Adhes" user "B.Adhesive")',
        '\t\t(33 "F.Adhes" user "F.Adhesive")',
        '\t\t(34 "B.Paste" user)',
        '\t\t(35 "F.Paste" user)',
        '\t\t(36 "B.SilkS" user "B.Silkscreen")',
        '\t\t(37 "F.SilkS" user "F.Silkscreen")',
        '\t\t(38 "B.Mask" user)',
        '\t\t(39 "F.Mask" user)',
        '\t\t(40 "Dwgs.User" user "User.Drawings")',
        '\t\t(41 "Cmts.User" user "User.Comments")',
        '\t\t(42 "Eco1.User" user "User.Eco1")',
        '\t\t(43 "Eco2.User" user "User.Eco2")',
        '\t\t(44 "Edge.Cuts" user)',
        '\t\t(45 "Margin" user)',
        '\t\t(46 "B.CrtYd" user "B.Courtyard")',
        '\t\t(47 "F.CrtYd" user "F.Courtyard")',
        '\t\t(48 "B.Fab" user)',
        '\t\t(49 "F.Fab" user)',
        "\t)",
        '\t(setup (pad_to_mask_clearance 0))',
        '\t(net 0 "")',
    ]
    for nid in sorted(net_ids, key=lambda n: net_ids[n]):
        out.append(f'\t(net {net_ids[nid]} "{nid}")')

    for x, y in holes:
        out.append(make_footprint(f"H{int(x)}{int(y)}", "MountingHole", 
                                  "MountingHole:MountingHole_3.2mm_M3:MountingHole",
                                  x, y, {}, net_ids))

    for ref in used_refs:
        entry = placements[ref]
        px, py, rot = entry[0], entry[1], entry[2]
        side = entry[3] if len(entry) > 3 else "F"
        out.append(make_footprint(ref, comps.get(ref, ""), footprint_for(ref),
                                  px, py, pin_net, net_ids, rot=rot, side=side))

    # contorno da placa
    w, h = size
    uid = uuid.uuid4()
    out.append(f'\t(gr_rect (start 0 0) (end {w:.3f} {h:.3f})'
               '\n\t\t(stroke (width 0.1) (type default)) (fill none)'
               f'\n\t\t(layer "Edge.Cuts") (uuid "{uid}")\n\t)')

    # area reservada para o display de cada tecla
    for kx, ky, kw, kh in keepouts:
        out.append(f'\t(gr_rect (start {kx - kw / 2:.3f} {ky - kh / 2:.3f})'
                   f' (end {kx + kw / 2:.3f} {ky + kh / 2:.3f})'
                   '\n\t\t(stroke (width 0.15) (type dash)) (fill none)'
                   f'\n\t\t(layer "Dwgs.User") (uuid "{uuid.uuid4()}")\n\t)')

    out.append(")")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Placas
# --------------------------------------------------------------------------


def build_main_board(comps, pin_net) -> tuple[pathlib.Path, tuple[float, float]]:
    keys = key_positions()
    w_keys, h_keys = board_size()

    width = w_keys + 2 * MARGIN
    height = h_keys + 2 * MARGIN + 14.0   # faixa extra para o conector J3

    placements: dict[str, tuple[float, float, float]] = {}
    keepouts: list[tuple[float, float, float, float]] = []

    for k in keys:
        ref_sw = f"SW{k['idx']}"
        x = k["x_mm"] + MARGIN
        y = k["y_mm"] + MARGIN
        placements[ref_sw] = (x, y, 0.0, "F")
        placements[f"D{k['idx']}"] = (x, y - 6.2, 0.0, "B")
        keepouts.append((x, y, k["width_mm"] - 1.6, k["height_mm"] - 1.6))

    # J3 na faixa inferior
    placements["J3"] = (60.0, h_keys + MARGIN + 6.0, 90.0, "F")

    holes = [(4.0, 4.0), (width - 4.0, 4.0), (4.0, height - 4.0), (width - 4.0, height - 4.0)]

    path = HW / "main-board.kicad_pcb"
    write_board(path, comps, placements, pin_net, {}, (width, height), keepouts, holes)
    return path, (width, height)


def build_control_board(comps, pin_net) -> tuple[pathlib.Path, tuple[float, float]]:
    width, height = 120.0, 90.0

    # (ref, x, y, rot)
    grid: list[tuple[str, float, float, float]] = [
        ("J1", 18.0, 16.0, 0.0), ("J2", 38.0, 16.0, 0.0),
        ("U1", 22.0, 52.0, 0.0),
        ("Y1", 12.0, 76.0, 0.0), ("C1", 24.0, 84.0, 0.0), ("C2", 26.0, 74.0, 0.0),
        ("C3", 50.0, 20.0, 0.0), ("C4", 50.0, 32.0, 0.0), ("C5", 50.0, 44.0, 0.0),
        ("C6", 50.0, 56.0, 0.0), ("C7", 50.0, 68.0, 0.0),
        ("U2", 70.0, 20.0, 0.0), ("U3", 70.0, 44.0, 0.0), ("U4", 70.0, 68.0, 0.0),
        ("U5", 92.0, 20.0, 0.0), ("C8", 112.0, 36.0, 0.0),
        ("R1", 52.0, 10.0, 0.0),
        ("R3", 92.0, 48.0, 0.0), ("R4", 92.0, 60.0, 0.0), ("R5", 108.0, 48.0, 0.0),
        ("R6", 108.0, 60.0, 0.0), ("R7", 92.0, 72.0, 0.0), ("R8", 108.0, 72.0, 0.0),
        ("R2", 100.0, 84.0, 0.0), ("LED1", 88.0, 84.0, 0.0),
        ("J4", 56.0, 86.0, 90.0),
    ]
    placements = {ref: (x, y, r, "F") for ref, x, y, r in grid if ref in comps}

    holes = [(4.0, 4.0), (width - 4.0, 4.0), (4.0, height - 4.0), (width - 4.0, height - 4.0)]

    path = HW / "control-board.kicad_pcb"
    write_board(path, comps, placements, pin_net, {}, (width, height), [], holes)
    return path, (width, height)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true", help="exporta STEP e SVG")
    args = ap.parse_args()

    if not NET_PATH.exists():
        print(f"erro: {NET_PATH} ausente; rode tools/gen_hw_netlist.py", file=sys.stderr)
        return 1
    if not FP_DIR.exists():
        print(f"erro: footprints ausentes em {FP_DIR}. Instale kicad-library.", file=sys.stderr)
        return 1

    write_switch_wrl(HW / SW_WRL_REL)

    comps, nets, pin_net = parse_netlist(NET_PATH)
    print(f"componentes no netlist: {len(comps)}   redes: {len(nets)}")

    main_path, main_size = build_main_board(comps, pin_net)
    ctrl_path, ctrl_size = build_control_board(comps, pin_net)

    print(f"placa matriz  : {main_path.name}  {main_size[0]:.1f} x {main_size[1]:.1f} mm")
    print(f"placa controle: {ctrl_path.name}  {ctrl_size[0]:.1f} x {ctrl_size[1]:.1f} mm")

    if not args.render:
        return 0

    out = HW / "pcb"
    out.mkdir(exist_ok=True)

    env = dict(os.environ)
    model_dir = pathlib.Path("/usr/share/kicad/3dmodels")
    if model_dir.is_dir():
        env.setdefault("KICAD10_3DMODEL_DIR", str(model_dir))
        env.setdefault("KICAD9_3DMODEL_DIR", str(model_dir))

    for pth in (main_path, ctrl_path):
        jobs = [
            ("step", [], f"{pth.stem}.step"),
            ("svg", ["--layers", "F.Cu,B.Cu,F.SilkS,Edge.Cuts"], f"{pth.stem}.svg"),
        ]
        for fmt, extra, name in jobs:
            target = out / name
            cmd = ["kicad-cli", "pcb", "export", fmt, str(pth), "-o", str(target), *extra]
            r = subprocess.run(cmd, capture_output=True, text=True, env=env)
            # O STEP sai com codigo != 0 quando algum modelo e VRML: o KiCad nao
            # converte VRML para STEP. O arquivo e valido, entao julgamos pelo
            # artefato, e nao pelo codigo de retorno.
            ok = target.exists() and target.stat().st_size > 1024
            if not ok:
                print(f"FALHA {fmt} {pth.name}:\n{r.stdout}\n{r.stderr}", file=sys.stderr)
                return 1
            skipped = r.stdout.count("VRML") + r.stderr.count("VRML")
            note = f"  ({skipped} modelos VRML omitidos)" if skipped else ""
            print(f"  {target.name:30s} {target.stat().st_size / 1024:8.0f} kB{note}")

        for side, tag in (("top", "top"), ("bottom", "bottom")):
            target = out / f"{pth.stem}-3d-{tag}.png"
            cmd = ["kicad-cli", "pcb", "render", "--side", side, "-w", "2000", "-h", "1100",
                   "-o", str(target), str(pth)]
            r = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if r.returncode != 0:
                print(f"FALHA render {pth.name}:\n{r.stdout}\n{r.stderr}", file=sys.stderr)
                return 1
            print(f"  {target.name:30s} {target.stat().st_size / 1024:8.0f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

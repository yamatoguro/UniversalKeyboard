"""Layout fisico full-size (base Keychron V6) com colunas laterais de macro.

Geometria confirmada com o autor do projeto:

  - matriz 6 linhas x 23 colunas
  - 120 teclas: 104 padrao + 12 macro (M1-M6 a esquerda, M7-M12 a direita)
    + 4 teclas de midia acima do numpad
  - coluna extra de 1u em cada lado, alinhada as 6 linhas
  - teclas largas reservam a largura real (Backspace 2u, Space 6.25u, ...)

Unidade: 1u = 19.05 mm (padrao Cherry MX / Keychron).

Estrutura fisica, da esquerda para a direita:
    [macro 1u] 0.25  [bloco principal 15u] 0.25  [nav 3u] 0.25
    [numpad 4u] 0.25  [macro 1u]
    => 25u de largura = 476.25 mm
"""

from __future__ import annotations

U = 19.05

Key = tuple[float, float, str]

GAP = 0.25
MAIN_W = 15.0
NAV_W = 3.0
NUMPAD_W = 4.0

X_MAIN = 1.0 + GAP
X_NAV = X_MAIN + MAIN_W + GAP
X_NUMPAD = X_NAV + NAV_W + GAP
X_RIGHT = X_NUMPAD + NUMPAD_W + GAP
WIDTH_U = X_RIGHT + 1.0


def _row_f() -> list[Key]:
    """F-row: Esc, F1-F12, PrtSc/ScrLk/Pause e 4 teclas de midia."""
    return [
        (1.0, 1.0, "Esc"),
        (1.0, 1.0, "F1"), (1.0, 1.0, "F2"), (1.0, 1.0, "F3"), (1.0, 1.0, "F4"),
        (1.0, 1.0, "F5"), (1.0, 1.0, "F6"), (1.0, 1.0, "F7"), (1.0, 1.0, "F8"),
        (1.0, 1.0, "F9"), (1.0, 1.0, "F10"), (1.0, 1.0, "F11"), (1.0, 1.0, "F12"),
        (1.0, 1.0, "PrtSc"), (1.0, 1.0, "ScrLk"), (1.0, 1.0, "Pause"),
        (1.0, 1.0, "Mute"), (1.0, 1.0, "Vol-"), (1.0, 1.0, "Vol+"), (1.0, 1.0, "Play"),
    ]


ROW_1: list[Key] = [
    (1.0, 1.0, "`"), (1.0, 1.0, "1"), (1.0, 1.0, "2"), (1.0, 1.0, "3"),
    (1.0, 1.0, "4"), (1.0, 1.0, "5"), (1.0, 1.0, "6"), (1.0, 1.0, "7"),
    (1.0, 1.0, "8"), (1.0, 1.0, "9"), (1.0, 1.0, "0"), (1.0, 1.0, "-"),
    (1.0, 1.0, "="), (2.0, 1.0, "Backspace"),
]

ROW_2: list[Key] = [
    (1.5, 1.0, "Tab"),
    (1.0, 1.0, "Q"), (1.0, 1.0, "W"), (1.0, 1.0, "E"), (1.0, 1.0, "R"),
    (1.0, 1.0, "T"), (1.0, 1.0, "Y"), (1.0, 1.0, "U"), (1.0, 1.0, "I"),
    (1.0, 1.0, "O"), (1.0, 1.0, "P"), (1.0, 1.0, "["), (1.0, 1.0, "]"),
    (1.5, 1.0, "\\"),
]

ROW_3: list[Key] = [
    (1.75, 1.0, "Caps"),
    (1.0, 1.0, "A"), (1.0, 1.0, "S"), (1.0, 1.0, "D"), (1.0, 1.0, "F"),
    (1.0, 1.0, "G"), (1.0, 1.0, "H"), (1.0, 1.0, "J"), (1.0, 1.0, "K"),
    (1.0, 1.0, "L"), (1.0, 1.0, ";"), (1.0, 1.0, "'"), (2.25, 1.0, "Enter"),
]

ROW_4: list[Key] = [
    (2.25, 1.0, "LShift"),
    (1.0, 1.0, "Z"), (1.0, 1.0, "X"), (1.0, 1.0, "C"), (1.0, 1.0, "V"),
    (1.0, 1.0, "B"), (1.0, 1.0, "N"), (1.0, 1.0, "M"),
    (1.0, 1.0, ","), (1.0, 1.0, "."), (1.0, 1.0, "/"),
    (2.75, 1.0, "RShift"),
]

ROW_5: list[Key] = [
    (1.25, 1.0, "LCtrl"), (1.25, 1.0, "LWin"), (1.25, 1.0, "LAlt"),
    (6.25, 1.0, "Space"),
    (1.25, 1.0, "RAlt"), (1.25, 1.0, "RWin"), (1.25, 1.0, "Menu"),
    (1.25, 1.0, "RCtrl"),
]

NAV_1: list[Key] = [(1.0, 1.0, "Ins"), (1.0, 1.0, "Home"), (1.0, 1.0, "PgUp")]
NAV_2: list[Key] = [(1.0, 1.0, "Del"), (1.0, 1.0, "End"), (1.0, 1.0, "PgDn")]
NAV_4: list[Key] = [(1.0, 1.0, "Up")]
NAV_5: list[Key] = [(1.0, 1.0, "Left"), (1.0, 1.0, "Down"), (1.0, 1.0, "Right")]

PAD_1: list[Key] = [(1.0, 1.0, "NumLock"), (1.0, 1.0, "/"),
                   (1.0, 1.0, "*"), (1.0, 1.0, "-")]
PAD_2: list[Key] = [(1.0, 1.0, "7"), (1.0, 1.0, "8"), (1.0, 1.0, "9"),
                   (1.0, 1.0, "+")]
PAD_3: list[Key] = [(1.0, 1.0, "4"), (1.0, 1.0, "5"), (1.0, 1.0, "6")]
PAD_4: list[Key] = [(1.0, 1.0, "1"), (1.0, 1.0, "2"), (1.0, 1.0, "3"),
                   (1.0, 1.0, "Enter")]
PAD_5: list[Key] = [(2.0, 1.0, "0"), (1.0, 1.0, ".")]

F_ROW = _row_f()

MAIN_ROWS = [F_ROW, ROW_1, ROW_2, ROW_3, ROW_4, ROW_5]
NAV_ROWS = [[], NAV_1, NAV_2, [], NAV_4, NAV_5]
PAD_ROWS = [[], PAD_1, PAD_2, PAD_3, PAD_4, PAD_5]

MACRO_LEFT = ["M1", "M2", "M3", "M4", "M5", "M6"]
MACRO_RIGHT = ["M7", "M8", "M9", "M10", "M11", "M12"]

ROW_PITCH_U = 1.0
ROW_GAP_AFTER_F_U = 0.5


def _emit(row_idx: int, y_u: float) -> list[dict]:
    items: list[tuple[float, float, float, str, str]] = []
    items.append((0.0, 1.0, 1.0, MACRO_LEFT[row_idx], "macro"))

    x = X_MAIN
    for w, h, legend in MAIN_ROWS[row_idx]:
        items.append((x, w, h, legend, "main"))
        x += w

    x = X_NAV
    for w, h, legend in NAV_ROWS[row_idx]:
        items.append((x, w, h, legend, "nav"))
        x += w

    x = X_NUMPAD
    for w, h, legend in PAD_ROWS[row_idx]:
        items.append((x, w, h, legend, "numpad"))
        x += w

    items.append((X_RIGHT, 1.0, 1.0, MACRO_RIGHT[row_idx], "macro"))

    out = []
    for x_u, w_u, h_u, legend, group in items:
        out.append({
            "x_mm": (x_u + w_u / 2.0) * U,
            "y_mm": (y_u + h_u / 2.0) * U,
            "width_mm": w_u * U,
            "height_mm": h_u * U,
            "legend": legend,
            "group": group,
            "row_phys": row_idx,
        })
    return out


def positions() -> list[dict]:
    """Todas as teclas fisicas, em ordem de leitura, com slot na matriz."""
    raw: list[dict] = []
    y_u = 0.0
    for ri in range(6):
        raw.extend(_emit(ri, y_u))
        y_u += ROW_PITCH_U + (ROW_GAP_AFTER_F_U if ri == 0 else 0.0)

    per_row: dict[int, int] = {}
    for k, item in enumerate(raw):
        r = item["row_phys"]
        c = per_row.get(r, 0)
        per_row[r] = c + 1
        item["idx"] = k
        item["col"] = c
        item["row"] = r

    return raw


def board_size() -> tuple[float, float]:
    keys = positions()
    return WIDTH_U * U, max(k["y_mm"] + k["height_mm"] / 2.0 for k in keys)


if __name__ == "__main__":
    keys = positions()
    w, h = board_size()
    per_row: dict[int, int] = {}
    for k in keys:
        per_row[k["row"]] = per_row.get(k["row"], 0) + 1
    print(f"teclas   : {len(keys)}")
    print(f"matriz   : 6x23 = {6 * 23} posicoes, {6 * 23 - len(keys)} livres")
    for r in range(6):
        used = per_row.get(r, 0)
        print(f"  linha {r}: {used:2d} teclas  (colunas {used})")
    print(f"placa    : {w:.2f} x {h:.2f} mm")
    overflow = [r for r, n in per_row.items() if n > 23]
    assert not overflow, f"linha excede 23 colunas: {overflow}"
    assert len(keys) == 120, len(keys)

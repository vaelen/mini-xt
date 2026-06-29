"""Generate hardware/mini-xt.kicad_sym with the project's custom symbols:

  - V20         : NEC uPD70108, copied from the stock 8088_Min_Mode symbol
                  (pin-compatible) and relabelled. The signature vintage part.
  - MAX3241     : RS-232 transceiver, 3 drivers + 5 receivers (authored).
  - DS12C887    : RTC/CMOS with integral battery+crystal (authored).

Pin numbers for the two authored parts are best-effort from the datasheets and
flagged in notes/open-questions.md for review.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from mxsch import dump, Sym, parse_sexp_typed

SYMDIR = "/snap/kicad/22/usr/share/kicad/symbols"
HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = 2.54
PINLEN = 3.81


def _eff(hide=False, *justify):
    e = ["effects", ["font", ["size", 1.27, 1.27]]]
    if justify:
        e.append(["justify"] + [Sym(j) for j in justify])
    if hide:
        e.append(["hide", Sym("yes")])
    return e


def _prop(name, val, at, hide=False):
    n = ["property", name, val, ["at", at[0], at[1], at[2] if len(at) > 2 else 0]]
    e = ["effects", ["font", ["size", 1.27, 1.27]]]
    if hide:
        e.append(["hide", Sym("yes")])
    n.append(e)
    return n


def make_ic(name, left, right, top=None, bottom=None, ref="U",
            description="", datasheet="", footprint=""):
    """left/right/top/bottom: list of (number, pinname, etype). Returns typed node."""
    top = top or []
    bottom = bottom or []
    nrows = max(len(left), len(right))
    height = (nrows + 1) * GRID
    # body half-width from longest side-pin name
    longest = max([len(p[1]) for p in left + right] + [4])
    # body half-width as a clean multiple of GRID so pins land on the 1.27 grid
    halfw = max(4, round((longest * 1.4 + 8) / 2.0 / 2.54)) * GRID
    top_y = (nrows - 1) * GRID / 2.0

    unit_graphic = ["symbol", name + "_0_1",
                    ["rectangle", ["start", -halfw, top_y + GRID],
                     ["end", halfw, top_y - (nrows) * GRID],
                     ["stroke", ["width", 0.254], ["type", Sym("default")]],
                     ["fill", ["type", Sym("background")]]]]
    unit_pins = ["symbol", name + "_1_1"]

    def addpin(num, pnm, etype, x, y, ang):
        unit_pins.append(["pin", Sym(etype), Sym("line"),
                          ["at", x, y, ang], ["length", PINLEN],
                          ["name", pnm, _eff()],
                          ["number", str(num), _eff()]])

    for i, (num, pnm, et) in enumerate(left):
        y = top_y - i * GRID
        addpin(num, pnm, et, -halfw - PINLEN, y, 0)
    for i, (num, pnm, et) in enumerate(right):
        y = top_y - i * GRID
        addpin(num, pnm, et, halfw + PINLEN, y, 180)
    # top/bottom along width
    for i, (num, pnm, et) in enumerate(top):
        x = (i - (len(top) - 1) / 2.0) * GRID
        addpin(num, pnm, et, x, top_y + GRID + PINLEN, 270)
    for i, (num, pnm, et) in enumerate(bottom):
        x = (i - (len(bottom) - 1) / 2.0) * GRID
        addpin(num, pnm, et, x, top_y - nrows * GRID - PINLEN, 90)

    node = ["symbol", name,
            ["pin_names", ["offset", 1.016]],
            ["exclude_from_sim", Sym("no")],
            ["in_bom", Sym("yes")], ["on_board", Sym("yes")],
            _prop("Reference", ref, (-halfw, top_y + GRID + 2.54)),
            _prop("Value", name, (-halfw, top_y + GRID + 5.08)),
            _prop("Footprint", footprint, (0, 0), hide=True),
            _prop("Datasheet", datasheet or "~", (0, 0), hide=True),
            _prop("Description", description, (0, 0), hide=True),
            unit_graphic, unit_pins,
            ["embedded_fonts", Sym("no")]]
    return node


def copy_symbol(srcpath, srcname, newname, value=None, description=None):
    root = parse_sexp_typed(open(srcpath).read())
    for node in root[1:]:
        if isinstance(node, list) and node[0] == Sym("symbol") and node[1] == srcname:
            node = [x for x in node]  # shallow copy top list
            node[1] = newname
            # rename nested unit symbols srcname_x_y -> newname_x_y
            for j, ch in enumerate(node):
                if isinstance(ch, list) and ch and ch[0] == Sym("symbol"):
                    ch[1] = newname + ch[1][len(srcname):]
                if isinstance(ch, list) and ch[0] == Sym("property"):
                    if ch[1] == "Value" and value:
                        ch[2] = value
                    if ch[1] == "Description" and description:
                        ch[2] = description
            return node
    raise SystemExit("symbol %s not found in %s" % (srcname, srcpath))


# ---- V20: copy the base 8088 symbol (full graphics+pins; min-mode pinout) ----
# (8088_Min_Mode only `extends` 8088 with label overrides, so copy the base.)
v20 = copy_symbol(SYMDIR + "/MCU_Intel.kicad_sym", "8088", "V20",
                  value="V20",
                  description="NEC uPD70108 (V20), 8088-compatible CPU, min mode")

# ---- MAX3241: 3 drivers (T1..T3) + 5 receivers (R1..R5) + charge pump ----
# Pin numbers per MAX3241E 28-pin (SSOP); flagged for datasheet review.
max3241 = make_ic(
    "MAX3241",
    left=[
        ("13", "T1IN", "input"), ("14", "T2IN", "input"), ("15", "T3IN", "input"),
        ("9",  "R1OUT", "output"), ("12", "R2OUT", "output"), ("23", "R3OUT", "output"),
        ("24", "R4OUT", "output"), ("25", "R5OUT", "output"),
        ("8",  "~{FORCEOFF}", "input"), ("21", "~{FORCEON}", "input"),
        ("20", "~{INVALID}", "output"),
    ],
    right=[
        ("16", "T1OUT", "output"), ("17", "T2OUT", "output"), ("18", "T3OUT", "output"),
        ("10", "R1IN", "input"), ("11", "R2IN", "input"), ("26", "R3IN", "input"),
        ("27", "R4IN", "input"), ("28", "R5IN", "input"),
    ],
    top=[("4", "VCC", "power_in"), ("2", "V+", "passive"), ("3", "C1+", "passive"),
         ("1", "C2+", "passive")],
    bottom=[("19", "GND", "power_in"), ("7", "V-", "passive"), ("5", "C1-", "passive"),
            ("6", "C2-", "passive")],
    description="RS-232 transceiver, 3 drivers / 5 receivers, charge pump (full DB9)",
    datasheet="https://www.analog.com/media/en/technical-documentation/data-sheets/MAX3222-MAX3241.pdf")

# ---- DS12C887: RTC/CMOS, MC146818-compatible, integral battery+crystal (24-pin) ----
ds12c887 = make_ic(
    "DS12C887",
    left=[
        ("4", "AD0", "bidirectional"), ("5", "AD1", "bidirectional"),
        ("6", "AD2", "bidirectional"), ("7", "AD3", "bidirectional"),
        ("8", "AD4", "bidirectional"), ("9", "AD5", "bidirectional"),
        ("10", "AD6", "bidirectional"), ("11", "AD7", "bidirectional"),
    ],
    right=[
        ("14", "AS", "input"), ("16", "DS", "input"), ("15", "R/~{W}", "input"),
        ("13", "~{CS}", "input"), ("17", "~{RESET}", "input"),
        ("18", "~{IRQ}", "output"), ("21", "SQW", "output"), ("1", "MOT", "input"),
    ],
    top=[("24", "VCC", "power_in")],
    bottom=[("12", "GND", "power_in")],
    description="RTC + 113B NVRAM, MC146818-compatible, integral battery and crystal",
    datasheet="https://www.analog.com/media/en/technical-documentation/data-sheets/DS12885-DS12C887A.pdf")

# ---- flat single-body versions of multi-unit glue chips ----
# (clearer for an architecture schematic; connectivity is by pin number).
from mxsch import SymbolLib  # noqa: E402

_glue_lib = SymbolLib()
for _l in ["74xx", "4xxx", "Amplifier_Operational"]:
    _glue_lib.load(SYMDIR + "/%s.kicad_sym" % _l, _l)


def flatten(srclibid, newname, description=""):
    sd = _glue_lib.get(srclibid)
    seen = {}
    for p in sd.pins:                      # dedup by pin number (multi-unit repeats)
        if p.number not in seen:
            seen[p.number] = p
    pins = list(seen.values())
    top, bottom, left, right = [], [], [], []
    body = []
    for p in pins:
        nm = p.name if p.name not in ("~", "") else ("P" + p.number)
        ent = (p.number, nm, p.etype)
        up = p.name.upper()
        if p.etype.startswith("power") or up in ("VCC", "VDD", "GND", "VSS", "V+"):
            if up in ("GND", "VSS", "V-"):
                bottom.append(ent)
            else:
                top.append(ent)
        elif p.etype == "output":
            right.append(ent)
        elif p.etype in ("input",):
            left.append(ent)
        else:
            body.append(ent)               # bidir/passive/tri_state -> balance later
    # balance the bidirectional/passive pins across the shorter side
    for ent in body:
        (left if len(left) <= len(right) else right).append(ent)
    name = newname
    return make_ic(name, left, right, top=top, bottom=bottom, ref="U",
                   description=description)


# Standardized on 74HCT (TTL input thresholds) for all 5 V glue -- the board has
# many 3.3 V<->5 V crossings, and HCT reliably reads a 3.3 V high (Vih=2.0 V)
# where 74HC (Vih~3.5 V) would be marginal. The 4017 (no HCT variant) is replaced
# by a 74HCT163 preset-to-divide-by-3. Level shifters stay 74LVC245A.
GLUE = [
    ("74xx:74LS573", "74HCT573", "Octal transparent latch (address latch)"),
    ("74xx:74HC245", "74HCT245", "Octal bus transceiver"),
    ("74xx:74HC245", "74LVC245A", "Octal level-shift transceiver (3.3V<->5V)"),
    ("74xx:74HCT138", "74HCT138", "3-to-8 line decoder"),
    ("74xx:74HC00", "74HCT00", "Quad 2-input NAND"),
    ("74xx:74HC74", "74HCT74", "Dual D flip-flop"),
    ("74xx:74LS157", "74HCT157", "Quad 2-to-1 mux (clock select)"),
    ("74xx:74HC04", "74HCT04", "Hex inverter (clock buffer)"),
    ("74xx:74HC374", "74HCT374", "Octal D flip-flop (LPT data latch)"),
    ("74xx:74HC244", "74HCT244", "Octal buffer (LPT status/control)"),
    ("74xx:74HC165", "74HCT165", "8-bit PISO shift register (IRQ collector)"),
    ("74xx:74LS163", "74HCT163", "4-bit binary counter (bus-master addr / div-by-3)"),
    ("74xx:74LS32", "74HCT32", "Quad 2-input OR"),
    ("74xx:74LS08", "74HCT08", "Quad 2-input AND"),
    ("74xx:74HC02", "74HCT02", "Quad 2-input NOR"),
    ("74xx:74LS125", "74HCT125", "Quad bus buffer, 3-state"),
    ("Amplifier_Operational:TL072", "TL072", "Dual JFET op-amp (audio summer)"),
]
glue_syms = []
for src, new, desc in GLUE:
    try:
        glue_syms.append(flatten(src, new, desc))
    except Exception as e:
        print("  (skip glue %s: %s)" % (new, e))

lib = ["kicad_symbol_lib", ["version", 20241209], ["generator", "mxsch"],
       ["generator_version", "9.0"], v20, max3241, ds12c887] + glue_syms

out = os.path.join(HW, "mini-xt.kicad_sym")
open(out, "w").write(dump(lib) + "\n")
print("wrote", out)

"""Generate hardware/mini-xt.kicad_sym with the project's custom symbols:

  - V20         : NEC uPD70108, copied from the stock 8088_Min_Mode symbol
                  (pin-compatible) and relabelled. The signature vintage part.
  - MAX3241     : RS-232 transceiver, 3 drivers + 5 receivers (authored).

Pin numbers for MAX3241 were VERIFIED against JLCPCB/EasyEDA symbol data on
2026-07-03 (MAX3241EEAI+T = LCSC C406859): the original best-effort numbering
was wrong on almost every pin (and used MAX3243-style FORCEON/FORCEOFF names
-- the real MAX3241 has SHDN#/EN# plus two always-on receiver outputs). See
notes/jlcpcb-sourcing.md.

DS12C887 (RTC) was authored here too, but the 3.3V single-board redesign
deleted it in favor of an emulated RTC (PCF8563 + Bus-MCU 0x70/71 emulation,
see docs/superpowers/specs/2026-07-14-3v3-single-board-design.md) -- removed
2026-07-14, no sheet ever placed it again after that point.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from mxsch import dump, Sym, parse_sexp_typed

SYMDIR = __import__("mxsch").kicad_symdir()
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
# Pin numbers/names per the real MAX3241E SSOP-28 (verified vs LCSC C406859):
# SHDN# (22) active-low shutdown, EN# (23) active-low receiver-output enable,
# R1OUTB/R2OUTB (21/20) always-active complementary receiver outputs (wake-up).
max3241 = make_ic(
    "MAX3241",
    left=[
        ("14", "T1IN", "input"), ("13", "T2IN", "input"), ("12", "T3IN", "input"),
        ("19", "R1OUT", "output"), ("18", "R2OUT", "output"), ("17", "R3OUT", "output"),
        ("16", "R4OUT", "output"), ("15", "R5OUT", "output"),
        ("21", "R1OUTB", "output"), ("20", "R2OUTB", "output"),
        ("22", "~{SHDN}", "input"), ("23", "~{EN}", "input"),
    ],
    right=[
        ("9", "T1OUT", "output"), ("10", "T2OUT", "output"), ("11", "T3OUT", "output"),
        ("4", "R1IN", "input"), ("5", "R2IN", "input"), ("6", "R3IN", "input"),
        ("7", "R4IN", "input"), ("8", "R5IN", "input"),
    ],
    top=[("26", "VCC", "power_in"), ("27", "V+", "passive"), ("28", "C1+", "passive"),
         ("1", "C2+", "passive")],
    bottom=[("25", "GND", "power_in"), ("3", "V-", "passive"), ("24", "C1-", "passive"),
            ("2", "C2-", "passive")],
    description="RS-232 transceiver, 3 drivers / 5 receivers, charge pump (full DB9). MAX3241EEAI SSOP-28",
    datasheet="https://www.analog.com/media/en/technical-documentation/data-sheets/MAX3222-MAX3241.pdf")

# ---- IS62WV51216BLL: 512Kx16 async SRAM, TSOP-II-44 (3.3V bus redesign) ----
# Pins VERIFIED against jlc_get_pinout for LCSC C11315 (IS62WV51216BLL-55TLI) on
# 2026-07-14, cross-checked against the ISSI 62WV51216ALL.pdf pin-configuration
# diagram (44-pin TSOP-II) -- both agree exactly. The 44-pin package brings out
# only CS1# (named ~{CE} here); CS2 is a 48-pin-BGA-only pin, tied active
# internally, not present on this package.
is62wv51216 = make_ic(
    "IS62WV51216",
    left=[(str(n), "A%d" % a, "input") for n, a in [
        (5, 0), (4, 1), (3, 2), (2, 3), (1, 4), (44, 5), (43, 6), (42, 7),
        (27, 8), (26, 9), (25, 10), (24, 11), (22, 12), (21, 13), (20, 14),
        (19, 15), (18, 16), (23, 17), (28, 18)]],
    right=[(str(n), "IO%d" % i, "bidirectional") for n, i in [
        (7, 0), (8, 1), (9, 2), (10, 3), (13, 4), (14, 5), (15, 6), (16, 7),
        (29, 8), (30, 9), (31, 10), (32, 11), (35, 12), (36, 13), (37, 14),
        (38, 15)]] + [
        ("6", "~{CE}", "input"), ("41", "~{OE}", "input"), ("17", "~{WE}", "input"),
        ("39", "~{LB}", "input"), ("40", "~{UB}", "input"),
    ],
    top=[("11", "VDD", "power_in"), ("33", "VDD", "power_in")],
    bottom=[("12", "GND", "power_in"), ("34", "GND", "power_in")],
    description="IS62WV51216BLL 512Kx16 async SRAM, TSOP-II-44, 2.5-3.6V. Pins verified vs LCSC C11315 + ISSI datasheet 2026-07-14.",
    datasheet="https://www.issi.com/WW/pdf/62WV51216ALL.pdf")

# ---- TL16C550PT: TL16C550C UART, LQFP-48 (PT package) (3.3V bus redesign) ----
# Pin numbers are the NO.PT column of TI SLLS177I Table 4-1 -- DISTINCT from the
# DIP-40/PLCC-44 numbering the existing mini-xt:16550 symbol uses (do not reuse
# those numbers). Verified against jlc_get_pinout for LCSC C181382
# (TL16C550CPTR) on 2026-07-14 -- both sources agree exactly, pin for pin.
tl16c550pt = make_ic(
    "TL16C550PT",
    left=[
        ("43", "D0", "bidirectional"), ("44", "D1", "bidirectional"),
        ("45", "D2", "bidirectional"), ("46", "D3", "bidirectional"),
        ("47", "D4", "bidirectional"), ("2", "D5", "bidirectional"),
        ("3", "D6", "bidirectional"), ("4", "D7", "bidirectional"),
        ("28", "A0", "input"), ("27", "A1", "input"), ("26", "A2", "input"),
        ("24", "~{ADS}", "input"),
        ("9", "CS0", "input"), ("10", "CS1", "input"), ("11", "~{CS2}", "input"),
        ("19", "~{RD1}", "input"), ("20", "RD2", "input"),
        ("16", "~{WR1}", "input"), ("17", "WR2", "input"),
    ],
    right=[
        ("7", "SIN", "input"), ("8", "SOUT", "output"),
        ("5", "RCLK", "input"), ("12", "~{BAUDOUT}", "output"),
        ("14", "XIN", "bidirectional"), ("15", "XOUT", "bidirectional"),
        ("22", "DDIS", "output"), ("23", "~{TXRDY}", "output"),
        ("29", "~{RXRDY}", "output"), ("30", "INTRPT", "output"),
        ("35", "MR", "input"),
        ("34", "~{OUT1}", "output"), ("31", "~{OUT2}", "output"),
        ("32", "~{RTS}", "output"), ("33", "~{DTR}", "output"),
        ("38", "~{CTS}", "input"), ("39", "~{DSR}", "input"),
        ("40", "~{DCD}", "input"), ("41", "~{RI}", "input"),
    ],
    top=[("42", "VCC", "power_in")],
    bottom=[("18", "VSS", "power_in")] + [
        (str(n), "NC", "no_connect") for n in (1, 6, 13, 21, 25, 36, 37, 48)],
    description="TL16C550C UART, LQFP-48 (PT). Pins = TI SLLS177I Table 4-1 NO.PT column, verified vs LCSC C181382 2026-07-14.",
    datasheet="https://www.ti.com/lit/ds/symlink/tl16c550c.pdf")

# ---- PCF8563: I2C RTC, SO-8 (3.3V bus redesign -- replaces DS12C887) ----
# jlc_get_pinout for LCSC C7440 mis-numbers this part (reports OSCI as pin "9"
# on an 8-pin package, and omits pin 1 entirely -- an EasyEDA data bug). Pin
# numbers below are instead taken directly from the NXP PCF8563 datasheet
# ("7.2 Pin description" Table 3, SO8/TSSOP8 column), fetched via the Wayback
# Machine mirror on 2026-07-14 after nxp.com 404'd: OSCI=1, OSCO=2, INT#=3,
# VSS=4, SDA=5, SCL=6, CLKOUT=7, VDD=8.
pcf8563 = make_ic(
    "PCF8563",
    left=[
        ("1", "OSCI", "input"), ("2", "OSCO", "output"),
        ("3", "~{INT}", "open_collector"), ("5", "SDA", "bidirectional"),
    ],
    right=[("6", "SCL", "input"), ("7", "CLKOUT", "open_collector")],
    top=[("8", "VDD", "power_in")],
    bottom=[("4", "VSS", "power_in")],
    description="PCF8563T I2C RTC, SO-8. Pins verified vs NXP datasheet (Wayback mirror) 2026-07-14 -- jlc_get_pinout mis-numbered this part.",
    datasheet="https://www.nxp.com/docs/en/data-sheet/PCF8563.pdf")

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
    ("74xx:74HCT574", "74HCT574", "Octal D flip-flop, 3-state (LPT latches; '374 not stocked at JLC)"),
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

# ---- Waveshare Core2350B RP2350B module (double-ring 2.54mm PGA) ----
# Physical (verified from module photos, hardware/Core2350B0-details-*.jpg):
# 25.4 x 25.4 mm, TWO concentric rings of through-holes on a 2.54 mm grid
# (22.86 mm inner span), NO castellated edges -- must mount on female
# headers/sockets, cannot be reflowed as an SMD part. Holes are silk-labelled
# by SIGNAL NAME (GP0..GP47, VB, 3V, BS, ...) with no canonical 1..64
# numbering, so the pin NUMBERS below are project-defined: the layout
# footprint must be authored with the SAME numbers as this symbol. The
# module has ~6 GND holes; this symbol models 2 (tie all at the footprint).
# Exposes all 48 GPIO + VBUS / 3V3 (onboard ME6217C33 LDO out) / 3V3_EN /
# ADC_VREF / RUN / SWCLK / SWDIO / USB_DP / USB_DM / BOOTSEL / GND.  Onboard:
# W25Q128 16MB flash, optional 0/2/8MB QSPI PSRAM (CS=GPIO47), user LED on
# GPIO39 (GPIO39 still usable). HSTX = GP12-19 (photos confirm the design's
# HDMI and PSRAM-CS assignments).
core2350b = make_ic(
    "Core2350B",
    left=[(str(i + 1), "GPIO%d" % i, "bidirectional") for i in range(24)],
    right=[(str(i + 25), "GPIO%d" % (i + 24), "bidirectional") for i in range(24)],
    top=[("49", "VBUS", "power_in"), ("50", "3V3", "power_out"),
         ("51", "3V3_EN", "input"), ("52", "ADC_VREF", "passive")],
    bottom=[("59", "GND", "power_in"), ("60", "GND", "power_in"),
            ("53", "RUN", "input"), ("54", "SWCLK", "input"),
            ("55", "SWDIO", "bidirectional"), ("56", "USB_DP", "bidirectional"),
            ("57", "USB_DM", "bidirectional"), ("58", "BOOTSEL", "input")],
    ref="M",
    description="Waveshare Core2350B: RP2350B module, 48 GPIO, 16MB flash, opt PSRAM (CS=GPIO47), 3V3 LDO, LED on GPIO39",
    datasheet="https://www.waveshare.com/wiki/Core2350B0")

# ---- Raspberry Pi Pico module (RP2040; Pico 2/RP2350A pin-compatible) ----
# Standard 40-pin castellated module. Exposes 26 usable GPIO (GP0-GP22, GP26-28;
# GP23/24/25 are module-internal) + power/control. GPIO NAMES are authoritative;
# pin NUMBERS follow the physical 40-pin Pico pinout (GND pins collapsed to two).
pico = make_ic(
    "Pico",
    left=[(str(n), "GP%d" % g, "bidirectional") for n, g in [
        (1, 0), (2, 1), (4, 2), (5, 3), (6, 4), (7, 5), (9, 6),
        (10, 7), (11, 8), (12, 9), (14, 10), (15, 11), (16, 12)]],
    right=[(str(n), "GP%d" % g, "bidirectional") for n, g in [
        (17, 13), (19, 14), (20, 15), (21, 16), (22, 17), (24, 18),
        (25, 19), (26, 20), (27, 21), (29, 22), (31, 26), (32, 27), (34, 28)]],
    top=[("40", "VBUS", "power_in"), ("39", "VSYS", "power_in"),
         ("37", "3V3_EN", "input")],
    bottom=[("3", "GND", "power_in"), ("38", "GND", "power_in"),
            ("36", "3V3", "power_out"), ("30", "RUN", "input"),
            ("35", "ADC_VREF", "passive")],
    ref="M",
    description="Raspberry Pi Pico module (RP2040; Pico 2/RP2350A pin-compatible): 26 usable GPIO, onboard 3V3 SMPS, USB",
    datasheet="https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf")

# ---- audio/support parts added for the audio card + storage PSRAM ----
# Pin numbers below were VERIFIED against the official PicoGUS chip-down
# KiCad netlist (picogus/hw-chipdown/chipdown.net) on 2026-07-11, whose
# pinfunctions come from the real vendor symbols (cross-checked via its
# `nets`/`node` entries, not just the `libparts` table, for CB3T3245 since
# that netlist reuses a generic 74HC244 libsource for it).

# ---- CB3T3257: SN74CB3T3257 quad 2:1 FET bus switch (TSSOP-16) ----
cb3t3257 = make_ic(
    "CB3T3257",
    left=[
        ("4", "1A", "passive"), ("7", "2A", "passive"),
        ("9", "3A", "passive"), ("12", "4A", "passive"),
        ("1", "S", "input"), ("15", "~{OE}", "input"),
    ],
    right=[
        ("2", "1B1", "passive"), ("3", "1B2", "passive"),
        ("5", "2B1", "passive"), ("6", "2B2", "passive"),
        ("11", "3B1", "passive"), ("10", "3B2", "passive"),
        ("14", "4B1", "passive"), ("13", "4B2", "passive"),
    ],
    top=[("16", "VCC", "power_in")],
    bottom=[("8", "GND", "power_in")],
    description="SN74CB3T3257 quad 2:1 FET bus switch, TSSOP-16",
    datasheet="https://www.ti.com/lit/ds/symlink/sn74cb3t3257.pdf")

# ---- CB3T3245: SN74CB3T3245 8-bit FET bus switch (TSSOP-20) ----
cb3t3245 = make_ic(
    "CB3T3245",
    left=[
        ("2", "1A0", "passive"), ("4", "1A1", "passive"),
        ("6", "1A2", "passive"), ("8", "1A3", "passive"),
        ("17", "2A0", "passive"), ("15", "2A1", "passive"),
        ("13", "2A2", "passive"), ("11", "2A3", "passive"),
        ("1", "1OE", "input"), ("19", "2OE", "input"),
    ],
    right=[
        ("18", "1Y0", "passive"), ("16", "1Y1", "passive"),
        ("14", "1Y2", "passive"), ("12", "1Y3", "passive"),
        ("3", "2Y0", "passive"), ("5", "2Y1", "passive"),
        ("7", "2Y2", "passive"), ("9", "2Y3", "passive"),
    ],
    top=[("20", "VCC", "power_in")],
    bottom=[("10", "GND", "power_in")],
    description="SN74CB3T3245 8-bit FET bus switch, TSSOP-20",
    datasheet="https://assets.nexperia.com/documents/data-sheet/74LVC_LVCH244A.pdf")

# ---- 74LVC2G06: dual open-drain inverter (SOT-23-6) ----
lvc2g06 = make_ic(
    "74LVC2G06",
    left=[("1", "1A", "input"), ("3", "2A", "input")],
    right=[("6", "1Y", "open_collector"), ("4", "2Y", "open_collector")],
    top=[("5", "VCC", "power_in")],
    bottom=[("2", "GND", "power_in")],
    description="Dual open-drain inverter, SOT-23-6",
    datasheet="http://www.ti.com/lit/sg/scyt129e/scyt129e.pdf")

# ---- PCM5102A: I2S stereo DAC (TSSOP-20; 5100A/5101A/5102A pin-identical) ----
pcm5102a = make_ic(
    "PCM5102A",
    left=[
        ("13", "BCK", "input"), ("14", "DIN", "input"), ("15", "LRCK", "input"),
        ("12", "SCK", "input"), ("16", "FMT", "input"), ("11", "FLT", "input"),
        ("10", "DEMP", "input"), ("17", "XSMT", "input"),
    ],
    right=[
        ("6", "OUTL", "output"), ("7", "OUTR", "output"),
        ("2", "CAPP", "passive"), ("4", "CAPM", "passive"),
        ("5", "VNEG", "passive"), ("18", "LDOO", "passive"),
    ],
    top=[("1", "CPVDD", "power_in"), ("20", "DVDD", "power_in"),
         ("8", "AVDD", "power_in")],
    bottom=[("3", "CPGND", "power_in"), ("19", "DGND", "power_in"),
            ("9", "AGND", "power_in")],
    description="PCM5102A I2S stereo DAC, TSSOP-20 (PCM5100A/5101A/5102A pin-identical)",
    datasheet="https://www.ti.com/lit/ds/symlink/pcm5102a.pdf")

# ---- M62429: I2C-ish 2-channel volume control (SOP-8, M62429L 3-5.5V grade) ----
m62429 = make_ic(
    "M62429",
    left=[("1", "1ch_IN", "input"), ("8", "2ch_IN", "input"),
          ("4", "DATA", "input"), ("5", "CLK", "input")],
    right=[("2", "1ch_OUT", "output"), ("7", "2ch_OUT", "output")],
    top=[("6", "Vcc", "power_in")],
    bottom=[("3", "GND", "power_in")],
    ref="U",
    description="M62429L 2-channel electronic volume control, SOP-8",
    datasheet="https://www.mitsubishielectric.com/semiconductors/php/psearch2.php?FOLDER_ID=1495")

# ---- APS6404L: 64Mbit QSPI PSRAM (SOP-8) ----
aps6404l = make_ic(
    "APS6404L",
    left=[("1", "~{CE}", "input"), ("6", "SCLK", "input")],
    right=[("2", "SO/SIO1", "bidirectional"), ("5", "SI/SIO0", "bidirectional"),
           ("3", "SIO2", "bidirectional"), ("7", "SIO3", "bidirectional")],
    top=[("8", "VCC", "power_in")],
    bottom=[("4", "VSS", "power_in")],
    description="APS6404L 64Mbit QSPI PSRAM, SOP-8",
    datasheet="https://www.espressif.com/sites/default/files/documentation/esp-psram32_datasheet_en.pdf")

# (RTL8019AS / AT93C46 / 13F-39MNL / RJ45_LED symbols removed with the
# network sheet 2026-07-14 -- tag full-board-with-nic has them.)

lib = ["kicad_symbol_lib", ["version", 20241209], ["generator", "mxsch"],
       ["generator_version", "9.0"], v20, max3241, core2350b, pico,
       cb3t3257, cb3t3245, lvc2g06, pcm5102a, m62429, aps6404l,
       is62wv51216, tl16c550pt, pcf8563] + glue_syms

out = os.path.join(HW, "mini-xt.kicad_sym")
open(out, "w").write(dump(lib) + "\n")
print("wrote", out)

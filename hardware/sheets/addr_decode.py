"""Central I/O address decode + IRQ mapping + peripheral disable jumpers.

Added 2026-07-14 (chip-count reduction), extended the same day: this sheet
now owns ALL the discrete peripherals' bus-interface plumbing --

  1. ADDRESS DECODE: one '138 + shared fine term hands each peripheral an
     active-low chip select (~{COM1_CS} / ~{COM2_CS} / ~{LPT_CS} / ~{IDE_CS},
     `mxbus.PRIV_CS`). 3 chips here replaced the 6 the sheets carried. This
     is shared logic factored out, not an isolation break: to lift a block
     onto a standalone ISA card, its wrapper schematic re-adds the decode
     alongside the bus headers, exactly like it adds the edge connector.
  2. IRQ MAPPING: the peripherals export IRQ *requests* on private nets
     (`mxbus.PRIV_IRQREQ`); ONE shared 74LVC125A here drives the real ISA
     lines (IRQ4/IRQ3/IRQ7/IRQ14), replacing the three per-sheet '125s.
     COM channels keep the PC convention: in = IRQ_COMx (raw INTRPT),
     ~OE = ~{COMx_IRQEN} (the UART's ~{OUT2} -- software masks by clearing
     OUT2, tri-stating the line). LPT/IDE channels strap the input high and
     pulse on their active-low requests, same as their old local stages.
  3. DISABLE JUMPERS (JP3-JP6, one per peripheral): peripherals are ENABLED
     by default; fitting a jumper pulls DIS_x high and a second 74HC32
     forces that ~CS inactive -- the peripheral never decodes, its IRQ
     request never fires (same causality as the old on-sheet enables: COM
     MCR resets to 0, LPT's idle-high ~Ack keeps its request off, IDE's
     INTRQ pulldown keeps Q1 off), and an expansion-port card can take over
     the address. NOTE the sense is INVERTED vs the old per-sheet jumpers
     (those needed a jumper fitted to enable / to select a base address).

How the map folds onto one '138 (all targets sit in 0x200-0x3FF, A9=1):
  select C,B,A = A8,A7,A6 -> 64-byte windows; AEN gates via ~E0.
    ~Y7  0x3C0-0x3FF   COM1 window
    ~Y3  0x2C0-0x2FF   COM2 window
    ~Y5  0x340-0x37F   LPT 0x378 window
    ~Y1  0x240-0x27F   LPT 0x278 window (JP1 alternate)
    ~Y4  0x300-0x33F   IDE window
  COM1/COM2/LPT all need offset 0x38-0x3F inside their window -- ONE shared
  fine term Q = A5&A4&A3 (74HC00: two NANDs build ~Q, one spare inverts A5).
  U3 ('32) ORs each window with ~Q (COM1/COM2/LPT) or the A5 strap (IDE);
  U4 ('32) ORs in the disable jumpers:
    ~{COM1_CS} = ~Y7 | ~Q | DIS_COM1          -> 0x3F8-0x3FF
    ~{COM2_CS} = ~Y3 | ~Q | DIS_COM2          -> 0x2F8-0x2FF
    ~{LPT_CS}  = (JP1: ~Y5/~Y1) | ~Q | DIS_LPT   -> 0x378 or 0x278
    ~{IDE_CS}  = ~Y4 | (JP2: A5/~A5) | DIS_IDE   -> 0x300 or 0x320 (+0x1F)
  (the A4 split inside the IDE window stays on the storage sheet, as before).

Straps: JP1 LPT base 0x378/0x278, JP2 IDE base 0x300/0x320. Strap commons
are pulled HIGH, so an unjumpered base strap also parks that peripheral
disabled instead of floating its decode.
"""
import mxbus
from mxbus import pin

NAME = "addr_decode"
TITLE = "Central I/O decode + IRQ map + disable jumpers"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[3:10]] +   # A3..A9 (block decode only)
    [pin("AEN", "input")] +                         # not a DMA cycle
    [pin(s, "output") for s in mxbus.PRIV_CS] +     # one chip select per peripheral
    [pin(s, "input") for s in mxbus.PRIV_IRQREQ] +  # peripheral IRQ requests
    [pin("IRQ4", "output"),      # COM1 (hardwired PC convention)
     pin("IRQ3", "output"),      # COM2
     pin("IRQ7", "output"),      # LPT1
     pin("IRQ14", "output")]     # XT-IDE (AT primary-IDE convention)
)


def build(sch, lib, expose=True):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    if expose:
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ---------------- U1: coarse 64-byte-window decode ----------------
    # 74HC138 value override (as everywhere since spec 2026-07-14): all
    # inputs are 3.3V-driven address/AEN lines; 74HCT is out of spec at 3.3V.
    U1 = sch.place("mini-xt:74HCT138", "U1", "74HC138", at=(101.6, 76.2))
    L(U1, "VCC", "+3V3", dx=0, dy=-2.54); L(U1, "GND", "GND", dx=0, dy=2.54)
    L(U1, "A0", "A6", dx=-2.54)          # A (LSB)
    L(U1, "A1", "A7", dx=-2.54)          # B
    L(U1, "A2", "A8", dx=-2.54)          # C (MSB)
    L(U1, "~{E0}", "AEN", dx=-2.54)      # CPU owns the bus
    L(U1, "~{E1}", "GND", dx=-2.54)
    L(U1, "E2", "A9", dx=-2.54)          # every target lives in 0x200-0x3FF
    L(U1, "~{Y7}", "WIN_COM1")           # 0x3C0-0x3FF
    L(U1, "~{Y3}", "WIN_COM2")           # 0x2C0-0x2FF
    L(U1, "~{Y5}", "WIN_LPT378")         # 0x340-0x37F
    L(U1, "~{Y1}", "WIN_LPT278")         # 0x240-0x27F
    L(U1, "~{Y4}", "WIN_IDE")            # 0x300-0x33F
    for y in ("~{Y0}", "~{Y2}", "~{Y6}"):
        sch.no_connect(U1.pin_xy(y))

    # ---------------- U2: shared fine term ~Q = ~(A5&A4&A3), plus ~A5 ----------------
    # 74HC00 value override (same 3.3V rationale). Gate 2 re-inverts gate 1
    # so gate 3 can NAND in A3 (no 3-input NAND in the flat glue set).
    U2 = sch.place("mini-xt:74HCT00", "U2", "74HC00", at=(152.4, 76.2))
    L(U2, "VCC", "+3V3", dx=0, dy=-2.54); L(U2, "GND", "GND", dx=0, dy=2.54)
    L(U2, "P1", "A5", dx=-2.54); L(U2, "P2", "A4", dx=-2.54); L(U2, "P3", "N54")
    L(U2, "P4", "N54", dx=-2.54); L(U2, "P5", "N54", dx=-2.54); L(U2, "P6", "Q54")
    L(U2, "P9", "Q54", dx=-2.54); L(U2, "P10", "A3", dx=-2.54); L(U2, "P8", "Q_N")
    L(U2, "P12", "A5", dx=-2.54); L(U2, "P13", "A5", dx=-2.54); L(U2, "P11", "A5_N")

    # ---------------- U3: window + fine-term combine (active-low OR) ----------------
    # 74HC32 value override (same 3.3V rationale).
    U3 = sch.place("mini-xt:74HCT32", "U3", "74HC32", at=(203.2, 76.2))
    L(U3, "VCC", "+3V3", dx=0, dy=-2.54); L(U3, "GND", "GND", dx=0, dy=2.54)
    L(U3, "P1", "WIN_COM1", dx=-2.54); L(U3, "P2", "Q_N", dx=-2.54)
    L(U3, "P3", "CSP_COM1")
    L(U3, "P4", "WIN_COM2", dx=-2.54); L(U3, "P5", "Q_N", dx=-2.54)
    L(U3, "P6", "CSP_COM2")
    L(U3, "P9", "LPT_WIN", dx=-2.54); L(U3, "P10", "Q_N", dx=-2.54)
    L(U3, "P8", "CSP_LPT")
    L(U3, "P12", "WIN_IDE", dx=-2.54); L(U3, "P13", "IDE_A5", dx=-2.54)
    L(U3, "P11", "CSP_IDE")

    # ---------------- U4: disable-jumper combine ----------------
    # Second OR rank: DIS_x high (jumper fitted) forces the chip select
    # inactive. 74HC32 value override (same 3.3V rationale).
    U4 = sch.place("mini-xt:74HCT32", "U4", "74HC32", at=(254.0, 76.2))
    L(U4, "VCC", "+3V3", dx=0, dy=-2.54); L(U4, "GND", "GND", dx=0, dy=2.54)
    L(U4, "P1", "CSP_COM1", dx=-2.54); L(U4, "P2", "DIS_COM1", dx=-2.54)
    L(U4, "P3", "~{COM1_CS}")
    L(U4, "P4", "CSP_COM2", dx=-2.54); L(U4, "P5", "DIS_COM2", dx=-2.54)
    L(U4, "P6", "~{COM2_CS}")
    L(U4, "P9", "CSP_LPT", dx=-2.54); L(U4, "P10", "DIS_LPT", dx=-2.54)
    L(U4, "P8", "~{LPT_CS}")
    L(U4, "P12", "CSP_IDE", dx=-2.54); L(U4, "P13", "DIS_IDE", dx=-2.54)
    L(U4, "P11", "~{IDE_CS}")

    # ---------------- U5: shared IRQ driver (74LVC125A) ----------------
    # One quad tri-state buffer drives all four ISA IRQ lines (replaces the
    # per-sheet '125s). COM channels: in = raw INTRPT, ~OE = the UART's
    # ~{OUT2} (PC convention -- clearing OUT2 releases the line). LPT/IDE:
    # in strapped high, driven onto the line only while the active-low
    # request asserts (their request sources idle high, see mxbus.PRIV_IRQREQ).
    # 74LVC125A value override on the HCT125 body: LVC grade for 3.3V.
    U5 = sch.place("mini-xt:74HCT125", "U5", "74LVC125A", at=(304.8, 76.2))
    L(U5, "VCC", "+3V3", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "P1", "~{COM1_IRQEN}", dx=-2.54)
    L(U5, "P2", "IRQ_COM1", dx=-2.54)
    L(U5, "P3", "IRQ4")
    L(U5, "P4", "~{COM2_IRQEN}", dx=-2.54)
    L(U5, "P5", "IRQ_COM2", dx=-2.54)
    L(U5, "P6", "IRQ3")
    L(U5, "P10", "~{IRQ_LPT}", dx=-2.54)
    L(U5, "P9", "+3V3", dx=-2.54)
    L(U5, "P8", "IRQ7")
    L(U5, "P13", "~{IRQ_IDE}", dx=-2.54)
    L(U5, "P12", "+3V3", dx=-2.54)
    L(U5, "P11", "IRQ14")

    # ---------------- base-address straps ----------------
    # JP1: LPT base -- 1-2 = 0x378 (LPT1), 2-3 = 0x278 (LPT2)
    JP1 = sch.place("Connector_Generic:Conn_01x03", "JP1", "LPT 378/278", at=(355.6, 63.5))
    L(JP1, "Pin_1", "WIN_LPT378", dx=2.54)
    L(JP1, "Pin_2", "LPT_WIN", dx=2.54)
    L(JP1, "Pin_3", "WIN_LPT278", dx=2.54)
    # JP2: IDE base -- 1-2 = 0x300 (A5 must be 0 -> OR-input A5), 2-3 = 0x320
    JP2 = sch.place("Connector_Generic:Conn_01x03", "JP2", "IDE 300/320", at=(355.6, 101.6))
    L(JP2, "Pin_1", "A5", dx=2.54)
    L(JP2, "Pin_2", "IDE_A5", dx=2.54)
    L(JP2, "Pin_3", "A5_N", dx=2.54)
    # Unjumpered base straps park HIGH = that peripheral never decodes (safe
    # default -- unlike the old on-sheet straps, which floated the decode).
    R1 = sch.place("Device:R", "R1", "10k", at=(388.62, 63.5))
    L(R1, "1", "+3V3", dx=0, dy=-2.54); L(R1, "2", "LPT_WIN", dx=0, dy=2.54)
    R2 = sch.place("Device:R", "R2", "10k", at=(388.62, 101.6))
    L(R2, "1", "+3V3", dx=0, dy=-2.54); L(R2, "2", "IDE_A5", dx=0, dy=2.54)

    # ---------------- per-peripheral disable jumpers ----------------
    # ENABLED by default (pulldown holds DIS_x low); fit the jumper to
    # disable. Disabling kills the chip select, which also silences the IRQ
    # request at its source and frees the address for an expansion-port card.
    def dis_jp(jref, rref, net, label, x):
        jp = sch.place("Connector_Generic:Conn_01x02", jref, label, at=(x, 152.4))
        L(jp, "Pin_1", net, dx=2.54)
        L(jp, "Pin_2", "+3V3", dx=2.54)
        r = sch.place("Device:R", rref, "10k", at=(x + 20.32, 152.4))
        L(r, "1", net, dx=0, dy=-2.54)
        L(r, "2", "GND", dx=0, dy=2.54)

    dis_jp("JP3", "R3", "DIS_COM1", "DIS COM1", 203.2)
    dis_jp("JP4", "R4", "DIS_COM2", "DIS COM2", 254.0)
    dis_jp("JP5", "R5", "DIS_LPT", "DIS LPT", 304.8)
    dis_jp("JP6", "R6", "DIS_IDE", "DIS IDE", 355.6)

    # ---------------- decoupling ----------------
    for i, x in enumerate([101.6, 116.84, 132.08, 147.32, 162.56]):
        c = sch.place("Device:C", "C%d" % (i + 1), "100nF", at=(x, 190.5))
        sch.net(c, "1", "+3V3", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    sch.text("One decode for all discrete peripherals: COM1 0x3F8, COM2 0x2F8, "
             "LPT JP1 0x378/0x278, IDE JP2 0x300/0x320", (101.6, 210.82))
    sch.text("JP3-JP6: peripheral ENABLED by default; fit jumper to disable "
             "(kills decode, silences IRQ, frees address+IRQ for expansion)",
             (101.6, 213.36))
    sch.text("U5 maps IRQ requests -> ISA lines: COM1=IRQ4, COM2=IRQ3, LPT=IRQ7, "
             "IDE=IRQ14 (hardwired conventions)", (101.6, 215.9))

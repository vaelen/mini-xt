"""Storage -- XT-IDE rev2 / "Chuck-mod" 8-bit interface + CompactFlash @ I/O 0x300.

Design doc S10. A discrete, period-correct mass-storage soft card:

  * 16-bit IDE data register made accessible as two 8-bit transfers
    ("Chuck-mod" high-byte latch):
      - 74HC245 buffers bus D0-D7  <-> IDE/CF D0-D7  (low byte, direct).
      - 74HCT573 WRITE latch: bus D0-D7 -> IDE D8-D15, loaded on a write to the
        high-byte register, output-enabled only on the IDE data-register write.
      - 74HCT573 READ  latch: IDE D8-D15 -> bus D0-D7, loaded on the IDE
        data-register read, output-enabled when reading the high-byte register.
  * Address decode: TRUE rev-2 / Chuck-mod map = rev 1 with bus A0<->A3 swapped
    at the card, giving XTIDE Universal BIOS's "XT-IDE rev 2" layout in a
    16-byte window (0x300-0x30F):
      data 0x300, HIGH-BYTE LATCH 0x301, count 0x302, cyl-lo 0x304, drv/head
      0x306, altstatus/devctl 0x307, error/feat 0x308, sector 0x30A, cyl-hi
      0x30C, status/cmd 0x30E, drive-addr 0x30F.  Drive DA0 = bus A3 (!),
      DA1 = A1, DA2 = A2.
      - 74HCT138 (DEC1) splits the window on A0/A4: ~Y0 = /CS0 (even offsets =
        command block), ~Y1 = /ODD_SEL (odd offsets: latch + control block).
      - 74HCT138 (DEC2) decodes A1,A2,A3 inside ODD: ~Y0 = high-byte latch
        (0x301); ~Y3/~Y7 (0x307/0x30F) AND together (U3) into /CS1, so the
        latch address never asserts a drive CS or the low-byte buffer.
      - 74HCT138 (DEC3/U11) decodes A1,A2,A3 inside CS0: ~Y0 = data reg 0x300.
      - glue: 74HCT08 (block qualifier + buffer enable + CS1 combine), 74HCT32
        (strobe combiners), 74HCT04 (inverters + IDE -RESET).
  * 40-pin IDE header (Conn_02x20) and a CompactFlash True-IDE socket
    (Conn_02x25, 50-pin -- no CF symbol in lib, see questions-storage.md) wired
    in parallel.
  * Drive INTRQ -> 2N7002-gated 74HCT125 -> IRQ14, hardwired (AT primary-IDE
    convention; the soft PIC is AT-style anyway). Poll vs interrupt is an
    XTIDE UB config choice -- the line can stay wired either way, since the
    '125 only drives while INTRQ is asserted.
  * JP1: base-address strap (0x300 vs 0x320; differ only in A5).
  * JP2: enable/disable jumper; open kills the card, closed enables it.

Soft card: exposes ONLY ISA signals + power. The IDE/CF connectors are local.
See hardware/notes/questions-storage.md for the register-map / topology picks.
Card can be disabled or re-strapped so an external XT-IDE on the sidecar
doesn't conflict.
"""
import mxbus
from mxbus import pin

NAME = "storage"
TITLE = "Storage -- XT-IDE (Chuck-mod) + CompactFlash @ 0x300"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +          # A0..A9
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "AEN", "RESET_DRV"]] +
    [pin("IRQ14", "output")]   # hardwired (AT primary-IDE); poll vs IRQ = XTIDE UB config
)


def build(sch, lib, expose=True):
    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    def L(c, p, net, dx=2.54, dy=0.0):
        sch.net(c, p, net, kind="label", dx=dx, dy=dy)

    def pwr(c, vpin, gpin, vnet="+5V"):
        L(c, vpin, vnet, dx=0, dy=-2.54)
        L(c, gpin, "GND", dx=0, dy=2.54)

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def pullup(ref, net, at):
        r = sch.place("Device:R", ref, "10k", at=at)
        sch.net(r, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", net, kind="label", dx=0, dy=2.54)

    # ============================================================ glue logic ===
    # ---- 74HCT04 hex inverter: latch strobes, address inverts, IDE -RESET ----
    INV = sch.place("mini-xt:74HCT04", "U1", at=(38.1, 76.2))
    pwr(INV, "VCC", "GND")
    L(INV, "P1", "HBW_N", dx=-2.54);  L(INV, "P2", "LE_W")     # write-latch Load
    L(INV, "P3", "DR_N",  dx=-2.54);  L(INV, "P4", "LE_RD")    # read-latch  Load
    L(INV, "P5", "A5",    dx=-2.54);  L(INV, "P6", "nA5")
    L(INV, "P9", "A6",    dx=-2.54);  L(INV, "P8", "nA6")
    L(INV, "P11", "A7",   dx=-2.54);  L(INV, "P10", "nA7")
    L(INV, "P13", "RESET_DRV", dx=-2.54); L(INV, "P12", "~{IDE_RST}")

    # ---- 74HCT08 #1: block-address qualifier (A9&A8&~A5&~A6&~A7) -> HI_MATCH ----
    AND1 = sch.place("mini-xt:74HCT08", "U2", at=(38.1, 142.24))
    pwr(AND1, "VCC", "GND")
    L(AND1, "P1", "A9", dx=-2.54); L(AND1, "P2", "A8", dx=-2.54); L(AND1, "P3", "M1")
    L(AND1, "P4", "A5_SEL", dx=-2.54); L(AND1, "P5", "nA6", dx=-2.54); L(AND1, "P6", "M2")
    L(AND1, "P9", "M1", dx=-2.54); L(AND1, "P10", "M2", dx=-2.54); L(AND1, "P8", "M3")
    L(AND1, "P12", "M3", dx=-2.54); L(AND1, "P13", "nA7", dx=-2.54); L(AND1, "P11", "HI_MATCH")

    # ---- 74HCT08 #2: low-byte buffer enable + CS1 combine ----
    AND2 = sch.place("mini-xt:74HCT08", "U3", at=(38.1, 205.74))
    pwr(AND2, "VCC", "GND")
    L(AND2, "P1", "~{IDE_CS0}", dx=-2.54); L(AND2, "P2", "~{IDE_CS1}", dx=-2.54)
    L(AND2, "P3", "~{DBUF_OE}")            # buffer on for any DRIVE access (not the latch)
    # /CS1 = control-block regs only (0x307 altstatus, 0x30F drive-addr): AND of
    # the two active-low DEC2 outputs -- low when either decodes.
    L(AND2, "P4", "~{CS1_A}", dx=-2.54); L(AND2, "P5", "~{CS1_B}", dx=-2.54)
    L(AND2, "P6", "~{IDE_CS1}")
    for u in ("P9", "P10", "P12", "P13"):        # spare gates: tie inputs
        L(AND2, u, "GND", dx=-2.54)
    sch.no_connect(AND2.pin_xy("P8")); sch.no_connect(AND2.pin_xy("P11"))

    # ---- 74HCT32: strobe combiners (active-low pins -> active-low strobe) ----
    OR = sch.place("mini-xt:74HCT32", "U4", at=(114.3, 210.82))
    pwr(OR, "VCC", "GND")
    L(OR, "P1", "~{DATA_SEL}", dx=-2.54); L(OR, "P2", "~{IOW}", dx=-2.54); L(OR, "P3", "~{DWR_N}")   # data write
    L(OR, "P4", "~{DATA_SEL}", dx=-2.54); L(OR, "P5", "~{IOR}", dx=-2.54); L(OR, "P6", "DR_N")        # data read
    L(OR, "P9", "~{HB_SEL}", dx=-2.54);  L(OR, "P10", "~{IOR}", dx=-2.54); L(OR, "P8", "~{HBRD_N}")  # HB read
    L(OR, "P12", "~{HB_SEL}", dx=-2.54); L(OR, "P13", "~{IOW}", dx=-2.54); L(OR, "P11", "HBW_N")      # HB write

    # ---- 74HCT125: INTRQ -> IRQ14 (hardwired), tri-state (drive-high-else-release) ----
    # Q1 (2N7002) inverts INTRQ into the '125 ~OE: INTRQ=1 -> ~OE=0 -> buffer
    # drives IRQ14 high (input strapped high); INTRQ=0 -> ~OE=1 (R4) -> Z, so the
    # line stays shareable -- same convention as the LPT card's IRQ7 stage.
    IRQ = sch.place("mini-xt:74HCT125", "U5", at=(38.1, 256.54))
    pwr(IRQ, "VCC", "GND")
    L(IRQ, "P1", "~{IRQ_OE}", dx=-2.54); L(IRQ, "P2", "+5V", dx=-2.54); L(IRQ, "P3", "IRQ14")
    for oe in ("P4", "P10", "P13"):
        L(IRQ, oe, "+5V", dx=-2.54)
    for ip in ("P5", "P9", "P12"):
        L(IRQ, ip, "GND", dx=-2.54)
    for u in ("P6", "P8", "P11"):
        sch.no_connect(IRQ.pin_xy(u))
    Q1 = sch.place("Device:Q_NMOS", "Q1", "2N7002", at=(76.2, 256.54))
    L(Q1, "G", "IDE_IRQ", dx=-2.54)
    L(Q1, "D", "~{IRQ_OE}", dx=0, dy=-2.54)
    L(Q1, "S", "GND", dx=0, dy=2.54)

    # ============================================================== decode ====
    # Rev-2 = A0<->A3 swap: A0 splits even (drive command block) vs odd (latch
    # + control block); the drive's DA0 is bus A3 (wired at the connectors).
    # ---- DEC1: window split on A0/A4 -> /CS0 (even), /ODD_SEL (odd) ----
    DEC1 = sch.place("mini-xt:74HCT138", "U6", at=(114.3, 63.5))
    pwr(DEC1, "VCC", "GND")
    L(DEC1, "A0", "A0", dx=-2.54); L(DEC1, "A1", "A4", dx=-2.54); L(DEC1, "A2", "GND", dx=-2.54)
    L(DEC1, "~{E0}", "AEN", dx=-2.54); L(DEC1, "~{E1}", "~{STOR_EN}", dx=-2.54); L(DEC1, "E2", "HI_MATCH", dx=-2.54)
    L(DEC1, "~{Y0}", "~{IDE_CS0}")     # even offsets 0x300..0x30E: command block
    L(DEC1, "~{Y1}", "~{ODD_SEL}")     # odd offsets 0x301..0x30F: latch + ctrl
    for y in ("~{Y2}", "~{Y3}", "~{Y4}", "~{Y5}", "~{Y6}", "~{Y7}"):
        sch.no_connect(DEC1.pin_xy(y))  # A4=1 region unused (16-byte window)

    # ---- DEC2: odd-side decode (A1,A2,A3): latch @0x301, CS1 @0x307/0x30F ----
    DEC2 = sch.place("mini-xt:74HCT138", "U7", at=(114.3, 142.24))
    pwr(DEC2, "VCC", "GND")
    L(DEC2, "A0", "A1", dx=-2.54); L(DEC2, "A1", "A2", dx=-2.54); L(DEC2, "A2", "A3", dx=-2.54)
    L(DEC2, "~{E0}", "~{ODD_SEL}", dx=-2.54); L(DEC2, "~{E1}", "GND", dx=-2.54); L(DEC2, "E2", "+5V", dx=-2.54)
    L(DEC2, "~{Y0}", "~{HB_SEL}")      # 0x301 = high-byte latch register
    L(DEC2, "~{Y3}", "~{CS1_A}")       # 0x307 = altstatus / device control
    L(DEC2, "~{Y7}", "~{CS1_B}")       # 0x30F = drive address
    for y in ("~{Y1}", "~{Y2}", "~{Y4}", "~{Y5}", "~{Y6}"):
        sch.no_connect(DEC2.pin_xy(y))

    # ---- DEC3: even-side decode (A1,A2,A3) inside CS0; ~Y0 = data reg 0x300 ----
    DEC3 = sch.place("mini-xt:74HCT138", "U11", at=(152.4, 63.5))
    pwr(DEC3, "VCC", "GND")
    L(DEC3, "A0", "A1", dx=-2.54); L(DEC3, "A1", "A2", dx=-2.54); L(DEC3, "A2", "A3", dx=-2.54)
    L(DEC3, "~{E0}", "~{IDE_CS0}", dx=-2.54); L(DEC3, "~{E1}", "GND", dx=-2.54); L(DEC3, "E2", "+5V", dx=-2.54)
    L(DEC3, "~{Y0}", "~{DATA_SEL}")    # 0x300 = 16-bit data register
    for y in ("~{Y1}", "~{Y2}", "~{Y3}", "~{Y4}", "~{Y5}", "~{Y6}", "~{Y7}"):
        sch.no_connect(DEC3.pin_xy(y))

    # =========================================================== data path ====
    # ---- 74HC245 low-byte buffer: bus D0-D7 <-> IDE/CF D0-D7 ----
    LB = sch.place("mini-xt:74HCT245", "U8", at=(190.5, 63.5))
    pwr(LB, "VCC", "GND")
    L(LB, "A->B", "~{IOR}", dx=-2.54)    # write (IOR high) drives bus->IDE
    L(LB, "CE", "~{DBUF_OE}", dx=-2.54)  # enabled for any IDE register access
    for i in range(8):
        L(LB, "A%d" % i, "D%d" % i, dx=-2.54)     # bus side
        L(LB, "B%d" % i, "ID%d" % i)              # IDE side (low byte)

    # ---- 74HCT573 high-byte WRITE latch: bus D0-D7 -> IDE D8-D15 ----
    HW = sch.place("mini-xt:74HCT573", "U9", at=(190.5, 142.24))
    pwr(HW, "VCC", "GND")
    L(HW, "Load", "LE_W", dx=-2.54)      # capture on write to HB register
    L(HW, "OE", "~{DWR_N}", dx=-2.54)    # drive IDE high byte only on data write
    for i in range(8):
        L(HW, "D%d" % i, "D%d" % i, dx=-2.54)     # bus side
        L(HW, "Q%d" % i, "ID%d" % (8 + i))        # IDE high byte D8..D15

    # ---- 74HCT573 high-byte READ latch: IDE D8-D15 -> bus D0-D7 ----
    HR = sch.place("mini-xt:74HCT573", "U10", at=(190.5, 215.9))
    pwr(HR, "VCC", "GND")
    L(HR, "Load", "LE_RD", dx=-2.54)     # capture IDE high byte on data read
    L(HR, "OE", "~{HBRD_N}", dx=-2.54)   # present to bus when reading HB register
    for i in range(8):
        L(HR, "D%d" % i, "ID%d" % (8 + i), dx=-2.54)   # IDE high byte
        L(HR, "Q%d" % i, "D%d" % i)                    # bus side

    # ============================================================ connectors ==
    def conn_wire(conn, mapping, nc):
        for num, net in mapping.items():
            dx = -2.54 if int(num) % 2 == 1 else 2.54   # odd col left, even col right
            sch.net(conn, str(num), net, kind="label", dx=dx)
        for num in nc:
            sch.no_connect(conn.pin_xy(str(num)))

    # ---- 40-pin IDE header (standard ATA pinout) ----
    IDE = sch.place("Connector_Generic:Conn_02x20_Odd_Even", "J1", at=(292.1, 127.0))
    ide_map = {
        1: "~{IDE_RST}", 2: "GND",  3: "ID7", 4: "ID8", 5: "ID6", 6: "ID9",
        7: "ID5", 8: "ID10", 9: "ID4", 10: "ID11", 11: "ID3", 12: "ID12",
        13: "ID2", 14: "ID13", 15: "ID1", 16: "ID14", 17: "ID0", 18: "ID15",
        19: "GND", 22: "GND", 23: "~{IOW}", 24: "GND", 25: "~{IOR}", 26: "GND",
        27: "~{IORDY}", 28: "GND", 30: "GND", 31: "IDE_IRQ", 33: "A1", 35: "A3",
        36: "A2", 37: "~{IDE_CS0}", 38: "~{IDE_CS1}", 40: "GND",   # DA0 = bus A3 (rev-2 swap)
    }
    conn_wire(IDE, ide_map, nc=[20, 21, 29, 32, 34, 39])

    # ---- 50-pin CompactFlash socket, True-IDE mode (parallel to IDE) ----
    CF = sch.place("Connector_Generic:Conn_02x25_Odd_Even", "J2", at=(368.3, 127.0))
    cf_map = {
        1: "GND", 2: "ID3", 3: "ID4", 4: "ID5", 5: "ID6", 6: "ID7",
        7: "~{IDE_CS0}", 8: "GND", 9: "GND", 10: "GND", 11: "GND", 12: "GND",
        13: "+5V", 14: "GND", 15: "GND", 16: "GND", 17: "GND", 18: "A2",
        19: "A1", 20: "A3", 21: "ID0", 22: "ID1", 23: "ID2", 26: "GND",  # DA0 = bus A3
        27: "ID11", 28: "ID12", 29: "ID13", 30: "ID14", 31: "ID15",
        32: "~{IDE_CS1}", 34: "~{IOR}", 35: "~{IOW}", 36: "+5V", 37: "IDE_IRQ",
        38: "+5V", 39: "GND", 41: "~{IDE_RST}", 42: "~{IORDY}", 44: "+5V",
        47: "ID8", 48: "ID9", 49: "ID10", 50: "GND",
    }
    conn_wire(CF, cf_map, nc=[24, 25, 33, 40, 43, 45, 46])

    # =============================================================== passives =
    pullup("R1", "~{IORDY}", (228.6, 25.4))    # IORDY idle-high (8-bit PIO)
    # ATA INTRQ is ACTIVE-HIGH and tri-stated whenever no drive is selected (or
    # nIEN=1), so it parks DEASSERTED: pull-DOWN. (A pull-up here would hold
    # IRQ14 permanently asserted -> interrupt storm once IRQ14 is unmasked.)
    r2 = sch.place("Device:R", "R2", "10k", at=(243.84, 25.4))
    sch.net(r2, "1", "IDE_IRQ", kind="label", dx=0, dy=-2.54)
    sch.net(r2, "2", "GND", kind="label", dx=0, dy=2.54)
    pullup("R4", "~{IRQ_OE}", (91.44, 243.84))  # buffer released (Z) when INTRQ low
    # JP1: base address -- 1-2 = 0x300 (A5 must be 0), 2-3 = 0x320 (A5 must be 1).
    # 0x300/0x320 differ only in A5; the U1 inverter already provides nA5.
    JP1 = sch.place("Connector_Generic:Conn_01x03", "JP1", "BASE 300/320", at=(274.32, 25.4))
    L(JP1, "Pin_1", "nA5")
    L(JP1, "Pin_2", "A5_SEL")
    L(JP1, "Pin_3", "A5")
    # JP2: enable -- closed grounds ~{STOR_EN} (enabled); open = R5 parks it
    # high and DEC1 never selects, so /CS0, /ODD_SEL and everything downstream
    # (DEC2/DEC3, both '573 latch clocks, the '245 enable) are inert. IRQ14
    # stays quiet: the drive is never selected and R2 holds INTRQ low.
    JP2 = sch.place("Connector_Generic:Conn_01x02", "JP2", "STOR_EN", at=(289.56, 25.4))
    L(JP2, "Pin_1", "~{STOR_EN}")
    L(JP2, "Pin_2", "GND")
    pullup("R5", "~{STOR_EN}", (320.04, 25.4))
    for i, x in enumerate(range(30, 250, 20)):
        decouple("C%d" % (1 + i), (float(x), 276.86))
    cb = sch.place("Device:C", "C12", "10uF", at=(256.54, 276.86))   # card bulk
    sch.net(cb, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(cb, "2", "GND", kind="label", dx=0, dy=2.54)

    # =============== strapping notes ==
    sch.text("JP1 base 0x300/0x320 (XTIDE UB); JP2 open = card disabled; IRQ14 hardwired (poll vs IRQ = XTIDE UB config).", at=(266.7, 17.78))
    sch.text("Populate ONE of J1 (IDE) / J2 (CF): both CSELs are grounded, so both "
             "devices ID as master on the shared cable.", at=(266.7, 12.7))

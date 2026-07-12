"""parallel -- discrete 74HC parallel printer port (LPT1) @ I/O 0x378/0x278 + DB25.

Design doc S11.2. A *soft* card: it speaks ONLY the standard 8-bit XT/ISA bus
(A0-A9, D0-D7, ~{IOR}/~{IOW}, AEN) plus power and exports IRQ5/IRQ7
(selectable by JP3 strap). No private motherboard nets cross this sheet.

Straps: JP1 base address (A8 = 0x378 vs 0x278), JP2 enable/disable, JP3 IRQ
selection (IRQ7/IRQ5/open=polled).

Three classic registers in the 0x378 block (Centronics/SPP):
  * 0x378  Data    (R/W)  -- 74HCT574 output latch -> DB25 pins 2-9
                             read-back via 74HC245 onto the bus
  * 0x379  Status  (RO )  -- 74HCT244 buffers Busy/Ack/PaperEnd/Select/Error
  * 0x37A  Control (R/W)  -- 74HCT574 output latch (Strobe/AutoFd/Init/SlctIn
                             + IRQ-enable); read-back via 74HCT244

Address decode: 74HCT138 selects the three registers (A0-A2) once a 74HCT08
chain matches A3-A9 == 0x378>>3 (0b1111011) and AEN is low. 74HCT32 ORs the
register selects with ~{IOR}/~{IOW} to make the read enables and the rising-edge
write clocks for the '374s. IRQ7 is the (gated) ~Ack edge -- normally polled.
"""
import mxbus
from mxbus import pin

NAME = "parallel"
TITLE = "Parallel port (LPT1) -- 74HCT574/244/245 @ 0x378 + DB25"

# Soft card: ISA signals + power only.  DB25 is a LOCAL connector (not a hier pin).
PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +          # A0..A9 (I/O decode)
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin("~{IOR}", "input"), pin("~{IOW}", "input"),
     pin("AEN", "input")] +      # no RESET_DRV: the '574s have no reset pin;
                                 # BIOS initializes 0x378/0x37A at POST
    [pin("IRQ5", "output"), pin("IRQ7", "output")]        # JP3 picks the line
)


def build(sch, lib, expose=True):
    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # connectivity-by-name helper: stub a pin out to a local label
    def L(c, p, net, dx=2.54, dy=0.0):
        sch.net(c, p, net, kind="label", dx=dx, dy=dy)

    def pwr(c):
        L(c, "VCC", "+5V", dx=0, dy=-2.54)
        L(c, "GND", "GND", dx=0, dy=2.54)

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # ============================================================
    # Address decode -- match A3..A9 == 0b1111011 (0x378 block), AEN low
    #   A3=1 A4=1 A5=1 A6=1 A7=0 A8=1 A9=1   (A0..A2 -> register offset)
    # ============================================================
    U7 = sch.place("mini-xt:74HCT08", "U7", at=(76.2, 76.2))    # AND tree (1/2)
    pwr(U7)
    L(U7, "P1", "A3", dx=-2.54); L(U7, "P2", "A4", dx=-2.54); L(U7, "P3", "AM_A")
    L(U7, "P4", "A5", dx=-2.54); L(U7, "P5", "A6", dx=-2.54); L(U7, "P6", "AM_B")
    L(U7, "P9", "A8_SEL", dx=-2.54); L(U7, "P10", "A9", dx=-2.54); L(U7, "P8", "AM_C")
    L(U7, "P12", "AM_A", dx=-2.54); L(U7, "P13", "AM_B", dx=-2.54); L(U7, "P11", "AM1")

    U8 = sch.place("mini-xt:74HCT08", "U8", at=(76.2, 127.0))   # AND tree (2/2) + IRQ
    pwr(U8)
    L(U8, "P1", "AM1", dx=-2.54); L(U8, "P2", "AM_C", dx=-2.54); L(U8, "P3", "AM2")
    L(U8, "P4", "AM2", dx=-2.54); L(U8, "P5", "NA7", dx=-2.54); L(U8, "P6", "ADDR_MATCH")
    # (IRQ7 drive moved to a tri-state buffer, U12/U13 below -- a push-pull
    # gate here would block any other card from ever sharing the IRQ7 line.)
    L(U8, "P9", "GND", dx=-2.54); L(U8, "P10", "GND", dx=-2.54)   # spare gate inputs
    L(U8, "P12", "GND", dx=-2.54); L(U8, "P13", "GND", dx=-2.54)
    sch.no_connect(U8.pin_xy("P8")); sch.no_connect(U8.pin_xy("P11"))

    U9 = sch.place("mini-xt:74HCT04", "U9", at=(76.2, 177.8))   # inverters
    pwr(U9)
    L(U9, "P1", "A7", dx=-2.54); L(U9, "P2", "NA7")               # ~A7 for decode
    L(U9, "P3", "P_ACK", dx=-2.54); L(U9, "P4", "ACK_POS")        # ~Ack -> +pulse
    L(U9, "P5", "CTRL0", dx=-2.54); L(U9, "P6", "P_STROBE")       # Strobe (inv)
    L(U9, "P9", "CTRL1", dx=-2.54); L(U9, "P8", "P_AUTOFD")       # AutoFeed (inv)
    L(U9, "P11", "CTRL3", dx=-2.54); L(U9, "P10", "P_SLIN")       # SelectIn (inv)
    L(U9, "P13", "P_BUSY", dx=-2.54); L(U9, "P12", "BUSY_N")      # Busy -> ~Busy (status bit 7)

    # IRQ drive: tri-state, like a real LPT card -- asserted high only for
    # the ~Ack pulse while IRQ_EN (control bit 4) is set, released (Z)
    # otherwise so the line stays shareable.  U12 NAND gate 1 makes the
    # active-low enable for the U13 '125 buffer (input strapped high); gate 2
    # makes ~A8 for the base-address strap (JP1). Output drives LPT_IRQ into
    # JP3 strap that selects IRQ7 or IRQ5.
    # NOTE the ISA ~Ack pulse is 1-12 us and is NOT latched here (real SPP
    # behaviour): the Bus MCU's '165 IRQ poll loop must run faster than the
    # shortest pulse, or sample IRQ7 via PIO.
    U12 = sch.place("mini-xt:74HCT00", "U12", at=(266.7, 76.2))
    pwr(U12)
    L(U12, "P1", "ACK_POS", dx=-2.54); L(U12, "P2", "IRQ_EN", dx=-2.54)
    L(U12, "P3", "~{IRQ7_OE}")
    L(U12, "P4", "A8", dx=-2.54); L(U12, "P5", "A8", dx=-2.54); L(U12, "P6", "NA8")   # spare NAND as ~A8 inverter (base strap)
    for ip in ("P9", "P10", "P12", "P13"):
        L(U12, ip, "GND", dx=-2.54)
    sch.no_connect(U12.pin_xy("P8")); sch.no_connect(U12.pin_xy("P11"))
    U13 = sch.place("mini-xt:74HCT125", "U13", at=(266.7, 127.0))
    pwr(U13)
    L(U13, "P1", "~{IRQ7_OE}", dx=-2.54); L(U13, "P2", "+5V", dx=-2.54)
    L(U13, "P3", "LPT_IRQ")
    for oe in ("P4", "P10", "P13"):
        L(U13, oe, "+5V", dx=-2.54)        # disable spare buffers
    for ip in ("P5", "P9", "P12"):
        L(U13, ip, "GND", dx=-2.54)
    for op in ("P6", "P8", "P11"):
        sch.no_connect(U13.pin_xy(op))

    U6 = sch.place("mini-xt:74HCT138", "U6", at=(139.7, 177.8))  # register select
    pwr(U6)
    L(U6, "A0", "A0", dx=-2.54); L(U6, "A1", "A1", dx=-2.54); L(U6, "A2", "A2", dx=-2.54)
    L(U6, "~{E0}", "AEN", dx=-2.54)      # enabled only when AEN low (CPU owns bus)
    L(U6, "~{E1}", "~{LPT_EN}", dx=-2.54)
    L(U6, "E2", "ADDR_MATCH", dx=-2.54)  # active-high block match
    L(U6, "~{Y0}", "~{SEL_DATA}")        # 0x378
    L(U6, "~{Y1}", "~{SEL_STAT}")        # 0x379
    L(U6, "~{Y2}", "~{SEL_CTRL}")        # 0x37A
    for y in ("~{Y3}", "~{Y4}", "~{Y5}", "~{Y6}", "~{Y7}"):
        sch.no_connect(U6.pin_xy(y))

    # OR register-select with the command strobes:
    #   write clocks rise at the end of the cycle (~IOW going high) -> latch
    #   read enables are active-low for the '244/'245 output buffers
    U10 = sch.place("mini-xt:74HCT32", "U10", at=(203.2, 177.8))
    pwr(U10)
    L(U10, "P1", "~{SEL_DATA}", dx=-2.54); L(U10, "P2", "~{IOW}", dx=-2.54); L(U10, "P3", "WR_DATA")
    L(U10, "P4", "~{SEL_CTRL}", dx=-2.54); L(U10, "P5", "~{IOW}", dx=-2.54); L(U10, "P6", "WR_CTRL")
    L(U10, "P9", "~{SEL_DATA}", dx=-2.54); L(U10, "P10", "~{IOR}", dx=-2.54); L(U10, "P8", "~{RD_DATA}")
    L(U10, "P12", "~{SEL_STAT}", dx=-2.54); L(U10, "P13", "~{IOR}", dx=-2.54); L(U10, "P11", "~{RD_STAT}")

    U11 = sch.place("mini-xt:74HCT32", "U11", at=(266.7, 177.8))
    pwr(U11)
    L(U11, "P1", "~{SEL_CTRL}", dx=-2.54); L(U11, "P2", "~{IOR}", dx=-2.54); L(U11, "P3", "~{RD_CTRL}")
    for a, b in (("P4", "P5"), ("P9", "P10"), ("P12", "P13")):       # spare gates
        L(U11, a, "GND", dx=-2.54); L(U11, b, "GND", dx=-2.54)
    for o in ("P6", "P8", "P11"):
        sch.no_connect(U11.pin_xy(o))

    # ============================================================
    # Data register  (0x378) -- 74HCT574 latch, always-enabled outputs
    # ('574 = '374 with flow-through pinout; the '374 is not stocked at JLC)
    # ============================================================
    U1 = sch.place("mini-xt:74HCT574", "U1", at=(139.7, 76.2))
    pwr(U1)
    L(U1, "Cp", "WR_DATA", dx=-2.54)
    L(U1, "OE", "GND", dx=-2.54)
    for i in range(8):
        L(U1, "D%d" % i, "D%d" % i, dx=-2.54)         # bus -> latch
        L(U1, "Q%d" % i, "PD%d" % i)                  # latch -> DB25 data pin

    # data read-back: latched value driven onto the bus during a read of 0x378
    U4 = sch.place("mini-xt:74HCT245", "U4", at=(203.2, 76.2))
    pwr(U4)
    L(U4, "A->B", "+5V", dx=-2.54)        # always A(latch)->B(bus) direction
    L(U4, "CE", "~{RD_DATA}", dx=-2.54)
    for i in range(8):
        L(U4, "A%d" % i, "PD%d" % i, dx=-2.54)
        L(U4, "B%d" % i, "D%d" % i)

    # ============================================================
    # Control register (0x37A) -- 74HCT574 latch + 74HCT244 read-back
    #   Q0 Strobe  Q1 AutoFeed  Q2 Init(direct)  Q3 SelectIn  Q4 IRQ-enable
    # ============================================================
    U2 = sch.place("mini-xt:74HCT574", "U2", at=(139.7, 127.0))
    pwr(U2)
    L(U2, "Cp", "WR_CTRL", dx=-2.54)
    L(U2, "OE", "GND", dx=-2.54)
    for i in range(5):
        L(U2, "D%d" % i, "D%d" % i, dx=-2.54)
    for i in range(5, 8):
        L(U2, "D%d" % i, "GND", dx=-2.54)             # unused control bits
    L(U2, "Q0", "CTRL0"); L(U2, "Q1", "CTRL1")
    L(U2, "Q2", "CTRL2")          # Init is non-inverted: latch -> DB25 pin 16 direct
    L(U2, "Q3", "CTRL3"); L(U2, "Q4", "IRQ_EN")
    for o in ("Q5", "Q6", "Q7"):
        sch.no_connect(U2.pin_xy(o))

    U5 = sch.place("mini-xt:74HCT244", "U5", at=(203.2, 127.0))  # control read-back
    pwr(U5)
    L(U5, "1OE", "~{RD_CTRL}", dx=-2.54); L(U5, "2OE", "~{RD_CTRL}", dx=-2.54)
    cb = [("1A0", "1Y0", "CTRL0", "D0"), ("1A1", "1Y1", "CTRL1", "D1"),
          ("1A2", "1Y2", "CTRL2", "D2"), ("1A3", "1Y3", "CTRL3", "D3"),
          ("2A0", "2Y0", "IRQ_EN", "D4")]
    for a, y, src, d in cb:
        L(U5, a, src, dx=-2.54); L(U5, y, d)
    for a in ("2A1", "2A2", "2A3"):
        L(U5, a, "GND", dx=-2.54)
    for y in ("2Y1", "2Y2", "2Y3"):
        sch.no_connect(U5.pin_xy(y))

    # ============================================================
    # Status register (0x379) -- 74HCT244 buffers printer status onto the bus
    #   D7 ~Busy  D6 ~Ack  D5 PaperEnd  D4 Select  D3 ~Error  (D2..D0 = 0)
    # Bit 7 is INVERTED ON THE CARD (standard SPP semantics): BIOS INT 17h
    # spins on bit7=1 = "ready", so DB25 Busy passes through a U9 inverter.
    # ============================================================
    U3 = sch.place("mini-xt:74HCT244", "U3", at=(203.2, 228.6))
    pwr(U3)
    L(U3, "1OE", "~{RD_STAT}", dx=-2.54); L(U3, "2OE", "~{RD_STAT}", dx=-2.54)
    sb = [("1A0", "1Y0", "BUSY_N", "D7"), ("1A1", "1Y1", "P_ACK", "D6"),
          ("1A2", "1Y2", "P_PE", "D5"), ("1A3", "1Y3", "P_SEL", "D4"),
          ("2A0", "2Y0", "P_ERR", "D3")]
    for a, y, src, d in sb:
        L(U3, a, src, dx=-2.54); L(U3, y, d)
    L(U3, "2A1", "GND", dx=-2.54); L(U3, "2Y1", "D2")
    L(U3, "2A2", "GND", dx=-2.54); L(U3, "2Y2", "D1")
    L(U3, "2A3", "GND", dx=-2.54); L(U3, "2Y3", "D0")

    # ============================================================
    # DB25 male -- standard SPP/Centronics LPT pinout
    # ============================================================
    J1 = sch.place("Connector:DB25_Pins", "J1", at=(355.6, 127.0))
    db = {
        "1": "P_STROBE",                                   # ~Strobe (out)
        "2": "PD0", "3": "PD1", "4": "PD2", "5": "PD3",
        "6": "PD4", "7": "PD5", "8": "PD6", "9": "PD7",    # D0..D7 (out)
        "10": "P_ACK",                                     # ~Ack  (in)
        "11": "P_BUSY",                                    # Busy  (in)
        "12": "P_PE",                                      # PaperEnd (in)
        "13": "P_SEL",                                     # Select (in)
        "14": "P_AUTOFD",                                  # ~AutoFeed (out)
        "15": "P_ERR",                                     # ~Error (in)
        "16": "CTRL2",                                     # ~Init (out, non-inverted)
        "17": "P_SLIN",                                    # ~SelectIn (out)
    }
    for num, net in db.items():
        L(J1, num, net, dx=-2.54)
    for num in range(18, 26):                              # pins 18-25 = signal GND
        L(J1, str(num), "GND", dx=-2.54)

    # ============================================================
    # Pull-ups on the printer status inputs
    # ============================================================
    # 4.7k pull-ups on the printer status inputs: with no printer attached these
    # float into HCT inputs (oscillation + phantom ~Ack IRQs). Real SPP cards
    # shipped exactly this network.
    for i, net in enumerate(["P_ACK", "P_BUSY", "P_PE", "P_SEL", "P_ERR"]):
        r = sch.place("Device:R", "R%d" % (1 + i), "4.7k", at=(314.96 + 15.24 * i, 45.72))
        sch.net(r, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", net, kind="label", dx=0, dy=2.54)

    # ============================================================
    # Configuration straps
    # ============================================================
    # JP1: base address -- A8=1 -> 0x378 (LPT1), A8=0 -> 0x278 (LPT2)
    JP1 = sch.place("Connector_Generic:Conn_01x03", "JP1", "BASE 378/278", at=(299.72, 195.58))
    L(JP1, "Pin_1", "A8", dx=2.54)
    L(JP1, "Pin_2", "A8_SEL", dx=2.54)
    L(JP1, "Pin_3", "NA8", dx=2.54)

    # JP2: port enable -- closed = ~{LPT_EN} grounded = enabled; open = R6 parks
    # it high, the '138 never selects, so no register read/write/latch clock can
    # fire. IRQ7 stays silent too: the DB25 pull-ups idle ~Ack high -> ACK_POS
    # low -> U13 released.
    JP2 = sch.place("Connector_Generic:Conn_01x02", "JP2", "LPT_EN", at=(314.96, 195.58))
    L(JP2, "Pin_1", "~{LPT_EN}", dx=2.54)
    L(JP2, "Pin_2", "GND", dx=2.54)
    r6 = sch.place("Device:R", "R6", "10k", at=(345.44, 195.58))
    sch.net(r6, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(r6, "2", "~{LPT_EN}", kind="label", dx=0, dy=2.54)

    # JP3: IRQ strap -- 1-2 = IRQ7 (LPT1 convention), 2-3 = IRQ5 (NOTE: shared
    # with the storage card's XT-IDE INTRQ -- don't enable both on IRQ5), open =
    # polled-only. U13 is tri-state, so the unselected line is untouched.
    JP3 = sch.place("Connector_Generic:Conn_01x03", "JP3", "IRQ strap", at=(330.2, 195.58))
    L(JP3, "Pin_1", "IRQ7", dx=2.54)
    L(JP3, "Pin_2", "LPT_IRQ", dx=2.54)
    L(JP3, "Pin_3", "IRQ5", dx=2.54)

    # Configuration note
    sch.text("JP1: base 0x378/0x278; JP2: open=port disabled; JP3: IRQ7/IRQ5/open=polled",
             at=(299.72, 187.96), size=2.5)

    # ============================================================
    # decoupling
    # ============================================================
    for i, x in enumerate([30.48, 60.96, 91.44, 121.92, 152.4, 182.88, 213.36, 243.84, 274.32, 304.8, 335.28, 365.76, 396.24]):
        decouple("C%d" % (i + 1), (x, 264.16))

    cb = sch.place("Device:C", "C14", "10uF", at=(30.48, 238.76))
    sch.net(cb, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(cb, "2", "GND", kind="label", dx=0, dy=2.54)

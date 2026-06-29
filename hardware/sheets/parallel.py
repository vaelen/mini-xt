"""parallel -- discrete 74HC parallel printer port (LPT1) @ I/O 0x378 + DB25.

Design doc S11.2. A *soft* card: it speaks ONLY the standard 8-bit XT/ISA bus
(A0-A9, D0-D7, ~{IOR}/~{IOW}, AEN, RESET_DRV) plus power and exports IRQ7. No
private motherboard nets cross this sheet.

Three classic registers in the 0x378 block (Centronics/SPP):
  * 0x378  Data    (R/W)  -- 74HC374 output latch -> DB25 pins 2-9
                             read-back via 74HC245 onto the bus
  * 0x379  Status  (RO )  -- 74HC244 buffers Busy/Ack/PaperEnd/Select/Error
  * 0x37A  Control (R/W)  -- 74HC374 output latch (Strobe/AutoFd/Init/SlctIn
                             + IRQ-enable); read-back via 74HC244

Address decode: 74HCT138 selects the three registers (A0-A2) once a 74HC08
chain matches A3-A9 == 0x378>>3 (0b1111011) and AEN is low. 74HC32 ORs the
register selects with ~{IOR}/~{IOW} to make the read enables and the rising-edge
write clocks for the '374s. IRQ7 is the (gated) ~Ack edge -- normally polled.
"""
import mxbus
from mxbus import pin

NAME = "parallel"
TITLE = "Parallel port (LPT1) -- 74HC374/244/245 @ 0x378 + DB25"

# Soft card: ISA signals + power only.  DB25 is a LOCAL connector (not a hier pin).
PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +          # A0..A9 (I/O decode)
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin("~{IOR}", "input"), pin("~{IOW}", "input"),
     pin("AEN", "input"), pin("RESET_DRV", "input")] +
    [pin("IRQ7", "output")]
)


def build(sch, lib):
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
    U7 = sch.place("mini-xt:74HC08", "U7", at=(76.2, 76.2))    # AND tree (1/2)
    pwr(U7)
    L(U7, "P1", "A3", dx=-2.54); L(U7, "P2", "A4", dx=-2.54); L(U7, "P3", "AM_A")
    L(U7, "P4", "A5", dx=-2.54); L(U7, "P5", "A6", dx=-2.54); L(U7, "P6", "AM_B")
    L(U7, "P9", "A8", dx=-2.54); L(U7, "P10", "A9", dx=-2.54); L(U7, "P8", "AM_C")
    L(U7, "P12", "AM_A", dx=-2.54); L(U7, "P13", "AM_B", dx=-2.54); L(U7, "P11", "AM1")

    U8 = sch.place("mini-xt:74HC08", "U8", at=(76.2, 127.0))   # AND tree (2/2) + IRQ
    pwr(U8)
    L(U8, "P1", "AM1", dx=-2.54); L(U8, "P2", "AM_C", dx=-2.54); L(U8, "P3", "AM2")
    L(U8, "P4", "AM2", dx=-2.54); L(U8, "P5", "NA7", dx=-2.54); L(U8, "P6", "ADDR_MATCH")
    # IRQ7 = ack(positive) AND irq-enable  (edge normally polled by the driver)
    L(U8, "P9", "ACK_POS", dx=-2.54); L(U8, "P10", "IRQ_EN", dx=-2.54); L(U8, "P8", "IRQ7")
    L(U8, "P12", "GND", dx=-2.54); L(U8, "P13", "GND", dx=-2.54)  # spare gate inputs
    sch.no_connect(U8.pin_xy("P11"))

    U9 = sch.place("mini-xt:74HC04", "U9", at=(76.2, 177.8))   # inverters
    pwr(U9)
    L(U9, "P1", "A7", dx=-2.54); L(U9, "P2", "NA7")               # ~A7 for decode
    L(U9, "P3", "P_ACK", dx=-2.54); L(U9, "P4", "ACK_POS")        # ~Ack -> +pulse
    L(U9, "P5", "CTRL0", dx=-2.54); L(U9, "P6", "P_STROBE")       # Strobe (inv)
    L(U9, "P9", "CTRL1", dx=-2.54); L(U9, "P8", "P_AUTOFD")       # AutoFeed (inv)
    L(U9, "P11", "CTRL3", dx=-2.54); L(U9, "P10", "P_SLIN")       # SelectIn (inv)
    L(U9, "P13", "GND", dx=-2.54); sch.no_connect(U9.pin_xy("P12"))  # spare inverter

    U6 = sch.place("mini-xt:74HCT138", "U6", at=(139.7, 177.8))  # register select
    pwr(U6)
    L(U6, "A0", "A0", dx=-2.54); L(U6, "A1", "A1", dx=-2.54); L(U6, "A2", "A2", dx=-2.54)
    L(U6, "~{E0}", "AEN", dx=-2.54)      # enabled only when AEN low (CPU owns bus)
    L(U6, "~{E1}", "GND", dx=-2.54)
    L(U6, "E2", "ADDR_MATCH", dx=-2.54)  # active-high block match
    L(U6, "~{Y0}", "~{SEL_DATA}")        # 0x378
    L(U6, "~{Y1}", "~{SEL_STAT}")        # 0x379
    L(U6, "~{Y2}", "~{SEL_CTRL}")        # 0x37A
    for y in ("~{Y3}", "~{Y4}", "~{Y5}", "~{Y6}", "~{Y7}"):
        sch.no_connect(U6.pin_xy(y))

    # OR register-select with the command strobes:
    #   write clocks rise at the end of the cycle (~IOW going high) -> latch
    #   read enables are active-low for the '244/'245 output buffers
    U10 = sch.place("mini-xt:74HC32", "U10", at=(203.2, 177.8))
    pwr(U10)
    L(U10, "P1", "~{SEL_DATA}", dx=-2.54); L(U10, "P2", "~{IOW}", dx=-2.54); L(U10, "P3", "WR_DATA")
    L(U10, "P4", "~{SEL_CTRL}", dx=-2.54); L(U10, "P5", "~{IOW}", dx=-2.54); L(U10, "P6", "WR_CTRL")
    L(U10, "P9", "~{SEL_DATA}", dx=-2.54); L(U10, "P10", "~{IOR}", dx=-2.54); L(U10, "P8", "~{RD_DATA}")
    L(U10, "P12", "~{SEL_STAT}", dx=-2.54); L(U10, "P13", "~{IOR}", dx=-2.54); L(U10, "P11", "~{RD_STAT}")

    U11 = sch.place("mini-xt:74HC32", "U11", at=(266.7, 177.8))
    pwr(U11)
    L(U11, "P1", "~{SEL_CTRL}", dx=-2.54); L(U11, "P2", "~{IOR}", dx=-2.54); L(U11, "P3", "~{RD_CTRL}")
    for a, b in (("P4", "P5"), ("P9", "P10"), ("P12", "P13")):       # spare gates
        L(U11, a, "GND", dx=-2.54); L(U11, b, "GND", dx=-2.54)
    for o in ("P6", "P8", "P11"):
        sch.no_connect(U11.pin_xy(o))

    # ============================================================
    # Data register  (0x378) -- 74HC374 latch, always-enabled outputs
    # ============================================================
    U1 = sch.place("mini-xt:74HC374", "U1", at=(139.7, 76.2))
    pwr(U1)
    L(U1, "Cp", "WR_DATA", dx=-2.54)
    L(U1, "OE", "GND", dx=-2.54)
    for i in range(8):
        L(U1, "D%d" % i, "D%d" % i, dx=-2.54)         # bus -> latch
        L(U1, "O%d" % i, "PD%d" % i)                  # latch -> DB25 data pin

    # data read-back: latched value driven onto the bus during a read of 0x378
    U4 = sch.place("mini-xt:74HC245", "U4", at=(203.2, 76.2))
    pwr(U4)
    L(U4, "A->B", "+5V", dx=-2.54)        # always A(latch)->B(bus) direction
    L(U4, "CE", "~{RD_DATA}", dx=-2.54)
    for i in range(8):
        L(U4, "A%d" % i, "PD%d" % i, dx=-2.54)
        L(U4, "B%d" % i, "D%d" % i)

    # ============================================================
    # Control register (0x37A) -- 74HC374 latch + 74HC244 read-back
    #   O0 Strobe  O1 AutoFeed  O2 Init(direct)  O3 SelectIn  O4 IRQ-enable
    # ============================================================
    U2 = sch.place("mini-xt:74HC374", "U2", at=(139.7, 127.0))
    pwr(U2)
    L(U2, "Cp", "WR_CTRL", dx=-2.54)
    L(U2, "OE", "GND", dx=-2.54)
    for i in range(5):
        L(U2, "D%d" % i, "D%d" % i, dx=-2.54)
    for i in range(5, 8):
        L(U2, "D%d" % i, "GND", dx=-2.54)             # unused control bits
    L(U2, "O0", "CTRL0"); L(U2, "O1", "CTRL1")
    L(U2, "O2", "CTRL2")          # Init is non-inverted: latch -> DB25 pin 16 direct
    L(U2, "O3", "CTRL3"); L(U2, "O4", "IRQ_EN")
    for o in ("O5", "O6", "O7"):
        sch.no_connect(U2.pin_xy(o))

    U5 = sch.place("mini-xt:74HC244", "U5", at=(203.2, 127.0))  # control read-back
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
    # Status register (0x379) -- 74HC244 buffers printer status onto the bus
    #   D7 Busy  D6 ~Ack  D5 PaperEnd  D4 Select  D3 ~Error  (D2..D0 = 0)
    # ============================================================
    U3 = sch.place("mini-xt:74HC244", "U3", at=(203.2, 228.6))
    pwr(U3)
    L(U3, "1OE", "~{RD_STAT}", dx=-2.54); L(U3, "2OE", "~{RD_STAT}", dx=-2.54)
    sb = [("1A0", "1Y0", "P_BUSY", "D7"), ("1A1", "1Y1", "P_ACK", "D6"),
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
    # decoupling
    # ============================================================
    for i, x in enumerate([76.2, 116.84, 157.48, 198.12, 238.76, 279.4]):
        decouple("C%d" % (i + 1), (x, 264.16))

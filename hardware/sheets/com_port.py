"""COM port -- 16C550 UART + MAX3241 + DB9 (generic, instanced x2).

Design doc S11.1. ONE serial port; the harness instantiates this sheet twice
(COM1 0x3F8, COM2 0x2F8) via INSTANCES below. Each instance is configurable
via on-sheet jumpers: J2 (base-address strap, A8/~A8) and JP3 (port
enable/disable via CS1 gating). The IRQ is hardwired per instance (COM1 ->
IRQ4, COM2 -> IRQ3, the PC convention) through the COM_IRQ instance remap;
to reuse the IRQ for something else, disable the whole port with JP3.

Structure:
  * U1  16C550 UART (mini-xt:TL16C550PT, LQFP-48, soldered, +3V3) -- 8-bit ISA slave
  * U2  MAX3241 single-supply RS-232 transceiver (3 drivers + 5 receivers),
        +5V, unchanged (spec 2026-07-14: "already 3.3V"-compatible, no swap)
  * J1  DE9 male, full DTE port (TXD/RTS/DTR out; RXD/CTS/DSR/DCD/RI in)
  * J2  base-address strap (0x3F8 vs 0x2F8, selects A8 polarity in the decode)
  * J3  TTL console header tapped ahead of the MAX3241 (populated on COM1 only)
  * U3/U4/U5  address-decode glue (74HC04/74HC08 @ +3V3) -> active-low chip-select on ~{CS2}
  * U6  74LVC125A buffer gating INTRPT onto COM_IRQ under ~{OUT2}, +3V3
  * Y1  1.8432 MHz baud crystal on XIN/XOUT; ~{BAUDOUT} -> RCLK

3.3V single-board redesign (spec 2026-07-14): U1 replaces the old PLCC-44
socketed 16550 with a soldered 3.3V LQFP-48 part; U3-U6 move to +3V3. MAX3241
and the DE9/RS-232 side are untouched. Soft card: uses ISA bus signals +
power (isolation now a firmware-portability guideline, not a hard rule --
see mxbus.py).
"""
import mxbus
from mxbus import pin

NAME = "com_port"
TITLE = "COM port -- 16C550 UART + MAX3241 + DB9 (instanced x2)"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +        # A0..A9 (A0-A2 regs, A3-A9 decode)
    [pin(s, "bidirectional") for s in mxbus.DATA] +     # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "AEN", "RESET_DRV"]] +
    [pin("COM_IRQ", "output")]      # remapped per instance: COM1->IRQ4, COM2->IRQ3
)


def build(sch, lib, expose=True):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, rail="+5V"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ---------------- U1: 16C550 UART ----------------
    # Soldered LQFP-48, 3.3V (spec 2026-07-14 decision 3): PLCC-44 socket
    # deleted. mini-xt:TL16C550PT is the real TI LQFP-48 pinout (verified via
    # pins.py, NOT copied from the old DIP/PLCC-style symbol) -- pin NAMES are
    # the same UART signals, pin NUMBERS differ, and a few pins are renamed
    # (RD/WR active-high halves -> RD2/WR2, INTR -> INTRPT, GND -> VSS).
    U1 = sch.place("mini-xt:TL16C550PT", "U1", "TL16C550C", at=(127.0, 101.6))
    L(U1, "VCC", "+3V3", dx=0, dy=-2.54)
    L(U1, "VSS", "GND", dx=0, dy=2.54)
    # bus data + register-select address
    for i in range(8):
        L(U1, "D%d" % i, "D%d" % i, dx=-2.54)
    L(U1, "A0", "A0", dx=-2.54); L(U1, "A1", "A1", dx=-2.54); L(U1, "A2", "A2", dx=-2.54)
    # read/write strobes: use active-low ~{RD1}/~{WR1}, tie the active-high RD2/WR2 + ~{ADS} off
    L(U1, "~{RD1}", "~{IOR}", dx=-2.54)
    L(U1, "~{WR1}", "~{IOW}", dx=-2.54)
    L(U1, "RD2", "GND", dx=-2.54)
    L(U1, "WR2", "GND", dx=-2.54)
    L(U1, "~{ADS}", "GND", dx=-2.54)
    # chip select: CS0 high, CS1 gated by JP3, ~{CS2} = decoded address match (active low)
    L(U1, "CS0", "+3V3", dx=2.54)
    L(U1, "CS1", "COM_EN", dx=2.54)
    L(U1, "~{CS2}", "~{UART_CS}", dx=-2.54)
    # reset
    L(U1, "MR", "RESET_DRV", dx=-2.54)
    # baud reference: 1.8432 MHz CRYSTAL on the 16C550's own XIN/XOUT
    # oscillator -- unchanged at 3.3V (TL16C550C's on-chip oscillator runs the
    # same crystal at either supply; a crystal is supply-agnostic either way).
    # RX clock from internal ~{BAUDOUT}.
    L(U1, "XIN", "BAUD_XI", dx=-2.54)
    L(U1, "XOUT", "BAUD_XO", dx=2.54)
    L(U1, "RCLK", "BAUDOUT_N", dx=-2.54)
    L(U1, "~{BAUDOUT}", "BAUDOUT_N", dx=2.54)
    # modem control / status -> TTL side of MAX3241 (3.3V logic swing; the
    # MAX3241's TTL-side inputs read valid-high well below its own 5V VCC, see
    # questions-com_port.md)
    L(U1, "SOUT", "UART_TXD"); L(U1, "SIN", "UART_RXD")
    L(U1, "~{RTS}", "UART_RTS"); L(U1, "~{DTR}", "UART_DTR")
    L(U1, "~{CTS}", "UART_CTS"); L(U1, "~{DSR}", "UART_DSR")
    L(U1, "~{DCD}", "UART_DCD"); L(U1, "~{RI}", "UART_RI")
    # interrupt path: INTRPT (was INTR on the old symbol) gated onto COM_IRQ by ~{OUT2}
    L(U1, "INTRPT", "IRQ_RAW")
    L(U1, "~{OUT2}", "OUT2_N")
    for nc in ["~{OUT1}", "DDIS", "~{RXRDY}", "~{TXRDY}"]:
        sch.no_connect(U1.pin_xy(nc))
    # LQFP-48 has 8 NC pins the old DIP/PLCC symbol didn't need to model
    # (package has more pins than functional signals) -- tie all off by number.
    for nc in ["1", "6", "13", "21", "25", "36", "37", "48"]:
        sch.no_connect(U1.pin_xy(nc))

    # ---------------- baud reference crystal (XIN/XOUT) ----------------
    Y1 = sch.place("Device:Crystal", "Y1", "1.8432MHz", at=(60.96, 142.24))
    L(Y1, "1", "BAUD_XI", dx=-2.54)
    L(Y1, "2", "BAUD_XO", dx=2.54)
    cx1 = sch.place("Device:C", "C7", "22pF", at=(50.8, 154.94))
    L(cx1, "1", "BAUD_XI", dx=0, dy=-2.54); L(cx1, "2", "GND", dx=0, dy=2.54)
    cx2 = sch.place("Device:C", "C8", "22pF", at=(71.12, 154.94))
    L(cx2, "1", "BAUD_XO", dx=0, dy=-2.54); L(cx2, "2", "GND", dx=0, dy=2.54)

    # ---------------- address decode -> ~{UART_CS} ----------------
    # Match when A3..A7,A9 = 1, A8 = strap-selected, AEN = 0 (not a DMA cycle).
    # 0x3F8 and 0x2F8 differ only in A8; J2 jumpers A8 (3F8) or ~A8 (2F8) into A8_SEL.
    # 74HC04 value override: HC (not HCT) on the HCT body -- all inputs
    # (A8, AEN, this gate's own output) are 3.3V-driven now; 74HCT is out of
    # spec below 4.5V VCC.
    U3 = sch.place("mini-xt:74HCT04", "U3", "74HC04", at=(60.96, 198.12))     # inverters
    L(U3, "VCC", "+3V3", dx=0, dy=-2.54); L(U3, "GND", "GND", dx=0, dy=2.54)
    L(U3, "P1", "A8", dx=-2.54); L(U3, "P2", "A8_N")               # ~A8
    L(U3, "P3", "AEN", dx=-2.54); L(U3, "P4", "AEN_N")             # ~AEN
    L(U3, "P5", "ADDR_MATCH", dx=-2.54); L(U3, "P6", "~{UART_CS}") # ~(match)
    for ip in ["P9", "P11", "P13"]:
        L(U3, ip, "GND", dx=-2.54)
    for op in ["P8", "P10", "P12"]:
        sch.no_connect(U3.pin_xy(op))

    # base-address strap: Pin1=A8 (0x3F8), Pin2=A8_SEL, Pin3=~A8 (0x2F8)
    J2 = sch.place("Connector_Generic:Conn_01x03", "J2", at=(30.48, 167.64))
    L(J2, "Pin_1", "A8", dx=2.54)
    L(J2, "Pin_2", "A8_SEL", dx=2.54)
    L(J2, "Pin_3", "A8_N", dx=2.54)

    # 74HC08 value override (same rationale as U3): decode inputs are all
    # 3.3V-driven address/AEN lines.
    U4 = sch.place("mini-xt:74HCT08", "U4", "74HC08", at=(116.84, 198.12))    # AND, level 1
    L(U4, "VCC", "+3V3", dx=0, dy=-2.54); L(U4, "GND", "GND", dx=0, dy=2.54)
    L(U4, "P1", "A3", dx=-2.54); L(U4, "P2", "A4", dx=-2.54); L(U4, "P3", "AND1")
    L(U4, "P4", "A5", dx=-2.54); L(U4, "P5", "A6", dx=-2.54); L(U4, "P6", "AND2")
    L(U4, "P9", "A7", dx=-2.54); L(U4, "P10", "A9", dx=-2.54); L(U4, "P8", "AND3")
    L(U4, "P12", "A8_SEL", dx=-2.54); L(U4, "P13", "AEN_N", dx=-2.54); L(U4, "P11", "AND4")

    U5 = sch.place("mini-xt:74HCT08", "U5", "74HC08", at=(167.64, 198.12))    # AND, level 2/3
    L(U5, "VCC", "+3V3", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "P1", "AND1", dx=-2.54); L(U5, "P2", "AND2", dx=-2.54); L(U5, "P3", "AND5")
    L(U5, "P4", "AND3", dx=-2.54); L(U5, "P5", "AND4", dx=-2.54); L(U5, "P6", "AND6")
    L(U5, "P9", "AND5", dx=-2.54); L(U5, "P10", "AND6", dx=-2.54); L(U5, "P8", "ADDR_MATCH")
    L(U5, "P12", "GND", dx=-2.54); L(U5, "P13", "GND", dx=-2.54)   # spare gate
    sch.no_connect(U5.pin_xy("P11"))

    # ---------------- IRQ buffer (74LVC125A): INTRPT -> COM_IRQ, enabled by ~{OUT2} ----------------
    # 74LVC125A value override on the HCT125 body (spec 2026-07-14): tri-state
    # buffer driving a shared IRQ line -- LVC grade for 3.3V operation.
    U6 = sch.place("mini-xt:74HCT125", "U6", "74LVC125A", at=(132.08, 162.56))
    L(U6, "VCC", "+3V3", dx=0, dy=-2.54); L(U6, "GND", "GND", dx=0, dy=2.54)
    L(U6, "P1", "OUT2_N", dx=-2.54)        # ~OE = ~{OUT2}: tri-states IRQ when masked
    L(U6, "P2", "IRQ_RAW", dx=-2.54)
    L(U6, "P3", "COM_IRQ", dx=2.54)        # generic IRQ -> remapped to IRQ4/IRQ3
    for oe in ["P4", "P10", "P13"]:
        L(U6, oe, "+3V3", dx=-2.54)        # disable spare buffers
    for ip in ["P5", "P9", "P12"]:
        L(U6, ip, "GND", dx=-2.54)
    for op in ["P6", "P8", "P11"]:
        sch.no_connect(U6.pin_xy(op))

    # ---------------- U2: MAX3241 transceiver ----------------
    U2 = sch.place("mini-xt:MAX3241", "U2", at=(228.6, 101.6))
    L(U2, "VCC", "+5V", dx=0, dy=-2.54); L(U2, "GND", "GND", dx=0, dy=2.54)
    # TTL side <-> UART
    L(U2, "T1IN", "UART_TXD", dx=-2.54)
    L(U2, "T2IN", "UART_RTS", dx=-2.54)
    L(U2, "T3IN", "UART_DTR", dx=-2.54)
    L(U2, "R1OUT", "RXD_RS232", dx=-2.54)   # -> JP1: R1OUT is push-pull, so the
                                            # console TX must be jumper-selected,
                                            # never wire-OR'd onto UART_RXD
    L(U2, "R2OUT", "UART_CTS", dx=-2.54)
    L(U2, "R3OUT", "UART_DSR", dx=-2.54)
    L(U2, "R4OUT", "UART_DCD", dx=-2.54)
    L(U2, "R5OUT", "UART_RI", dx=-2.54)
    # RS-232 side <-> DB9
    L(U2, "T1OUT", "RS_TXD", dx=2.54)
    L(U2, "T2OUT", "RS_RTS", dx=2.54)
    L(U2, "T3OUT", "RS_DTR", dx=2.54)
    L(U2, "R1IN", "RS_RXD", dx=2.54)
    L(U2, "R2IN", "RS_CTS", dx=2.54)
    L(U2, "R3IN", "RS_DSR", dx=2.54)
    L(U2, "R4IN", "RS_DCD", dx=2.54)
    L(U2, "R5IN", "RS_RI", dx=2.54)
    # enable / status (real MAX3241 control set, verified vs LCSC C406859:
    # SHDN# high = transceiver running; EN# low = receiver outputs enabled;
    # R1OUTB/R2OUTB are the always-active wake-up receiver outputs, unused)
    L(U2, "~{SHDN}", "+5V", dx=-2.54)
    L(U2, "~{EN}", "GND", dx=-2.54)
    sch.no_connect(U2.pin_xy("R1OUTB"))
    sch.no_connect(U2.pin_xy("R2OUTB"))
    # charge pump caps (route vertically so adjacent pin stubs don't collide)
    L(U2, "C1+", "C1P", dx=0, dy=-2.54); L(U2, "C1-", "C1N", dx=0, dy=2.54)
    L(U2, "C2+", "C2P", dx=0, dy=-2.54); L(U2, "C2-", "C2N", dx=0, dy=2.54)
    L(U2, "V+", "MAX_VP", dx=0, dy=-2.54); L(U2, "V-", "MAX_VN", dx=0, dy=2.54)

    def cap(ref, val, at, na, nb):
        c = sch.place("Device:C", ref, val, at=at)
        sch.net(c, "1", na, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", nb, kind="label", dx=0, dy=2.54)

    # MAX3241 at 5V: C1=47nF, C2-C4=330nF (datasheet table); 100nF-everywhere was undersized
    cap("C3", "47nF", (251.46, 152.4), "C1P", "C1N")     # flying cap 1
    cap("C4", "330nF", (266.7, 152.4), "C2P", "C2N")      # flying cap 2
    cap("C5", "330nF", (281.94, 152.4), "MAX_VP", "GND")  # V+ reservoir
    cap("C6", "330nF", (297.18, 152.4), "MAX_VN", "GND")  # V- reservoir

    # ---------------- J1: DE9 male, full DTE ----------------
    J1 = sch.place("Connector:DE9_Pins", "J1", at=(330.2, 101.6))
    L(J1, "3", "RS_TXD", dx=2.54)   # TXD out
    L(J1, "7", "RS_RTS", dx=2.54)   # RTS out
    L(J1, "4", "RS_DTR", dx=2.54)   # DTR out
    L(J1, "2", "RS_RXD", dx=2.54)   # RXD in
    L(J1, "8", "RS_CTS", dx=2.54)   # CTS in
    L(J1, "6", "RS_DSR", dx=2.54)   # DSR in
    L(J1, "1", "RS_DCD", dx=2.54)   # DCD in
    L(J1, "9", "RS_RI", dx=2.54)    # RI in
    L(J1, "5", "GND", dx=2.54)      # signal ground

    # ---------------- J3: TTL console header (ahead of MAX3241) ----------------
    # Tapped on the UART TTL lines; populated on COM1 only (see design S11.1).
    # NOTE 3.3 V TTL levels now (U1 moved to +3V3, spec 2026-07-14) -- a plain
    # 5 V-only USB-serial adapter may not read these reliably; most 3.3 V
    # dongles are now the correct match. Pin 4 supplies +3V3 for a
    # self-powered adapter only.
    J3 = sch.place("Connector_Generic:Conn_01x04", "J3", at=(165.1, 254.0))
    L(J3, "Pin_1", "GND", dx=2.54)
    L(J3, "Pin_2", "UART_TXD", dx=2.54)   # board TX (TTL) out
    L(J3, "Pin_3", "CONSOLE_RXI", dx=2.54)  # console TX -> JP1 pin 3
    L(J3, "Pin_4", "+3V3", dx=2.54)

    # ---------------- JP1: UART RX source select ----------------
    # The MAX3241 R1OUT is PUSH-PULL, so the console adapter's TX cannot share
    # UART_RXD with it -- JP1 selects exactly one driver for the 16550's SIN:
    #   1-2 = DB9 (RS-232, via MAX3241)   2-3 = TTL console (J3)
    JP1 = sch.place("Connector_Generic:Conn_01x03", "JP1", at=(203.2, 254.0))
    L(JP1, "Pin_1", "RXD_RS232", dx=2.54)
    L(JP1, "Pin_2", "UART_RXD", dx=2.54)
    L(JP1, "Pin_3", "CONSOLE_RXI", dx=2.54)
    # SIN idles at mark if JP1 is left open (floating CMOS input otherwise);
    # pulled to +3V3 (not +5V) -- SIN is a 3.3V-VCC input on U1 now.
    R2 = sch.place("Device:R", "R2", "10k", at=(215.9, 236.22))
    L(R2, "1", "+3V3", dx=0, dy=-2.54); L(R2, "2", "UART_RXD", dx=0, dy=2.54)
    sch.text("J2 (base strap) has no default: it must ALWAYS be jumpered, or "
             "A8_SEL floats and the decode is undefined.", (203.2, 265.43))

    # ---------------- JP3: port enable ----------------
    # 16550 CS1 is a spare ACTIVE-HIGH select: jumper closed = port enabled,
    # open = R1 parks CS1 low and the UART can never be selected. IRQ needs no
    # extra gating -- MCR resets to 0, so ~OUT2 stays high and U6 stays Z.
    JP3 = sch.place("Connector_Generic:Conn_01x02", "JP3", "COM_EN", at=(256.54, 254.0))
    L(JP3, "Pin_1", "COM_EN", dx=2.54)
    L(JP3, "Pin_2", "+3V3", dx=2.54)     # CS1 is a 3.3V-VCC logic input on U1 now
    R1 = sch.place("Device:R", "R1", "10k", at=(271.78, 254.0))
    L(R1, "1", "COM_EN", dx=0, dy=-2.54)
    L(R1, "2", "GND", dx=0, dy=2.54)

    # ---------------- decoupling ----------------
    decouple("C1", (109.22, 50.8), rail="+3V3")   # U1
    decouple("C2", (210.82, 50.8))                # U2 (MAX3241, stays +5V -- untouched)
    decouple("C9", (60.96, 271.78), rail="+3V3")    # U3
    decouple("C10", (76.2, 271.78), rail="+3V3")    # U4
    decouple("C11", (91.44, 271.78), rail="+3V3")   # U5
    decouple("C12", (106.68, 271.78), rail="+3V3")  # U6
    C13 = sch.place("Device:C", "C13", "10uF", at=(121.92, 271.78))   # MAX3241 (+5V) bulk
    sch.net(C13, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(C13, "2", "GND", kind="label", dx=0, dy=2.54)
    C14 = sch.place("Device:C", "C14", "10uF", at=(137.16, 271.78))   # UART+glue (+3V3) bulk
    sch.net(C14, "1", "+3V3", kind="label", dx=0, dy=-2.54)
    sch.net(C14, "2", "GND", kind="label", dx=0, dy=2.54)

    sch.text("Base-address strap J2: jumper A8 (0x3F8/COM1) or ~A8 (0x2F8/COM2)",
             (60.96, 233.68))
    sch.text("TTL console header J3 (5V levels!): populate on COM1 only;", (165.1, 248.92))
    sch.text("JP1 selects UART RX source: 1-2 DB9, 2-3 console; IRQ hardwired per instance (COM1=IRQ4, COM2=IRQ3)",
             (165.1, 246.38))
    sch.text("JP3: jumper closed = port enabled, open = port disabled via CS1 pulldown (R1)",
             (165.1, 243.84))


INSTANCES = [("COM1", "", {"COM_IRQ": "IRQ4"}),     # hardwired PC convention;
             ("COM2", "B", {"COM_IRQ": "IRQ3"})]    # JP3 disables the whole port

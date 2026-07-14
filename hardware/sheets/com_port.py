"""COM1 + COM2 -- 2x 16C550 UART + MAX3241 + DB9, shared decode/IRQ glue.

Design doc S11.1. BOTH serial ports on one sheet (merged 2026-07-14; was one
generic sheet instanced twice). Merging lets the two ports share glue that a
per-instance copy had to duplicate:

  * ONE address decoder for both ports: 0x3F8 and 0x2F8 differ only in A8, so
    the common term (A3..A7,A9 = 1, AEN = 0) is built once and ANDed with A8
    (-> ~{UART_CS1}, COM1) or ~A8 (-> ~{UART_CS2}, COM2). 1x 74HC04 + 2x
    74HC08 total (was 2x04 + 4x08). Base addresses are HARDWIRED -- the old J2
    strap existed only because one generic sheet had to serve both addresses.
  * ONE 74LVC125A gates both IRQs (each port used 1 of its 4 buffers).

IRQs stay hardwired per the PC convention: COM1 -> IRQ4, COM2 -> IRQ3.

Structure (per port, suffix 1/2 on local nets):
  * U1/U3  16C550 UART (mini-xt:TL16C550PT, LQFP-48, soldered, +3V3)
  * U2/U4  MAX3241 single-supply RS-232 transceiver (3 drivers + 5 receivers),
           +3V3: rated 3.0-5.5V, makes valid RS-232 from 3.3V; caps sized to
           the datasheet 3.0-3.6V column. This sheet has no +5V rail.
  * J1/J2  DE9 male, full DTE port (TXD/RTS/DTR out; RXD/CTS/DSR/DCD/RI in)
  * Y1/Y2  1.8432 MHz baud crystal on XIN/XOUT; ~{BAUDOUT} -> RCLK
  * JP3/JP4  port enable (CS1 gating, pulldown parks it disabled when open)
Shared:
  * U5     74HC04: A8/AEN inverters + both ~{UART_CS} inverters
  * U6/U7  74HC08: common decode term + per-port A8/~A8 AND (all 8 gates used)
  * U8     74LVC125A: INTRPT -> IRQ4/IRQ3 under each port's ~{OUT2}
COM1 only:
  * J3     TTL console header tapped ahead of the MAX3241
  * JP1    UART RX source select (DB9 vs console; MAX R1OUT is push-pull)
COM2's RX is wired straight from its MAX3241 (no console -> no selector).

3.3V single-board redesign (spec 2026-07-14): soldered 3.3V LQFP-48 UART,
all glue at +3V3, MAX3241 at +3V3 (Task-10 fix). Soft card: uses ISA bus
signals + power only (isolation is a firmware-portability guideline now --
see mxbus.py).
"""
import mxbus
from mxbus import pin

NAME = "com_port"
TITLE = "COM1+COM2 -- 2x 16C550 UART + MAX3241 + DB9, shared decode"
PAPER = "A2"      # two full ports + shared glue outgrow A3

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +        # A0..A9 (A0-A2 regs, A3-A9 decode)
    [pin(s, "bidirectional") for s in mxbus.DATA] +     # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "AEN", "RESET_DRV"]] +
    [pin("IRQ4", "output"),     # COM1 (hardwired PC convention)
     pin("IRQ3", "output")]     # COM2
)


def build(sch, lib, expose=True):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, rail="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def cap(ref, val, at, na, nb):
        c = sch.place("Device:C", ref, val, at=at)
        sch.net(c, "1", na, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", nb, kind="label", dx=0, dy=2.54)

    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    def com_port(sfx, dy, uref, mref, jref, yref, cb, rxout_net):
        """One complete port: UART + crystal + MAX3241 + DE9 + decoupling.

        sfx: net-name suffix ("1"/"2"); dy: vertical block offset; cb: first
        cap ref number (uses C<cb>..C<cb+7>); rxout_net: where the MAX3241's
        push-pull R1OUT goes (COM1: to the JP1 selector; COM2: straight to SIN).
        """
        C = lambda i: "C%d" % (cb + i)

        # ---- 16C550 UART ----
        # Soldered LQFP-48, 3.3V (spec 2026-07-14 decision 3). mini-xt:TL16C550PT
        # is the real TI LQFP-48 pinout (verified via pins.py) -- vs the old
        # DIP/PLCC symbol, pin NUMBERS differ and a few pins are renamed
        # (RD/WR active-high halves -> RD2/WR2, INTR -> INTRPT, GND -> VSS).
        U = sch.place("mini-xt:TL16C550PT", uref, "TL16C550C", at=(127.0, 101.6 + dy))
        L(U, "VCC", "+3V3", dx=0, dy=-2.54)
        L(U, "VSS", "GND", dx=0, dy=2.54)
        # bus data + register-select address (shared ISA nets, no suffix)
        for i in range(8):
            L(U, "D%d" % i, "D%d" % i, dx=-2.54)
        L(U, "A0", "A0", dx=-2.54); L(U, "A1", "A1", dx=-2.54); L(U, "A2", "A2", dx=-2.54)
        # read/write strobes: use active-low ~{RD1}/~{WR1}, tie RD2/WR2 + ~{ADS} off
        L(U, "~{RD1}", "~{IOR}", dx=-2.54)
        L(U, "~{WR1}", "~{IOW}", dx=-2.54)
        L(U, "RD2", "GND", dx=-2.54)
        L(U, "WR2", "GND", dx=-2.54)
        L(U, "~{ADS}", "GND", dx=-2.54)
        # chip select: CS0 high, CS1 gated by the enable jumper, ~{CS2} = decode
        L(U, "CS0", "+3V3", dx=2.54)
        L(U, "CS1", "COM_EN" + sfx, dx=2.54)
        L(U, "~{CS2}", "~{UART_CS%s}" % sfx, dx=-2.54)
        L(U, "MR", "RESET_DRV", dx=-2.54)
        # baud reference: 1.8432 MHz crystal on the 16C550's own XIN/XOUT
        # oscillator (supply-agnostic); RX clock from internal ~{BAUDOUT}.
        L(U, "XIN", "BAUD_XI" + sfx, dx=-2.54)
        L(U, "XOUT", "BAUD_XO" + sfx, dx=2.54)
        L(U, "RCLK", "BAUDOUT%s_N" % sfx, dx=-2.54)
        L(U, "~{BAUDOUT}", "BAUDOUT%s_N" % sfx, dx=2.54)
        # modem control / status -> TTL side of MAX3241 (both at +3V3)
        L(U, "SOUT", "UART_TXD" + sfx); L(U, "SIN", "UART_RXD" + sfx)
        L(U, "~{RTS}", "UART_RTS" + sfx); L(U, "~{DTR}", "UART_DTR" + sfx)
        L(U, "~{CTS}", "UART_CTS" + sfx); L(U, "~{DSR}", "UART_DSR" + sfx)
        L(U, "~{DCD}", "UART_DCD" + sfx); L(U, "~{RI}", "UART_RI" + sfx)
        # interrupt path: INTRPT gated onto the ISA IRQ by ~{OUT2} via U8
        L(U, "INTRPT", "IRQ_RAW" + sfx)
        L(U, "~{OUT2}", "OUT2_N" + sfx)
        for nc in ["~{OUT1}", "DDIS", "~{RXRDY}", "~{TXRDY}"]:
            sch.no_connect(U.pin_xy(nc))
        # LQFP-48 has 8 NC package pins -- tie off by number.
        for nc in ["1", "6", "13", "21", "25", "36", "37", "48"]:
            sch.no_connect(U.pin_xy(nc))

        # ---- baud reference crystal ----
        Y = sch.place("Device:Crystal", yref, "1.8432MHz", at=(60.96, 142.24 + dy))
        L(Y, "1", "BAUD_XI" + sfx, dx=-2.54)
        L(Y, "2", "BAUD_XO" + sfx, dx=2.54)
        cap(C(6), "22pF", (50.8, 154.94 + dy), "BAUD_XI" + sfx, "GND")
        cap(C(7), "22pF", (71.12, 154.94 + dy), "BAUD_XO" + sfx, "GND")

        # ---- MAX3241 transceiver ----
        # +3V3 (Task-10 fix): rated 3.0-5.5V, valid RS-232 swings from 3.3V via
        # its charge pumps; matches the UART's 3.3V TTL side.
        M = sch.place("mini-xt:MAX3241", mref, at=(228.6, 101.6 + dy))
        L(M, "VCC", "+3V3", dx=0, dy=-2.54); L(M, "GND", "GND", dx=0, dy=2.54)
        # TTL side <-> UART
        L(M, "T1IN", "UART_TXD" + sfx, dx=-2.54)
        L(M, "T2IN", "UART_RTS" + sfx, dx=-2.54)
        L(M, "T3IN", "UART_DTR" + sfx, dx=-2.54)
        L(M, "R1OUT", rxout_net, dx=-2.54)
        L(M, "R2OUT", "UART_CTS" + sfx, dx=-2.54)
        L(M, "R3OUT", "UART_DSR" + sfx, dx=-2.54)
        L(M, "R4OUT", "UART_DCD" + sfx, dx=-2.54)
        L(M, "R5OUT", "UART_RI" + sfx, dx=-2.54)
        # RS-232 side <-> DB9
        L(M, "T1OUT", "RS_TXD" + sfx, dx=2.54)
        L(M, "T2OUT", "RS_RTS" + sfx, dx=2.54)
        L(M, "T3OUT", "RS_DTR" + sfx, dx=2.54)
        L(M, "R1IN", "RS_RXD" + sfx, dx=2.54)
        L(M, "R2IN", "RS_CTS" + sfx, dx=2.54)
        L(M, "R3IN", "RS_DSR" + sfx, dx=2.54)
        L(M, "R4IN", "RS_DCD" + sfx, dx=2.54)
        L(M, "R5IN", "RS_RI" + sfx, dx=2.54)
        # enable / status (real MAX3241 control set, verified vs LCSC C406859:
        # SHDN# high = running; EN# low = receiver outputs enabled;
        # R1OUTB/R2OUTB are the always-active wake-up outputs, unused)
        L(M, "~{SHDN}", "+3V3", dx=-2.54)
        L(M, "~{EN}", "GND", dx=-2.54)
        sch.no_connect(M.pin_xy("R1OUTB"))
        sch.no_connect(M.pin_xy("R2OUTB"))
        # charge pump caps (vertical stubs so adjacent pin stubs don't collide);
        # datasheet 3.0-3.6V column: all four caps 0.1uF
        L(M, "C1+", "C1P" + sfx, dx=0, dy=-2.54); L(M, "C1-", "C1N" + sfx, dx=0, dy=2.54)
        L(M, "C2+", "C2P" + sfx, dx=0, dy=-2.54); L(M, "C2-", "C2N" + sfx, dx=0, dy=2.54)
        L(M, "V+", "MAX_VP" + sfx, dx=0, dy=-2.54); L(M, "V-", "MAX_VN" + sfx, dx=0, dy=2.54)
        cap(C(2), "100nF", (251.46, 152.4 + dy), "C1P" + sfx, "C1N" + sfx)
        cap(C(3), "100nF", (266.7, 152.4 + dy), "C2P" + sfx, "C2N" + sfx)
        cap(C(4), "100nF", (281.94, 152.4 + dy), "MAX_VP" + sfx, "GND")
        cap(C(5), "100nF", (297.18, 152.4 + dy), "MAX_VN" + sfx, "GND")

        # ---- DE9 male, full DTE ----
        J = sch.place("Connector:DE9_Pins", jref, at=(330.2, 101.6 + dy))
        L(J, "3", "RS_TXD" + sfx, dx=2.54)   # TXD out
        L(J, "7", "RS_RTS" + sfx, dx=2.54)   # RTS out
        L(J, "4", "RS_DTR" + sfx, dx=2.54)   # DTR out
        L(J, "2", "RS_RXD" + sfx, dx=2.54)   # RXD in
        L(J, "8", "RS_CTS" + sfx, dx=2.54)   # CTS in
        L(J, "6", "RS_DSR" + sfx, dx=2.54)   # DSR in
        L(J, "1", "RS_DCD" + sfx, dx=2.54)   # DCD in
        L(J, "9", "RS_RI" + sfx, dx=2.54)    # RI in
        L(J, "5", "GND", dx=2.54)            # signal ground

        # ---- decoupling ----
        decouple(C(0), (109.22, 50.8 + dy))    # UART
        decouple(C(1), (210.82, 50.8 + dy))    # MAX3241

    # ================ port 1 (COM1, 0x3F8, IRQ4) ================
    com_port("1", 0, "U1", "U2", "J1", "Y1", 1, "RXD_RS232")
    # ================ port 2 (COM2, 0x2F8, IRQ3) ================
    # No console header on COM2, so its MAX3241 R1OUT drives SIN directly.
    com_port("2", 152.4, "U3", "U4", "J2", "Y2", 9, "UART_RXD2")

    # ---------------- shared address decode -> ~{UART_CS1}/~{UART_CS2} ----------------
    # Both ports match on A3..A7,A9 = 1, AEN = 0 (not a DMA cycle); they differ
    # only in A8: 1 -> 0x3F8 (COM1), 0 -> 0x2F8 (COM2). The common term is built
    # once and ANDed with A8 / ~A8 -- HARDWIRED (the old J2 base-address strap
    # only existed because one generic sheet was instanced at both addresses).
    # 74HC04/74HC08 value overrides: HC (not HCT) on the HCT bodies -- every
    # input is 3.3V-driven; 74HCT is out of spec below 4.5V VCC.
    U5 = sch.place("mini-xt:74HCT04", "U5", "74HC04", at=(60.96, 340.36))     # inverters
    L(U5, "VCC", "+3V3", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "P1", "A8", dx=-2.54); L(U5, "P2", "A8_N")                   # ~A8
    L(U5, "P3", "AEN", dx=-2.54); L(U5, "P4", "AEN_N")                 # ~AEN
    L(U5, "P5", "ADDR_MATCH1", dx=-2.54); L(U5, "P6", "~{UART_CS1}")   # ~(COM1 match)
    L(U5, "P9", "ADDR_MATCH2", dx=-2.54); L(U5, "P8", "~{UART_CS2}")   # ~(COM2 match)
    for ip in ["P11", "P13"]:
        L(U5, ip, "GND", dx=-2.54)
    for op in ["P10", "P12"]:
        sch.no_connect(U5.pin_xy(op))

    U6 = sch.place("mini-xt:74HCT08", "U6", "74HC08", at=(116.84, 340.36))    # AND, level 1
    L(U6, "VCC", "+3V3", dx=0, dy=-2.54); L(U6, "GND", "GND", dx=0, dy=2.54)
    L(U6, "P1", "A3", dx=-2.54); L(U6, "P2", "A4", dx=-2.54); L(U6, "P3", "AND1")
    L(U6, "P4", "A5", dx=-2.54); L(U6, "P5", "A6", dx=-2.54); L(U6, "P6", "AND2")
    L(U6, "P9", "A7", dx=-2.54); L(U6, "P10", "A9", dx=-2.54); L(U6, "P8", "AND3")
    L(U6, "P12", "AND1", dx=-2.54); L(U6, "P13", "AND2", dx=-2.54); L(U6, "P11", "AND4")

    U7 = sch.place("mini-xt:74HCT08", "U7", "74HC08", at=(172.72, 340.36))    # AND, level 2/3
    L(U7, "VCC", "+3V3", dx=0, dy=-2.54); L(U7, "GND", "GND", dx=0, dy=2.54)
    L(U7, "P1", "AND3", dx=-2.54); L(U7, "P2", "AEN_N", dx=-2.54); L(U7, "P3", "AND5")
    L(U7, "P4", "AND4", dx=-2.54); L(U7, "P5", "AND5", dx=-2.54); L(U7, "P6", "COM_DEC")
    L(U7, "P9", "COM_DEC", dx=-2.54); L(U7, "P10", "A8", dx=-2.54); L(U7, "P8", "ADDR_MATCH1")
    L(U7, "P12", "COM_DEC", dx=-2.54); L(U7, "P13", "A8_N", dx=-2.54); L(U7, "P11", "ADDR_MATCH2")

    # ---------------- shared IRQ buffer (74LVC125A) ----------------
    # One quad tri-state buffer gates BOTH ports' INTRPT onto the ISA IRQs
    # under each port's ~{OUT2} (the PC serial-card convention: software masks
    # the IRQ by clearing OUT2, tri-stating the shared line). 74LVC125A value
    # override on the HCT125 body: LVC grade for 3.3V operation.
    U8 = sch.place("mini-xt:74HCT125", "U8", "74LVC125A", at=(228.6, 340.36))
    L(U8, "VCC", "+3V3", dx=0, dy=-2.54); L(U8, "GND", "GND", dx=0, dy=2.54)
    L(U8, "P1", "OUT2_N1", dx=-2.54)       # ~OE: tri-states IRQ4 when masked
    L(U8, "P2", "IRQ_RAW1", dx=-2.54)
    L(U8, "P3", "IRQ4", dx=2.54)           # COM1
    L(U8, "P4", "OUT2_N2", dx=-2.54)       # ~OE: tri-states IRQ3 when masked
    L(U8, "P5", "IRQ_RAW2", dx=-2.54)
    L(U8, "P6", "IRQ3", dx=2.54)           # COM2
    for oe in ["P10", "P13"]:
        L(U8, oe, "+3V3", dx=-2.54)        # disable spare buffers
    for ip in ["P9", "P12"]:
        L(U8, ip, "GND", dx=-2.54)
    for op in ["P8", "P11"]:
        sch.no_connect(U8.pin_xy(op))

    # ---------------- J3: TTL console header (COM1 only, ahead of MAX3241) ----------------
    # 3.3V TTL levels -- a 5V-only USB-serial adapter may not read these
    # reliably; most 3.3V dongles are the correct match. Pin 4 supplies +3V3
    # for a self-powered adapter only.
    J3 = sch.place("Connector_Generic:Conn_01x04", "J3", at=(287.02, 340.36))
    L(J3, "Pin_1", "GND", dx=2.54)
    L(J3, "Pin_2", "UART_TXD1", dx=2.54)     # board TX (TTL) out
    L(J3, "Pin_3", "CONSOLE_RXI", dx=2.54)   # console TX -> JP1 pin 3
    L(J3, "Pin_4", "+3V3", dx=2.54)

    # ---------------- JP1: COM1 UART RX source select ----------------
    # The MAX3241 R1OUT is PUSH-PULL, so the console adapter's TX cannot share
    # UART_RXD1 with it -- JP1 selects exactly one driver for the 16550's SIN:
    #   1-2 = DB9 (RS-232, via MAX3241)   2-3 = TTL console (J3)
    JP1 = sch.place("Connector_Generic:Conn_01x03", "JP1", at=(322.58, 340.36))
    L(JP1, "Pin_1", "RXD_RS232", dx=2.54)
    L(JP1, "Pin_2", "UART_RXD1", dx=2.54)
    L(JP1, "Pin_3", "CONSOLE_RXI", dx=2.54)
    # SIN idles at mark if JP1 is left open (floating CMOS input otherwise).
    # COM2 needs no pull-up: its SIN is driven push-pull by its MAX3241.
    R3 = sch.place("Device:R", "R3", "10k", at=(335.28, 322.58))
    L(R3, "1", "+3V3", dx=0, dy=-2.54); L(R3, "2", "UART_RXD1", dx=0, dy=2.54)

    # ---------------- JP3/JP4: port enables ----------------
    # 16550 CS1 is a spare ACTIVE-HIGH select: jumper closed = port enabled,
    # open = pulldown parks CS1 low and the UART can never be selected. IRQ
    # needs no extra gating -- MCR resets to 0, so ~OUT2 stays high and U8's
    # buffer stays Z.
    JP3 = sch.place("Connector_Generic:Conn_01x02", "JP3", "COM1_EN", at=(287.02, 373.38))
    L(JP3, "Pin_1", "COM_EN1", dx=2.54)
    L(JP3, "Pin_2", "+3V3", dx=2.54)
    R1 = sch.place("Device:R", "R1", "10k", at=(311.15, 373.38))
    L(R1, "1", "COM_EN1", dx=0, dy=-2.54)
    L(R1, "2", "GND", dx=0, dy=2.54)
    JP4 = sch.place("Connector_Generic:Conn_01x02", "JP4", "COM2_EN", at=(330.2, 373.38))
    L(JP4, "Pin_1", "COM_EN2", dx=2.54)
    L(JP4, "Pin_2", "+3V3", dx=2.54)
    R2 = sch.place("Device:R", "R2", "10k", at=(353.06, 373.38))
    L(R2, "1", "COM_EN2", dx=0, dy=-2.54)
    L(R2, "2", "GND", dx=0, dy=2.54)

    # ---------------- shared-glue decoupling + rail bulk ----------------
    decouple("C17", (60.96, 322.58))    # U5
    decouple("C18", (76.2, 322.58))     # U6
    decouple("C19", (91.44, 322.58))    # U7
    decouple("C20", (106.68, 322.58))   # U8
    cap("C21", "10uF", (386.08, 340.36), "+3V3", "GND")   # MAX3241 pair bulk
    cap("C22", "10uF", (401.32, 340.36), "+3V3", "GND")   # UART + glue bulk

    sch.text("Base addresses hardwired: COM1 0x3F8 (A8 AND), COM2 0x2F8 (~A8 AND); "
             "IRQs hardwired COM1=IRQ4, COM2=IRQ3", (60.96, 375.92))
    sch.text("JP1 selects COM1 UART RX source: 1-2 DB9, 2-3 TTL console (J3, 3.3V levels)",
             (60.96, 378.46))
    sch.text("JP3/JP4: jumper closed = port enabled, open = port disabled via CS1 pulldown",
             (60.96, 381.0))

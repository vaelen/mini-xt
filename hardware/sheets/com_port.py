"""COM1 + COM2 -- 2x 16C550 UART + MAX3241 + DB9, shared IRQ glue.

Design doc S11.1. BOTH serial ports on one sheet (merged 2026-07-14; was one
generic sheet instanced twice). Address decode is CENTRAL since the
addr_decode sheet landed (2026-07-14, chip-count reduction): the interface
takes ready-made active-low ~{COM1_CS}/~{COM2_CS} (0x3F8/0x2F8, AEN-gated)
straight into each UART's ~{CS2}, so this sheet keeps NO decode gates at all
(the merge-era 74HC04 + 2x 74HC08 moved to addr_decode and shrank there).
A0-A2 still come in for the 16550's own register select.

The IRQ stage and the enable jumpers are central too (same sheet, same day):
each UART exports its raw INTRPT (IRQ_COMx) and ~{OUT2} (~{COMx_IRQEN}) on
private nets (mxbus.PRIV_IRQREQ); addr_decode's shared 74LVC125A drives
IRQ4/IRQ3 from them (the PC convention -- OUT2 still software-gates the
line), and its DIS_COMx jumpers (addr_decode JP1/JP2) replace the old
on-sheet enables (sense inverted: enabled by default, fit to disable). This sheet is
just the ports now: no decode, no IRQ driver, no straps.

Structure (per port, suffix 1/2 on local nets):
  * U1/U3  16C550 UART (mini-xt:TL16C550PT, TQFP-48, soldered, +3V3)
  * U2/U4  MAX3241 single-supply RS-232 transceiver (3 drivers + 5 receivers),
           +3V3: rated 3.0-5.5V, makes valid RS-232 from 3.3V; caps sized to
           the datasheet 3.0-3.6V column. This sheet has no +5V rail.
  * J1/J2  DE9 male, full DTE port (TXD/RTS/DTR out; RXD/CTS/DSR/DCD/RI in)
  * Y1/Y2  1.8432 MHz baud crystal on XIN/XOUT; ~{BAUDOUT} -> RCLK
COM1 only:
  * J3     TTL console header tapped ahead of the MAX3241
  * JP1    UART RX source select (DB9 vs console; MAX R1OUT is push-pull)
COM2's RX is wired straight from its MAX3241 (no console -> no selector).

3.3V single-board redesign (spec 2026-07-14): soldered 3.3V TQFP-48 UART
(TL16C550CPFBR since later that day -- the PTR is dead/stockless; parts.py
binds it, pinout verified identical), MAX3241 at +3V3 (Task-10 fix).
"""
import mxbus
from mxbus import pin

NAME = "com_port"
TITLE = "COM1+COM2 -- 2x 16C550 UART + MAX3241 + DB9"
PAPER = "A2"      # two full ports outgrow A3

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:3]] +         # A0..A2 (register select)
    [pin(s, "bidirectional") for s in mxbus.DATA] +     # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "RESET_DRV",
                               "~{COM1_CS}", "~{COM2_CS}"]] +  # central decode (addr_decode)
    [pin("IRQ_COM1", "output"),         # raw INTRPT -> addr_decode's '125 -> IRQ4
     pin("IRQ_COM2", "output"),         # raw INTRPT -> addr_decode's '125 -> IRQ3
     pin("~{COM1_IRQEN}", "output"),    # ~{OUT2} = the '125 channel's ~OE
     pin("~{COM2_IRQEN}", "output")]
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
        # Soldered 48-pin QFP, 3.3V (spec 2026-07-14 decision 3). The symbol
        # is the real TI 48-QFP pinout, re-verified pin-for-pin against the
        # TL16C550CPFBR (LCSC C882798, EasyEDA) now bound in parts.py -- vs
        # the old DIP/PLCC symbol, pin NUMBERS differ and a few pins are
        # renamed (RD/WR halves -> RD2/WR2, INTR -> INTRPT, GND -> VSS).
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
        # chip select: CS0/CS1 strapped high; ~{CS2} straight from the central
        # decoder, whose DIS_COMx jumper is also the port's disable
        L(U, "CS0", "+3V3", dx=2.54)
        L(U, "CS1", "+3V3", dx=2.54)
        L(U, "~{CS2}", "~{COM%s_CS}" % sfx, dx=-2.54)
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
        # interrupt path: raw INTRPT + ~{OUT2} export to addr_decode's shared
        # '125, which gates INTRPT onto the ISA IRQ under ~{OUT2}
        L(U, "INTRPT", "IRQ_COM" + sfx)
        L(U, "~{OUT2}", "~{COM%s_IRQEN}" % sfx)
        for nc in ["~{OUT1}", "DDIS", "~{RXRDY}", "~{TXRDY}"]:
            sch.no_connect(U.pin_xy(nc))
        # the 48-QFP package has 8 NC pins -- tie off by number.
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

    # ---------------- rail bulk ----------------
    cap("C17", "10uF", (386.08, 340.36), "+3V3", "GND")   # MAX3241 pair bulk
    cap("C18", "10uF", (401.32, 340.36), "+3V3", "GND")   # UART pair bulk

    sch.text("Chip selects, IRQ mapping (COM1=IRQ4, COM2=IRQ3) and the disable "
             "jumpers all live on the addr_decode sheet", (60.96, 375.92))
    sch.text("JP1 selects COM1 UART RX source: 1-2 DB9, 2-3 TTL console (J3, 3.3V levels)",
             (60.96, 378.46))

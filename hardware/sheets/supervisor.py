"""supervisor -- Supervisor MCU (RP2040): USB HID host, setup UI, config/BIOS-image
flash, POST display, console. OFF the system bus (design doc S5/S5.3/S6/S11.4/S12).

The Supervisor is the "slow brain": it owns the USB stack, the pre-BIOS setup menu,
persistent config + BIOS/option-ROM images (QSPI flash), the console UART and the
2-digit POST display. It never touches the ISA bus -- its ONLY tie to the rest of the
board is a 2-wire full-duplex UART link to the Bus MCU plus the static speed-select
line it sets before reset release. Everything else (USB jack, POST display, console)
terminates at on-sheet connectors and stays LOCAL -- that small interface is the whole
point of the two-MCU split, so only the link + speed-select are hierarchical pins.

Cross-sheet interface (PINS):
  * LINK_B2S  (in)  -- Bus MCU -> Supervisor UART (POST codes, CMOS-write acks)
  * LINK_S2B  (out) -- Supervisor -> Bus MCU UART (HID events, menu draw, image push)
  * +5V is a GLOBAL power net (USB VBUS source); it arrives via the power symbol, not
    a hier pin.
"""
import mxbus
from mxbus import pin

NAME = "supervisor"
TITLE = "Supervisor MCU (RP2040) -- USB host, setup UI, config/flash, POST, console"

# Small, deliberate interface: only the 2-wire UART link crosses the sheet
# boundary. USB / POST / console are local (terminate at connectors here).
PINS = [
    pin("LINK_B2S", "input"),
    pin("LINK_S2B", "output"),
]


def build(sch, lib):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, rail="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # cross-sheet interface (the two-MCU split contract)
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ---------------- Supervisor MCU ----------------
    U1 = sch.place("MCU_RaspberryPi:RP2040", "U1", at=(177.8, 127.0))
    # IO / analog / USB supplies -> 3V3 (all duplicate IOVDD pins wired by number)
    for n in ("1", "10", "22", "33", "42", "49"):       # IOVDD
        L(U1, n, "+3V3", dx=0, dy=-2.54)
    L(U1, "43", "+3V3", dx=0, dy=-2.54)                  # ADC_AVDD
    L(U1, "48", "+3V3", dx=0, dy=-2.54)                  # USB_VDD
    L(U1, "44", "+3V3", dx=0, dy=-2.54)                  # VREG_VIN (core LDO input)
    # internal core LDO: VREG_VOUT (1.1V) feeds DVDD
    L(U1, "45", "VCORE", dx=2.54)                        # VREG_VOUT
    L(U1, "23", "VCORE", dx=0, dy=2.54)                  # DVDD
    L(U1, "50", "VCORE", dx=0, dy=2.54)                  # DVDD
    L(U1, "57", "GND", dx=0, dy=2.54)                    # GND
    L(U1, "19", "GND", dx=-2.54)                         # TESTEN -> GND (factory test)

    # crystal oscillator (12 MHz, RP2040 reference clock)
    L(U1, "XIN", "XTAL_IN", dx=-2.54)
    L(U1, "XOUT", "XTAL_OUT", dx=-2.54)
    Y1 = sch.place("Device:Crystal", "Y1", "12MHz", at=(127.0, 190.5))
    L(Y1, "1", "XTAL_IN", dx=-2.54)
    L(Y1, "2", "XTAL_OUT", dx=2.54)
    cx1 = sch.place("Device:C", "C1", "15pF", at=(116.84, 203.2))
    L(cx1, "1", "XTAL_IN", dx=0, dy=-2.54); L(cx1, "2", "GND", dx=0, dy=2.54)
    cx2 = sch.place("Device:C", "C2", "15pF", at=(137.16, 203.2))
    L(cx2, "1", "XTAL_OUT", dx=0, dy=-2.54); L(cx2, "2", "GND", dx=0, dy=2.54)

    # RUN (reset): pull-up + delay cap
    L(U1, "26", "RUN", dx=2.54)
    rrun = sch.place("Device:R", "R1", "10k", at=(228.6, 76.2))
    L(rrun, "1", "RUN", dx=0, dy=2.54); L(rrun, "2", "+3V3", dx=0, dy=-2.54)
    crun = sch.place("Device:C", "C3", "1uF", at=(241.3, 76.2))
    L(crun, "1", "RUN", dx=0, dy=2.54); L(crun, "2", "GND", dx=0, dy=-2.54)

    # ---------------- QSPI flash (firmware + BIOS / option-ROM images) ----------------
    # No QSPI-flash symbol exists in the available libs (see questions); represented as
    # an 8-pin footprint header: CS, SCLK, SD0..SD3, +3V3, GND.
    L(U1, "56", "QSPI_CS", dx=2.54)          # ~{QSPI_SS}
    L(U1, "52", "QSPI_SCLK", dx=2.54)
    L(U1, "53", "QSPI_SD0", dx=2.54)
    L(U1, "55", "QSPI_SD1", dx=2.54)
    L(U1, "54", "QSPI_SD2", dx=2.54)
    L(U1, "51", "QSPI_SD3", dx=2.54)
    JF = sch.place("Connector_Generic:Conn_01x08", "J1", "QSPI_FLASH", at=(279.4, 76.2))
    for pn, net in [("1", "QSPI_CS"), ("2", "QSPI_SCLK"), ("3", "QSPI_SD0"),
                    ("4", "QSPI_SD1"), ("5", "QSPI_SD2"), ("6", "QSPI_SD3")]:
        L(JF, pn, net, dx=2.54)
    L(JF, "7", "+3V3", dx=2.54)
    L(JF, "8", "GND", dx=2.54)
    decouple("C4", (279.4, 50.8))   # flash decoupling

    # ---------------- USB-A host jack (keyboard / hub) ----------------
    JU = sch.place("Connector:USB_A", "J2", "USB_HOST", at=(63.5, 101.6))
    L(JU, "VBUS", "+5V", dx=-2.54)          # 5V sources downstream USB device
    L(JU, "D+", "USB_DP", dx=-2.54)
    L(JU, "D-", "USB_DM", dx=-2.54)
    L(JU, "GND", "GND", dx=-2.54)
    L(JU, "Shield", "GND", dx=-2.54)
    # native USB PHY pins
    L(U1, "USB_DP", "USB_DP", dx=-2.54)
    L(U1, "USB_DM", "USB_DM", dx=-2.54)

    # ---------------- 2-digit hex POST display ----------------
    # POST_A..G + DP segment lines and two digit-select lines, driven from GPIO.
    # No 7-seg symbol in libs (see questions): a 10-pin display header carries them.
    post = [("GPIO6", "POST_A"), ("GPIO7", "POST_B"), ("GPIO8", "POST_C"),
            ("GPIO9", "POST_D"), ("GPIO10", "POST_E"), ("GPIO11", "POST_F"),
            ("GPIO12", "POST_G"), ("GPIO13", "POST_DP"),
            ("GPIO14", "POST_DIG0"), ("GPIO15", "POST_DIG1")]
    for gpio, net in post:
        L(U1, gpio, net, dx=2.54)
    JP = sch.place("Connector_Generic:Conn_01x10", "J3", "POST_HEX", at=(279.4, 152.4))
    for i, (_, net) in enumerate(post):
        L(JP, str(i + 1), net, dx=2.54)

    # ---------------- console (3-pin TTL UART header) ----------------
    L(U1, "GPIO0", "CONSOLE_TX", dx=-2.54)   # UART0 TX
    L(U1, "GPIO1", "CONSOLE_RX", dx=-2.54)   # UART0 RX
    JC = sch.place("Connector_Generic:Conn_01x03", "J4", "CONSOLE", at=(279.4, 215.9))
    L(JC, "1", "CONSOLE_TX", dx=2.54)
    L(JC, "2", "CONSOLE_RX", dx=2.54)
    L(JC, "3", "GND", dx=2.54)

    # ---------------- UART link to Bus MCU (the only data tie off-sheet) ----------------
    # GPIO4/5 are a real UART1 TX/RX pair (GPIO2/3 are only UART0 CTS/RTS on
    # the RP2040 -- a link there would force a PIO UART). POST segments moved
    # to GPIO6-15 to free these.
    L(U1, "GPIO4", "LINK_S2B", dx=-2.54)     # UART1 TX -> Bus MCU (out)
    L(U1, "GPIO5", "LINK_B2S", dx=-2.54)     # UART1 RX <- Bus MCU (in)

    # ---------------- speed-select latch (static, set before reset release) ----------
    # speed-select moved to the Bus MCU: the Supervisor now sends the chosen
    # CPU divisor to the Bus MCU over the UART link (no SPEED_SEL pin here).

    # ---------------- SWD debug header (bring-up aid, local) ----------------
    L(U1, "SWCLK", "SWCLK", dx=2.54)
    L(U1, "SWDIO", "SWDIO", dx=2.54)
    JS = sch.place("Connector_Generic:Conn_01x03", "J5", "SWD", at=(101.6, 76.2))
    L(JS, "1", "SWDIO", dx=-2.54)
    L(JS, "2", "SWCLK", dx=-2.54)
    L(JS, "3", "GND", dx=-2.54)

    # ---------------- decoupling ----------------
    decouple("C5", (101.6, 248.92), rail="VCORE")        # core (VCORE) decouple
    cbulk = sch.place("Device:C", "C6", "10uF", at=(127.0, 248.92))  # VCORE bulk
    sch.net(cbulk, "1", "VCORE", kind="label", dx=0, dy=-2.54)
    sch.net(cbulk, "2", "GND", kind="label", dx=0, dy=2.54)
    for i, x in enumerate(range(60, 300, 40)):
        decouple("C%d" % (7 + i), (float(x), 270.0))     # 3V3 rail decoupling

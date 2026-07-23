"""supervisor -- Supervisor MCU (RP2040): USB HID host, setup UI, config/BIOS-image
flash, POST display, console. OFF the system bus (design doc S5/S5.3/S6/S11.4/S12).

The Supervisor is the "slow brain": it owns the USB stack, the pre-BIOS setup menu,
persistent config + BIOS/option-ROM images (QSPI flash), the console UART and the
2-digit POST display. It never touches the ISA bus -- its ONLY tie to the rest of the
board is a 2-wire full-duplex UART link to the Bus MCU plus the static speed-select
line it sets before reset release. Everything else (USB jack, POST display, console)
terminates at on-sheet connectors and stays LOCAL -- that small interface is the whole
point of the two-MCU split, so only the link + speed-select are hierarchical pins.

USB host port hardened with RP2040-required 27R series termination on D+/D-, a
USBLC6-2SC6 ESD array at the jack, and 100uF bulk on VBUS_KBD (USB hosts must supply
>=120uF-class bulk for downstream inrush). GPIO16 reads PD_PG from the power sheet
(CH224K power-good) so setup can warn when only default-USB current is available.

Crystal drive per RP2040 minimal design (PicoGUS/RPi pattern): 30pF load caps
(crystal CL=20pF) + 1k series on XOUT (R4) for damping. BOOTSEL button (SW1 + R5
pull-up on QSPI_CS) enables USB bootloader entry at power-up (Supervisor is now
USB-flashable). Shared programming port (J6 USB-C) + DPDT selector (SW2) allows
one device-mode USB port to flash either the Supervisor RP2040 or the PicoGUS
RP2040: position A selects this chip (shares PHY with host jack -- unplug keyboard
to flash), position B selects PicoGUS via isolated PGUS_USB_DP/DM. J6 VBUS is
deliberately unconnected so the board must be powered to flash (no back-power paths).

Cross-sheet interface (PINS):
  * LINK_B2S       (in)  -- Bus MCU -> Supervisor UART (POST codes, CMOS-write acks)
  * LINK_S2B       (out) -- Supervisor -> Bus MCU UART (HID events, menu draw, image push)
  * PD_PG          (in)  -- Power sheet CH224K power-good (open-drain, 3V3 pull-up)
  * PGUS_USB_DP    (bidi) -- Shared programming port selector -> PicoGUS DP (SW2 pos B)
  * PGUS_USB_DM    (bidi) -- Shared programming port selector -> PicoGUS DM (SW2 pos B)
  * +5V is a GLOBAL power net (USB VBUS source); it arrives via the power symbol, not
    a hier pin.
"""
import mxbus
from mxbus import pin

NAME = "supervisor"
TITLE = "Supervisor MCU (RP2040) -- USB host, setup UI, config/flash, POST, console, shared prog port"

# Small, deliberate interface: only the 2-wire UART link crosses the sheet
# boundary. USB / POST / console are local (terminate at connectors here).
# PGUS_USB_DP/DM cross to the picogus sheet (shared programming port selector).
PINS = [
    pin("LINK_B2S", "input"),
    pin("LINK_S2B", "output"),
    pin("PD_PG", "input"),
    pin("PGUS_USB_DP", "bidirectional"),
    pin("PGUS_USB_DM", "bidirectional"),
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
    # Crystal drive per RP2040 minimal design: 30pF load caps (crystal CL=20pF)
    # + 1k series on XOUT (R4) for damping (PicoGUS/RPi pattern)
    L(U1, "XIN", "XTAL_IN", dx=-2.54)
    L(U1, "XOUT", "XOUT_R", dx=-2.54)
    Y1 = sch.place("Device:Crystal", "Y1", "12MHz", at=(127.0, 190.5))
    L(Y1, "1", "XTAL_IN", dx=-2.54)
    L(Y1, "2", "XTAL_OUT", dx=2.54)
    cx1 = sch.place("Device:C", "C1", "30pF", at=(116.84, 203.2))
    L(cx1, "1", "XTAL_IN", dx=0, dy=-2.54); L(cx1, "2", "GND", dx=0, dy=2.54)
    cx2 = sch.place("Device:C", "C2", "30pF", at=(137.16, 203.2))
    L(cx2, "1", "XTAL_OUT", dx=0, dy=-2.54); L(cx2, "2", "GND", dx=0, dy=2.54)
    # 1k series on XOUT (damping, RP2040 required minimum): XOUT -> R4 -> crystal
    rx = sch.place("Device:R", "R4", "1k", at=(147.32, 190.5))
    L(rx, "1", "XOUT_R", dx=0, dy=-2.54)
    L(rx, "2", "XTAL_OUT", dx=0, dy=2.54)

    # RUN (reset): pull-up + delay cap
    L(U1, "26", "RUN", dx=2.54)
    rrun = sch.place("Device:R", "R1", "10k", at=(228.6, 76.2))
    L(rrun, "1", "RUN", dx=0, dy=2.54); L(rrun, "2", "+3V3", dx=0, dy=-2.54)
    crun = sch.place("Device:C", "C3", "1uF", at=(241.3, 76.2))
    L(crun, "1", "RUN", dx=0, dy=2.54); L(crun, "2", "GND", dx=0, dy=-2.54)

    # ---------------- QSPI flash (firmware + BIOS / option-ROM images) ----------------
    # Real W25Q128JVSIQ (16 MB, JLC basic part) -- was a placeholder header;
    # the Supervisor cannot boot without actual flash on QSPI.
    L(U1, "56", "QSPI_CS", dx=2.54)          # ~{QSPI_SS}
    L(U1, "52", "QSPI_SCLK", dx=2.54)
    L(U1, "53", "QSPI_SD0", dx=2.54)
    L(U1, "55", "QSPI_SD1", dx=2.54)
    L(U1, "54", "QSPI_SD2", dx=2.54)
    L(U1, "51", "QSPI_SD3", dx=2.54)
    UF = sch.place("Memory_Flash:W25Q128JVS", "U2", at=(279.4, 76.2))
    L(UF, "~{CS}", "QSPI_CS", dx=-2.54)
    L(UF, "CLK", "QSPI_SCLK", dx=-2.54)
    L(UF, "DI/IO_{0}", "QSPI_SD0", dx=-2.54)
    L(UF, "DO/IO_{1}", "QSPI_SD1", dx=2.54)
    L(UF, "~{WP}/IO_{2}", "QSPI_SD2", dx=-2.54)
    L(UF, "~{HOLD}/~{RESET}/IO_{3}", "QSPI_SD3", dx=2.54)
    L(UF, "VCC", "+3V3", dx=0, dy=-2.54)
    L(UF, "GND", "GND", dx=0, dy=2.54)
    decouple("C4", (279.4, 50.8))   # flash decoupling

    # BOOTSEL button: hold at power-up to enter the USB bootloader (PicoGUS/RPi pattern)
    # The Supervisor is now USB-flashable via the shared programming port.
    rb = sch.place("Device:R", "R5", "1k", at=(304.8, 76.2))
    L(rb, "1", "QSPI_CS", dx=0, dy=-2.54)
    L(rb, "2", "~{USB_BOOT}", dx=0, dy=2.54)
    SW1 = sch.place("Switch:SW_Push", "SW1", "BOOTSEL", at=(304.8, 96.52))
    L(SW1, "1", "~{USB_BOOT}", dx=-2.54)
    L(SW1, "2", "GND", dx=2.54)

    # ---------------- USB-A host jack (keyboard / hub) ----------------
    # VBUS through a polyfuse: the board 5V rail sources the downstream USB
    # device (doc S13 calls this the tight current loop) -- a shorted keyboard
    # cable must not drop the whole rail.
    JU = sch.place("Connector:USB_A", "J2", "USB_HOST", at=(63.5, 101.6))
    F1 = sch.place("Device:Polyfuse", "F1", "500mA", at=(63.5, 76.2))
    L(F1, "1", "+5V", dx=0, dy=-2.54)
    L(F1, "2", "VBUS_KBD", dx=0, dy=2.54)
    L(JU, "VBUS", "VBUS_KBD", dx=-2.54)     # fused 5V to the downstream device
    L(JU, "D+", "USB_DP_J", dx=-2.54)
    L(JU, "D-", "USB_DM_J", dx=-2.54)
    L(JU, "GND", "GND", dx=-2.54)
    L(JU, "Shield", "GND", dx=-2.54)
    # native USB PHY pins
    L(U1, "USB_DP", "USB_DP", dx=-2.54)
    L(U1, "USB_DM", "USB_DM", dx=-2.54)

    # 27R series termination (RP2040 datasheet minimal design -- required)
    R2 = sch.place("Device:R", "R2", "27", at=(63.5, 134.62))
    L(R2, "1", "USB_DP", dx=0, dy=-2.54); L(R2, "2", "USB_DP_J", dx=0, dy=2.54)
    R3 = sch.place("Device:R", "R3", "27", at=(76.2, 134.62))
    L(R3, "1", "USB_DM", dx=0, dy=-2.54); L(R3, "2", "USB_DM_J", dx=0, dy=2.54)

    # ESD array on the outward-facing host port (jack side of the 27R)
    U3 = sch.place("Power_Protection:USBLC6-2SC6", "U3", "USBLC6-2SC6", at=(88.9, 134.62))
    L(U3, "1", "USB_DM_J", dx=-2.54); L(U3, "6", "USB_DM_J", dx=2.54)
    L(U3, "3", "USB_DP_J", dx=-2.54); L(U3, "4", "USB_DP_J", dx=2.54)
    L(U3, "5", "VBUS_KBD", dx=2.54)
    L(U3, "2", "GND", dx=-2.54)

    # Host-port VBUS bulk (USB spec requires >=120uF for downstream inrush)
    C13 = sch.place("Device:C_Polarized", "C13", "100uF", at=(50.8, 134.62))
    L(C13, "1", "VBUS_KBD", dx=0, dy=-2.54); L(C13, "2", "GND", dx=0, dy=2.54)
    pf = sch.place("power:PWR_FLAG", "#FLG1", at=(12.7, 12.7))  # VBUS_KBD is polyfuse-fed
    sch.net(pf, "1", "VBUS_KBD", kind="label", dx=0, dy=-2.54)

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

    # PD contract status from the power sheet (CH224K PG, open-drain + 3V3 pull-up)
    L(U1, "GPIO16", "PD_PG", dx=2.54)

    # ---------------- I2C RTC (PCF8563) + CR2032 battery backup ----------------
    # Battery-backed timekeeping for the Bus MCU's port-0x70/71 RTC emulation
    # (spec 2026-07-14): Supervisor reads it over I2C, syncs time over the
    # UART link at boot; CMOS config bytes live in Supervisor flash.
    # GPIO2/GPIO3 (RP2040's default I2C1 SDA/SCL function-select pair) are
    # picked from the spare-GPIO pool below -- no mux reassignment needed vs.
    # any other spare pin. See questions-supervisor.md.
    RTC = sch.place("mini-xt:PCF8563", "U5", "PCF8563T", at=(215.9, 177.8))
    L(RTC, "SDA", "RTC_SDA", dx=-2.54)
    L(RTC, "SCL", "RTC_SCL", dx=-2.54)
    L(U1, "GPIO2", "RTC_SDA", dx=2.54)   # I2C1 SDA (default mux)
    L(U1, "GPIO3", "RTC_SCL", dx=2.54)   # I2C1 SCL (default mux)
    # Pull-ups to +3V3 (not to the battery-only VDD_RTC rail): the Supervisor
    # is the only bus master and only runs on board power, so the bus is only
    # ever driven while +3V3 is up -- pulling from the always-on rail would
    # leak current into VDD_RTC through the PCF8563's ESD diodes with the
    # board off, for zero benefit.
    r8 = sch.place("Device:R", "R8", "4.7k", at=(241.3, 165.1))
    L(r8, "1", "+3V3", dx=0, dy=-2.54); L(r8, "2", "RTC_SDA", dx=0, dy=2.54)
    r9 = sch.place("Device:R", "R9", "4.7k", at=(254.0, 165.1))
    L(r9, "1", "+3V3", dx=0, dy=-2.54); L(r9, "2", "RTC_SCL", dx=0, dy=2.54)

    # VDD_RTC: simple two-Schottky diode-OR keeps the PCF8563 powered from
    # +3V3 while the board is up (forward drop puts VDD_RTC a diode-drop
    # below +3V3, so it always wins over the ~3.0V CR2032) and from the
    # CR2032 alone when the board is off -- the standard battery-backed-RTC
    # arrangement. Same SS34 already used for OR-ing elsewhere (video.py,
    # bus_mcu.py).
    d1 = sch.place("Device:D_Schottky", "D1", "SS34", at=(177.8, 152.4))
    L(d1, "2", "+3V3", dx=-2.54, dy=0)          # 2 = anode
    L(d1, "1", "VDD_RTC", dx=2.54, dy=0)        # 1 = cathode
    d2 = sch.place("Device:D_Schottky", "D2", "SS34", at=(177.8, 165.1))
    L(d2, "2", "VBAT_RTC", dx=-2.54, dy=0)      # 2 = anode
    L(d2, "1", "VDD_RTC", dx=2.54, dy=0)        # 1 = cathode
    # PWR_FLAG: VDD_RTC is only ever fed through the diode-OR (passive pins),
    # so ERC can't see a power source driving the PCF8563's VDD -- declare it.
    fl = sch.place("power:PWR_FLAG", "#FLG1", at=(203.2, 147.32))
    sch.net(fl, "1", "VDD_RTC", kind="label", dx=0, dy=2.54)
    bt1 = sch.place("Device:Battery_Cell", "BT1", "CR2032", at=(152.4, 177.8))
    L(bt1, "1", "VBAT_RTC", dx=0, dy=-2.54)     # '+'
    L(bt1, "2", "GND", dx=0, dy=2.54)           # '-'
    L(RTC, "VDD", "VDD_RTC", dx=0, dy=-2.54)
    L(RTC, "VSS", "GND", dx=0, dy=2.54)
    decouple("C8", (203.2, 152.4), rail="VDD_RTC")   # 100nF on VDD

    # 32.768kHz crystal: the PCF8563 has ONE integrated oscillator trim
    # capacitor (C_OSCO on OSCO, 15-35pF/typ 25pF per datasheet Table 30) --
    # only OSCI needs an external cap (Ctrim, 5-25pF ext., datasheet:
    # CL = Ctrim*C_OSCO / (Ctrim+C_OSCO)). Crystal picked at CL=12.5pF (the
    # datasheet's max quartz-CL rating, and JLC's deepest-stock 32.768kHz
    # part, C32346); solving for Ctrim at C_OSCO=25pF typ gives ~25pF --
    # reuse parts.py's existing 22pF (already sourced for the COM baud crystals)
    # rather than add a new SKU. That's within a couple pF of nominal, far
    # inside the crystal's +-20ppm tolerance for this fidelity. No cap on
    # OSCO (internal). ~{INT}: NC (Supervisor polls over I2C, no interrupt
    # wiring needed). CLKOUT: NC (unused).
    Y2 = sch.place("Device:Crystal", "Y2", "32.768kHz", at=(190.5, 203.2))
    L(Y2, "1", "OSCI_RTC", dx=-2.54); L(Y2, "2", "OSCO_RTC", dx=2.54)
    L(RTC, "OSCI", "OSCI_RTC", dx=-2.54)
    L(RTC, "OSCO", "OSCO_RTC", dx=-2.54)
    c7 = sch.place("Device:C", "C7", "22pF", at=(177.8, 215.9))
    L(c7, "1", "OSCI_RTC", dx=0, dy=-2.54); L(c7, "2", "GND", dx=0, dy=2.54)
    sch.no_connect(RTC.pin_xy("~{INT}"))
    sch.no_connect(RTC.pin_xy("CLKOUT"))

    # Unused GPIO (by pin number): GPIO17-25, GPIO26-29 (ADC bank) --
    # GPIO2/3 (pins 4/5) are now the RTC_SDA/RTC_SCL pair above.
    for p in (28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41):
        sch.no_connect(U1.pin_xy(p))

    # ----------- shared RP2040 programming port (USB-C, device mode) --------
    # SW2 selects which RP2040 the port reaches: position A = this Supervisor
    # (via the jack-side USB_DP_J/USB_DM_J nets -- unplug the keyboard while
    # flashing), position B = the PicoGUS RP2040 (PGUS_USB_DP/DM, a documented
    # isolation exception -- see notes). VBUS is NOT connected: the board must
    # be powered to flash, so no back-power path exists at all. Each chip has
    # its own BOOTSEL button (SW1 here, SW1 on the picogus sheet).
    J6 = sch.place("Connector:USB_C_Receptacle", "J6", "USB_PROG", at=(38.1, 43.18))
    L(J6, "A6", "PROG_DP"); L(J6, "B6", "PROG_DP")
    L(J6, "A7", "PROG_DM"); L(J6, "B7", "PROG_DM")
    L(J6, "A1", "GND", dx=0, dy=2.54); L(J6, "SH", "GND", dx=0, dy=2.54)
    rcc1 = sch.place("Device:R", "R6", "5.1k", at=(88.9, 43.18))
    L(rcc1, "1", "PROG_CC1", dx=0, dy=-2.54); L(rcc1, "2", "GND", dx=0, dy=2.54)
    rcc2 = sch.place("Device:R", "R7", "5.1k", at=(101.6, 43.18))
    L(rcc2, "1", "PROG_CC2", dx=0, dy=-2.54); L(rcc2, "2", "GND", dx=0, dy=2.54)
    L(J6, "A5", "PROG_CC1"); L(J6, "B5", "PROG_CC2")
    # NC the stacked VBUS pins (A4 covers the stack; if error, try A9/B4/B9 separately)
    for vbus_pin in ["A4", "A9", "B4", "B9"]:
        try:
            sch.no_connect(J6.pin_xy(vbus_pin))
        except KeyError:
            pass  # Pin not available in this symbol version
    # NC the USB 3.1 and auxiliary pins (not used for 2.0 device-mode operation)
    for nc in ["RX1-", "RX1+", "TX1-", "TX1+", "RX2-", "RX2+",
               "TX2-", "TX2+", "SBU1", "SBU2"]:
        sch.no_connect(J6.pin_xy(nc))
    # ESD array at the prog jack (common PROG_DP/DM side, so BOTH SW2 positions
    # are protected -- the U3 array only covers the Supervisor jack-side nets).
    # Clamp rail is +3V3: J6 VBUS is unconnected and the signaling is 3.3 V USB.
    U4 = sch.place("Power_Protection:USBLC6-2SC6", "U4", "USBLC6-2SC6", at=(63.5, 66.04))
    L(U4, "1", "PROG_DM", dx=-2.54); L(U4, "6", "PROG_DM", dx=2.54)
    L(U4, "3", "PROG_DP", dx=-2.54); L(U4, "4", "PROG_DP", dx=2.54)
    L(U4, "5", "+3V3", dx=2.54)
    L(U4, "2", "GND", dx=-2.54)
    SW2 = sch.place("Switch:SW_Slide_DPDT", "SW2", "PROG SEL", at=(137.16, 43.18))
    # KiCad SW_Slide_DPDT geometry: the MIDDLE pin of each pole (B = pins 2/5)
    # is the common; A (1/4) and C (3/6) are the two slide positions. Pair the
    # throws BY NAME so one slide position selects the same target on both
    # poles: A = Supervisor (jack-side nets), C = PicoGUS.
    L(SW2, "2", "PROG_DP", dx=-2.54, dy=0)         # pole 1 common
    L(SW2, "1", "USB_DP_J", dx=-2.54, dy=0)        # position A -> Supervisor
    L(SW2, "3", "PGUS_USB_DP", dx=-2.54, dy=0)     # position C -> PicoGUS
    L(SW2, "5", "PROG_DM", dx=2.54, dy=0)          # pole 2 common
    L(SW2, "4", "USB_DM_J", dx=2.54, dy=0)         # position A -> Supervisor
    L(SW2, "6", "PGUS_USB_DM", dx=2.54, dy=0)      # position C -> PicoGUS

    # (speed-select left the MCUs entirely 2026-07-20: it is a jumper strap
    # on cpu_core -- JP1 there, open = 7.16 MHz -- so there is no SPEED_SEL
    # pin here and no speed message on the UART link.)

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
    for i, x in enumerate(range(60, 340, 40)):
        decouple("C%d" % (14 + i), (float(x), 270.0))     # 3V3 rail decoupling

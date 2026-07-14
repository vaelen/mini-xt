"""PicoGUS (on-board, chip-down) -- ISA sound card on RP2040.

A faithful transcription of polpo's PicoGUS 2.0 "chip-down" reference design
(CERN-OHL-P; see `picogus/hw-chipdown/` -- schematic + `chipdown.net`), adapted
to run on this motherboard's ISA soft-card bus and STOCK PicoGUS firmware. The
GPIO map, the ADS/BUSOE address-data-mux time-sharing scheme, and the BUSOE
latch + AEN-masking glue are copied pin-for-pin because the firmware assumes
this exact hardware -- there is no "reasonable substitute" here the way there
is for, say, a generic 74HCT245 buffer.

Deviations from the reference (logged in hardware/notes/questions-picogus.md):
  * 3.3V bus redesign (2026-07-14): U6 (CB3T3245, "misc level shift") DELETED
    -- it was pure fixed-direction buffering (A8/A9 in, TC in, IRQ5/DRQ out,
    no muxing) with nothing left to do once the ISA bus is 3.3V-native; its
    6 channels are now direct GPIO<->net connections (gpio_map below). U4/U5
    (CB3T3257) are KEPT -- they are a genuine 2:1 GPIO-budget mux (8 GPIO
    serving both AD0-7 and A0-7/D0-7 via ADS/~{BUSOE} time-sharing), not a
    voltage bridge; deleting them would need 8 more GPIO the RP2040 doesn't
    have. U7/U8/U9/U10 are KEPT -- all four were already real logic (Schmitt
    reset-delay/inversion, AEN-masking NANDs, the BUSOE set-reset latch, an
    open-drain IOCHRDY driver) on 3V3_PGUS already, never doing 3.3V->5V
    buffering, so the voltage-domain change doesn't touch them. See
    questions-picogus.md Q6.
  * No ISA edge connector -- the bus arrives by net name (A0-A9, D0-D7, control
    strobes) like every other soft card, not a physical 60-pin/98-pin edge.
  * No USB-A joystick port -- the Supervisor sheet owns USB HID.
  * Wavetable header and MIDI out REMOVED (user decision 2026-07-11): with them
    went the M62429 (wavetable-volume-only) and the passive audio mix node.
    PG_L/PG_R are now simply the RC-filtered PCM5102A DAC outputs feeding the
    motherboard's audio summer. Stock firmware still drives RV_CLK/RV_DATA/
    MIDI_TX; those GPIOs are left as documented dangling local nets.
  * No local audio jack -- the post-filter node feeds the motherboard summer
    directly as PG_L/PG_R (the reference's mix node existed to combine the
    DAC with the wavetable board's return; with no wavetable there's nothing
    to mix).
  * No local programming USB -- the shared port on the supervisor sheet
    arrives here as PGUS_USB_DP/DM, a documented mxbus.PRIV_PROG isolation
    exception (see mxbus.py and supervisor.py).
  * GPIO29 grounded = the chip-down board-detect strap the stock firmware
    reads at boot to distinguish this hardware from the PicoGUS 2.0
    APU-daughterboard variant.
"""
import mxbus
from mxbus import pin

NAME = "picogus"
TITLE = "PicoGUS (on-board, chip-down) -- ISA sound card on RP2040"
PAPER = "A2"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +          # A0..A9
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "AEN", "RESET_DRV", "TC",
                               "~{DACK1}", "~{DACK3}"]] +
    [pin("IOCHRDY", "output"), pin("DRQ1", "output"), pin("DRQ3", "output")] +
    [pin("IRQ5", "output")] +      # hardwired (the free line); pgusinit sets the firmware to match
    [pin("PG_L", "output"), pin("PG_R", "output")] +       # post-filter audio -> audio sheet summer
    [pin("PGUS_USB_DP", "bidirectional"), pin("PGUS_USB_DM", "bidirectional")]
)


def build(sch, lib):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, rail="3V3_PGUS", gnd="GND"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", gnd, kind="label", dx=0, dy=2.54)

    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ============================================================ 1. RP2040 ===
    U1 = sch.place("MCU_RaspberryPi:RP2040", "U1", at=(127.0, 152.4))
    for n in ("1", "10", "22", "33", "42", "49"):        # IOVDD
        L(U1, n, "3V3_PGUS", dx=0, dy=-2.54)
    L(U1, "43", "3V3_PGUS", dx=0, dy=-2.54)               # ADC_AVDD
    L(U1, "48", "3V3_PGUS", dx=0, dy=-2.54)               # USB_VDD
    L(U1, "44", "3V3_PGUS", dx=0, dy=-2.54)               # VREG_VIN
    L(U1, "45", "VCORE", dx=2.54)                         # VREG_VOUT
    L(U1, "23", "VCORE", dx=0, dy=2.54)                   # DVDD
    L(U1, "50", "VCORE", dx=0, dy=2.54)                   # DVDD
    L(U1, "57", "GND", dx=0, dy=2.54)
    L(U1, "19", "GND", dx=-2.54)                          # TESTEN

    L(U1, "XIN", "XIN", dx=-2.54)
    L(U1, "XOUT", "XOUT_R", dx=-2.54)
    L(U1, "USB_DP", "USB_DP_I", dx=-2.54)
    L(U1, "USB_DM", "USB_DM_I", dx=-2.54)
    L(U1, "SWCLK", "PGUS_SWCLK", dx=2.54)
    L(U1, "SWDIO", "PGUS_SWDIO", dx=2.54)
    L(U1, "26", "RUN", dx=2.54)                           # RUN

    # ---- stock-firmware GPIO map (mini-xt/picogus/hw-chipdown/chipdown.net) ----
    # Keyed by RP2040 GPIO **name** (the symbol's pin NAME, e.g. "GPIO20"), which
    # is exactly what stock PicoGUS firmware addresses -- verified pin-for-pin
    # against docs/PicoGUS-chipdown-schematic.pdf (the reference RP2040 sheet).
    #
    # PIN-NAME-vs-NUMBER TRAP: sch.net() resolves a pin ref by NAME first, then
    # falls back to the package-pin NUMBER, and on the QFN-56 the two differ
    # (GPIO0 = package pin 2, GPIO14 = pin 17, GPIO20 = pin 31, ...). Revs up to
    # 2026-07-13 keyed this map by bare package-pin NUMBER strings ("31" for
    # GPIO20). That still wired the *correct* pads -- no pin is *named* "31", so
    # "31" fell through to package pin 31 = GPIO20 -- but the keys READ like GPIO
    # numbers under a "GPIO" header, which invited a false "wired to the wrong
    # GPIO" report. Keying by GPIO name is self-documenting and connectivity is
    # byte-identical (see questions-picogus.md Q7 / 3v3-verification.md check 6).
    #
    # GPIO (pkg pin)     | Sheet net | ISA-facing signal             | Path / notes
    # -------------------|-----------|-------------------------------|-------------
    # GPIO6-13 (8,9,11-16)| AD0-AD7  | A0-A7 / D0-D7 (time-shared)   | U4/U5 CB3T3257
    #                    |           |                               | mux, S=ADS, ~{OE}=~{BUSOE}
    # GPIO14 (17)        | A8        | A8 (address only)             | DIRECT (U6 deleted)
    # GPIO15 (18)        | A9        | A9                            | DIRECT (U6 deleted)
    # GPIO4  (6)         | ~{RIOW}   | ~{IOW}, AEN-masked            | U7/U8 gates
    # GPIO5  (7)         | ~{RIOR}   | ~{IOR}, AEN-masked            | U7/U8 gates
    # GPIO19 (30)        | ~{RDACK}  | ~{DACK1}/~{DACK3} (jumper J1)  | senses jumpered ack
    # GPIO20 (31)        | TC        | TC (ISA terminal count, in)   | DIRECT (U6 deleted)
    # GPIO21 (32)        | IRQ5      | IRQ5 (out, hardwired free)    | DIRECT (U6 deleted)
    # GPIO22 (34)        | DRQ       | DRQ1/DRQ3 (out, jumper J1)     | DIRECT (U6 deleted)
    # GPIO26 (38)        | RIOCHRDY  | IOCHRDY (out, open-drain)     | U10 74LVC2G06
    # GPIO27 (39)        | ADS       | (mux select/timing, not ISA)  | drives U4/U5/U9
    # GPIO0-3 (2-5)      | SPI_*     | (not ISA -- APS6404L SPI)     | unaffected
    # GPIO16-18 (27-29)  | DIN,BCK,LRCK | (not ISA -- PCM5102A I2S)  | unaffected
    # GPIO23 (35)        | LED_A     | (not ISA -- status LED)       | unaffected
    # GPIO24,25,28 (36,37,40)| RV_DATA,RV_CLK,MIDI_TX | (not ISA -- dangling, wavetable/MIDI removed 2026-07-11) | unaffected
    # GPIO29 (41)        | GND       | board-detect strap            | unaffected
    #
    # (GPIO26-29 keys carry the symbol's "/ADCn" name suffix; that IS the pin
    # name, so the ref resolves by name -- do not drop it.)
    gpio_map = [
        ("GPIO0", "SPI_RX"), ("GPIO1", "~{SPI_CS}"), ("GPIO2", "SPI_SCK"), ("GPIO3", "SPI_TX"),
        ("GPIO4", "~{RIOW}"), ("GPIO5", "~{RIOR}"),
        ("GPIO6", "AD0"), ("GPIO7", "AD1"), ("GPIO8", "AD2"), ("GPIO9", "AD3"),
        ("GPIO10", "AD4"), ("GPIO11", "AD5"), ("GPIO12", "AD6"), ("GPIO13", "AD7"),
        ("GPIO14", "A8"), ("GPIO15", "A9"),                # direct (was RA8/RA9 via U6)
        ("GPIO16", "DIN"), ("GPIO17", "BCK"), ("GPIO18", "LRCK"),
        ("GPIO19", "~{RDACK}"), ("GPIO20", "TC"), ("GPIO21", "IRQ5"), ("GPIO22", "DRQ"),  # direct (was RTC_LS/RIRQ/RDRQ via U6)
        ("GPIO23", "LED_A"), ("GPIO24", "RV_DATA"), ("GPIO25", "RV_CLK"),
        ("GPIO26/ADC0", "RIOCHRDY"), ("GPIO27/ADC1", "ADS"),
        ("GPIO28/ADC2", "MIDI_TX"), ("GPIO29/ADC3", "GND"),
    ]
    for gp, net in gpio_map:
        L(U1, gp, net, dx=2.54)
    sch.text("GPIO29->GND: chip-down board-detect strap (stock firmware reads\n"
              "low at boot to select this hardware variant).", at=(203.2, 96.52))
    sch.text("RV_CLK/RV_DATA/MIDI_TX: driven by stock firmware; volume chip /\n"
              "MIDI / wavetable omitted on this board (user decision 2026-07-11).",
              at=(203.2, 111.76))

    # ---- crystal (12MHz, X322512MSB4SI + 30pF + 1k -- RP2040 minimal design) ----
    Y1 = sch.place("Device:Crystal", "Y1", "12MHz", at=(76.2, 190.5))
    L(Y1, "1", "XIN", dx=-2.54)
    L(Y1, "2", "XTAL_OUT", dx=2.54)
    Cxin = sch.place("Device:C", "C1", "30pF", at=(63.5, 203.2))
    L(Cxin, "1", "XIN", dx=0, dy=-2.54); L(Cxin, "2", "GND", dx=0, dy=2.54)
    Cxout = sch.place("Device:C", "C2", "30pF", at=(88.9, 203.2))
    L(Cxout, "1", "XTAL_OUT", dx=0, dy=-2.54); L(Cxout, "2", "GND", dx=0, dy=2.54)
    Rxtal = sch.place("Device:R", "R1", "1k", at=(76.2, 215.9))
    L(Rxtal, "1", "XOUT_R", dx=0, dy=-2.54); L(Rxtal, "2", "XTAL_OUT", dx=0, dy=2.54)

    # ---- QSPI flash (firmware image) ----
    L(U1, "56", "PGUS_QSPI_SS", dx=2.54)
    L(U1, "52", "PGUS_QSPI_SCLK", dx=2.54)
    L(U1, "53", "PGUS_QSPI_SD0", dx=2.54)
    L(U1, "55", "PGUS_QSPI_SD1", dx=2.54)
    L(U1, "54", "PGUS_QSPI_SD2", dx=2.54)
    L(U1, "51", "PGUS_QSPI_SD3", dx=2.54)
    U2 = sch.place("Memory_Flash:W25Q128JVS", "U2", at=(63.5, 254.0))
    L(U2, "~{CS}", "PGUS_QSPI_SS", dx=-2.54)
    L(U2, "CLK", "PGUS_QSPI_SCLK", dx=-2.54)
    L(U2, "DI/IO_{0}", "PGUS_QSPI_SD0", dx=-2.54)
    L(U2, "DO/IO_{1}", "PGUS_QSPI_SD1", dx=2.54)
    L(U2, "~{WP}/IO_{2}", "PGUS_QSPI_SD2", dx=-2.54)
    L(U2, "~{HOLD}/~{RESET}/IO_{3}", "PGUS_QSPI_SD3", dx=2.54)
    L(U2, "VCC", "3V3_PGUS", dx=0, dy=-2.54)
    L(U2, "GND", "GND", dx=0, dy=2.54)
    decouple("C3", (63.5, 267.72))

    # ---- BOOTSEL ----
    Rboot = sch.place("Device:R", "R2", "1k", at=(101.6, 254.0))
    L(Rboot, "1", "PGUS_QSPI_SS", dx=0, dy=-2.54)
    L(Rboot, "2", "~{USB_BOOT}", dx=0, dy=2.54)
    SW1 = sch.place("Switch:SW_Push", "SW1", "BOOTSEL", at=(101.6, 267.72))
    L(SW1, "1", "~{USB_BOOT}", dx=-2.54)
    L(SW1, "2", "GND", dx=2.54)

    # ---- USB series termination (shared prog port arrives via hier pins) ----
    R3 = sch.place("Device:R", "R3", "27", at=(114.3, 292.1))
    L(R3, "1", "USB_DP_I", dx=0, dy=-2.54); L(R3, "2", "PGUS_USB_DP", dx=0, dy=2.54)
    R4 = sch.place("Device:R", "R4", "27", at=(127.0, 292.1))
    L(R4, "1", "USB_DM_I", dx=0, dy=-2.54); L(R4, "2", "PGUS_USB_DM", dx=0, dy=2.54)

    # ---- SWD header ----
    J5 = sch.place("Connector_Generic:Conn_01x03", "J5", "SWD", at=(63.5, 292.1))
    L(J5, "1", "PGUS_SWDIO", dx=-2.54)
    L(J5, "2", "PGUS_SWCLK", dx=-2.54)
    L(J5, "3", "GND", dx=-2.54)

    # ---- status LED ----
    R5 = sch.place("Device:R", "R5", "470", at=(152.4, 254.0))
    L(R5, "1", "LED_A", dx=0, dy=-2.54); L(R5, "2", "LED_RA", dx=0, dy=2.54)
    D1 = sch.place("Device:LED", "D1", at=(152.4, 267.72))
    L(D1, "A", "LED_RA", dx=-2.54); L(D1, "K", "GND", dx=2.54)

    # ---- VCORE / QSPI decoupling ----
    Cvin = sch.place("Device:C", "C4", "1uF", at=(139.7, 254.0))
    L(Cvin, "1", "3V3_PGUS", dx=0, dy=-2.54); L(Cvin, "2", "GND", dx=0, dy=2.54)
    Cvcore1 = sch.place("Device:C", "C5", "1uF", at=(101.6, 177.8))
    L(Cvcore1, "1", "VCORE", dx=0, dy=-2.54); L(Cvcore1, "2", "GND", dx=0, dy=2.54)
    Cvcore2 = sch.place("Device:C", "C6", "100nF", at=(114.3, 177.8))
    L(Cvcore2, "1", "VCORE", dx=0, dy=-2.54); L(Cvcore2, "2", "GND", dx=0, dy=2.54)

    # ============================================================ 2. power =====
    U3 = sch.place("Regulator_Linear:AMS1117-3.3", "U3", at=(50.8, 63.5))
    L(U3, "VI", "+5V", dx=-2.54)
    L(U3, "VO", "3V3_PGUS", dx=2.54)
    L(U3, "GND", "GND", dx=0, dy=2.54)
    Cvi = sch.place("Device:C", "C7", "10uF", at=(38.1, 63.5))
    L(Cvi, "1", "+5V", dx=0, dy=-2.54); L(Cvi, "2", "GND", dx=0, dy=2.54)
    Cvo = sch.place("Device:C", "C8", "10uF", at=(63.5, 63.5))
    L(Cvo, "1", "3V3_PGUS", dx=0, dy=-2.54); L(Cvo, "2", "GND", dx=0, dy=2.54)

    FB1 = sch.place("Device:FerriteBead", "FB1", "120R@100MHz", at=(50.8, 88.9))
    L(FB1, "1", "3V3_PGUS", dx=-2.54); L(FB1, "2", "AVDD_PGUS", dx=2.54)
    FB2 = sch.place("Device:FerriteBead", "FB2", "120R@100MHz", at=(50.8, 101.6))
    L(FB2, "1", "GND", dx=-2.54); L(FB2, "2", "AGND_PGUS", dx=2.54)
    # ERC power markers: both analog rails arrive through ferrite beads
    for i, net in ((1, "AVDD_PGUS"), (2, "AGND_PGUS")):
        pf = sch.place("power:PWR_FLAG", "#FLG%d" % i, at=(12.7 + (i - 1) * 15.24, 12.7))
        sch.net(pf, "1", net, kind="label", dx=0, dy=-2.54)

    C9 = sch.place("Device:C", "C9", "47uF", at=(76.2, 63.5))
    L(C9, "1", "+5V", dx=0, dy=-2.54); L(C9, "2", "GND", dx=0, dy=2.54)
    C10 = sch.place("Device:C", "C10", "47uF", at=(88.9, 63.5))
    L(C10, "1", "3V3_PGUS", dx=0, dy=-2.54); L(C10, "2", "GND", dx=0, dy=2.54)

    for i, x in enumerate(range(38, 190, 19)):
        decouple("C%d" % (11 + i), (float(x), 393.7))

    C19 = sch.place("Device:C_Polarized", "C19", "100uF", at=(63.5, 114.3))
    L(C19, "1", "AVDD_PGUS", dx=0, dy=-2.54); L(C19, "2", "AGND_PGUS", dx=0, dy=2.54)

    # ================================================= 3. address/data mux =====
    U4 = sch.place("mini-xt:CB3T3257", "U4", at=(254.0, 63.5))
    L(U4, "S", "ADS", dx=-2.54)
    L(U4, "~{OE}", "~{BUSOE}", dx=-2.54)
    L(U4, "VCC", "3V3_PGUS", dx=0, dy=-2.54)
    L(U4, "GND", "GND", dx=0, dy=2.54)
    L(U4, "1A", "AD0", dx=2.54); L(U4, "1B1", "A0", dx=-2.54); L(U4, "1B2", "D0", dx=-2.54)
    L(U4, "2A", "AD1", dx=2.54); L(U4, "2B1", "A1", dx=-2.54); L(U4, "2B2", "D1", dx=-2.54)
    L(U4, "3A", "AD3", dx=2.54); L(U4, "3B1", "A3", dx=-2.54); L(U4, "3B2", "D3", dx=-2.54)
    L(U4, "4A", "AD2", dx=2.54); L(U4, "4B1", "A2", dx=-2.54); L(U4, "4B2", "D2", dx=-2.54)

    U5 = sch.place("mini-xt:CB3T3257", "U5", at=(254.0, 101.6))
    L(U5, "S", "ADS", dx=-2.54)
    L(U5, "~{OE}", "~{BUSOE}", dx=-2.54)
    L(U5, "VCC", "3V3_PGUS", dx=0, dy=-2.54)
    L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "1A", "AD4", dx=2.54); L(U5, "1B1", "A4", dx=-2.54); L(U5, "1B2", "D4", dx=-2.54)
    L(U5, "2A", "AD5", dx=2.54); L(U5, "2B1", "A5", dx=-2.54); L(U5, "2B2", "D5", dx=-2.54)
    L(U5, "3A", "AD7", dx=2.54); L(U5, "3B1", "A7", dx=-2.54); L(U5, "3B2", "D7", dx=-2.54)
    L(U5, "4A", "AD6", dx=2.54); L(U5, "4B1", "A6", dx=-2.54); L(U5, "4B2", "D6", dx=-2.54)

    # ==================================================== 4. misc level shift ===
    # U6 (CB3T3245) DELETED (3.3V bus redesign, 2026-07-14): it was pure
    # fixed-direction buffering (no muxing) for A8/A9 (in), TC (in), IRQ5/DRQ
    # (out) -- nothing left to do once the ISA bus is 3.3V-native. GPIO17/18/
    # 31/32/34 now sit directly on A8/A9/TC/IRQ5/DRQ (see gpio_map above).

    # ========================================================= 5. glue logic ===
    U7 = sch.place("mini-xt:74HCT04", "U7", "74AHC14", at=(355.6, 63.5))
    L(U7, "VCC", "3V3_PGUS", dx=0, dy=-2.54); L(U7, "GND", "GND", dx=0, dy=2.54)
    L(U7, "P1", "~{IOR}", dx=-2.54);       L(U7, "P2", "IOR_POS")
    L(U7, "P3", "~{IOW}", dx=-2.54);       L(U7, "P4", "IOW_POS")
    L(U7, "P5", "DACK", dx=-2.54);         L(U7, "P6", "~{RDACK}")
    L(U7, "P11", "RESET_DRV", dx=-2.54);   L(U7, "P10", "RST_INV")
    L(U7, "P9", "RST_INV", dx=-2.54);      L(U7, "P8", "RST_DLY")
    L(U7, "P13", "ADS", dx=-2.54);         L(U7, "P12", "ADS_INV")

    # 74HC00 value override (2026-07-14, was 74LVC00): the LVC grade was
    # inherited from the 5V-ISA reference design; this island has been all
    # 3.3V since the redesign, so every input here is 3.3V-driven and plain
    # HC is in spec -- basic-part, deep stock, and it deletes the board's
    # thinnest BOM line (74LVC00, ~125 units). Same swap on U9.
    U8 = sch.place("mini-xt:74HCT00", "U8", "74HC00", at=(355.6, 127.0))
    L(U8, "VCC", "3V3_PGUS", dx=0, dy=-2.54); L(U8, "GND", "GND", dx=0, dy=2.54)
    L(U8, "P9", "AEN", dx=-2.54); L(U8, "P10", "DACK", dx=-2.54); L(U8, "P8", "IOMASK")
    L(U8, "P1", "IOR_POS", dx=-2.54); L(U8, "P2", "IOMASK", dx=-2.54); L(U8, "P3", "~{RIOR}")
    L(U8, "P4", "IOW_POS", dx=-2.54); L(U8, "P5", "IOMASK", dx=-2.54); L(U8, "P6", "~{RIOW}")
    # MIDI inverter gate removed with the MIDI port (design change 2026-07-11):
    # tie both inputs low, no_connect the output rather than leave float inputs.
    L(U8, "P12", "GND", dx=-2.54); L(U8, "P13", "GND", dx=-2.54)
    sch.no_connect(U8.pin_xy("P11"))

    U9 = sch.place("mini-xt:74HCT00", "U9", "74HC00", at=(355.6, 190.5))
    L(U9, "VCC", "3V3_PGUS", dx=0, dy=-2.54); L(U9, "GND", "GND", dx=0, dy=2.54)
    L(U9, "P1", "ADS_INV", dx=-2.54); L(U9, "P2", "~{BUSOE}", dx=-2.54); L(U9, "P3", "LATCH_A")
    L(U9, "P4", "LATCH_A", dx=-2.54); L(U9, "P5", "RUN", dx=-2.54); L(U9, "P6", "~{BUSOE}")
    L(U9, "P9", "RST_DLY", dx=-2.54); L(U9, "P10", "RST_DLY", dx=-2.54); L(U9, "P8", "RUN")
    # Wavetable-reset gate: no wavetable header on this board (design change
    # 2026-07-11), so its output is unused -- inputs stay wired to RST_DLY
    # (driven, no float hazard) and the output is no_connect.
    L(U9, "P12", "RST_DLY", dx=-2.54); L(U9, "P13", "RST_DLY", dx=-2.54)
    sch.no_connect(U9.pin_xy("P11"))

    U10 = sch.place("mini-xt:74LVC2G06", "U10", at=(355.6, 241.3))
    L(U10, "VCC", "3V3_PGUS", dx=0, dy=-2.54); L(U10, "GND", "GND", dx=0, dy=2.54)
    L(U10, "1A", "RIOCHRDY", dx=-2.54); L(U10, "1Y", "IOCHRDY", dx=2.54)
    # Gate 2 spare (was MIDI open-drain output; MIDI port removed 2026-07-11).
    L(U10, "2A", "GND", dx=-2.54); sch.no_connect(U10.pin_xy("2Y"))

    R6 = sch.place("Device:R", "R6", "10k", at=(228.6, 25.4))
    L(R6, "1", "RESET_DRV", dx=0, dy=-2.54); L(R6, "2", "GND", dx=0, dy=2.54)
    R7 = sch.place("Device:R", "R7", "10k", at=(241.3, 25.4))
    L(R7, "1", "3V3_PGUS", dx=0, dy=-2.54); L(R7, "2", "~{BUSOE}", dx=0, dy=2.54)
    R8 = sch.place("Device:R", "R8", "1k", at=(254.0, 25.4))
    L(R8, "1", "3V3_PGUS", dx=0, dy=-2.54); L(R8, "2", "RUN", dx=0, dy=2.54)
    C20 = sch.place("Device:C", "C20", "100nF", at=(266.7, 25.4))
    L(C20, "1", "RUN", dx=0, dy=-2.54); L(C20, "2", "GND", dx=0, dy=2.54)
    # R9 pulls DACK (idle-high = deasserted) to 3V3_PGUS, not +5V: DACK feeds
    # U7/U8 gate inputs on the 3V3_PGUS domain, and with no jumper installed
    # it must not park at a stray 5V while everything reading it is 3.3V
    # (3.3V bus redesign, 2026-07-14 -- matches the R7/R8 pull-up convention
    # on this sheet).
    R9 = sch.place("Device:R", "R9", "15k", at=(279.4, 25.4))
    L(R9, "1", "3V3_PGUS", dx=0, dy=-2.54); L(R9, "2", "DACK", dx=0, dy=2.54)
    sch.text("BUSOE latch: ~{BUSOE} parks HIGH (buffers off) through bus reset,\n"
              "latches LOW (buffers on) once firmware first toggles ADS.",
              at=(355.6, 215.9))

    # =================================================== 6. IRQ/DMA jumpers ====
    J1 = sch.place("Connector_Generic:Conn_02x04_Odd_Even", "J1", "DMA_JP", at=(431.8, 63.5))
    dma_odd = {1: "DRQ1", 3: "~{DACK1}", 5: "DRQ3", 7: "~{DACK3}"}
    for num, net in dma_odd.items():
        L(J1, str(num), net, dx=-2.54)
    for num in (2, 6):
        L(J1, str(num), "DRQ", dx=2.54)
    for num in (4, 8):
        L(J1, str(num), "DACK", dx=2.54)
    sch.text("DMA jumpers: one DRQ/DACK pair -- our Bus MCU services DMA ch1\n"
              "ONLY, so jumper DRQ1/DACK1. IRQ hardwired to IRQ5 (the free\n"
              "line, sole driver); pgusinit sets the firmware to match.", at=(431.8, 25.4))

    # ========================================================= 7. sample RAM ===
    U11 = sch.place("mini-xt:APS6404L", "U11", at=(63.5, 203.2))
    L(U11, "~{CE}", "~{SPI_CS}", dx=-2.54)
    L(U11, "SCLK", "SPI_SCK", dx=-2.54)
    L(U11, "SI/SIO0", "SPI_TX", dx=-2.54)
    L(U11, "SO/SIO1", "SPI_RX", dx=-2.54)
    sch.no_connect(U11.pin_xy("SIO2"))
    sch.no_connect(U11.pin_xy("SIO3"))
    L(U11, "VCC", "3V3_PGUS", dx=0, dy=-2.54)
    L(U11, "VSS", "GND", dx=0, dy=2.54)
    decouple("C21", (76.2, 190.5))
    sch.text("APS6404L MUST be the -3SQR (3.0-3.6V) grade, not -3SQN (1.8V).",
              at=(38.1, 228.6))

    # ================================================================ 8. audio =
    # Wavetable mix node removed with the wavetable header/M62429 (design
    # change 2026-07-11): PCM5102A OUTL/OUTR go straight through the
    # reference's RC filter to PG_L/PG_R -- no coupling caps or 1k mixers
    # needed (the DAC is ground-referenced via its VNEG charge pump, and the
    # audio sheet AC-couples the summer input anyway).
    U12 = sch.place("mini-xt:PCM5102A", "U12", at=(254.0, 292.1))
    L(U12, "BCK", "BCK", dx=-2.54)
    L(U12, "DIN", "DIN", dx=-2.54)
    L(U12, "LRCK", "LRCK", dx=-2.54)
    L(U12, "SCK", "GND", dx=-2.54)
    L(U12, "FMT", "GND", dx=-2.54)
    L(U12, "FLT", "GND", dx=-2.54)
    L(U12, "DEMP", "GND", dx=-2.54)
    L(U12, "XSMT", "3V3_PGUS", dx=-2.54)
    L(U12, "CPVDD", "AVDD_PGUS", dx=0, dy=-2.54)
    L(U12, "AVDD", "AVDD_PGUS", dx=0, dy=-2.54)
    L(U12, "DVDD", "3V3_PGUS", dx=0, dy=-2.54)
    L(U12, "CPGND", "AGND_PGUS", dx=0, dy=2.54)
    L(U12, "AGND", "AGND_PGUS", dx=0, dy=2.54)
    L(U12, "DGND", "GND", dx=0, dy=2.54)
    L(U12, "OUTL", "DAC_L", dx=2.54)
    L(U12, "OUTR", "DAC_R", dx=2.54)
    L(U12, "CAPP", "CAPP", dx=2.54)
    L(U12, "CAPM", "CAPM", dx=2.54)
    L(U12, "VNEG", "VNEG", dx=2.54)
    L(U12, "LDOO", "LDOO", dx=2.54)

    # Decoupling row placed clear of U12's own pin-stub columns (x=251.46/
    # 254.0/256.54 top+bottom, x=270.51 right) to avoid stray wire crossings.
    Ccp = sch.place("Device:C", "C22", "2.2uF", at=(228.6, 320.04))
    L(Ccp, "1", "CAPP", dx=0, dy=-2.54); L(Ccp, "2", "CAPM", dx=0, dy=2.54)
    Cvneg = sch.place("Device:C", "C23", "2.2uF", at=(241.3, 320.04))
    L(Cvneg, "1", "VNEG", dx=0, dy=-2.54); L(Cvneg, "2", "AGND_PGUS", dx=0, dy=2.54)
    Cldoo = sch.place("Device:C", "C24", "100nF", at=(254.0, 320.04))
    L(Cldoo, "1", "LDOO", dx=0, dy=-2.54); L(Cldoo, "2", "GND", dx=0, dy=2.54)
    Cdvdd = sch.place("Device:C", "C25", "100nF", at=(266.7, 320.04))
    L(Cdvdd, "1", "3V3_PGUS", dx=0, dy=-2.54); L(Cdvdd, "2", "GND", dx=0, dy=2.54)
    Cavdd1 = sch.place("Device:C", "C26", "100nF", at=(279.4, 320.04))
    L(Cavdd1, "1", "AVDD_PGUS", dx=0, dy=-2.54); L(Cavdd1, "2", "AGND_PGUS", dx=0, dy=2.54)
    Cavdd2 = sch.place("Device:C", "C27", "10uF", at=(292.1, 320.04))
    L(Cavdd2, "1", "AVDD_PGUS", dx=0, dy=-2.54); L(Cavdd2, "2", "AGND_PGUS", dx=0, dy=2.54)

    # ---- RC filter straight to PG_L/PG_R (was PGAUDIO_* -> mix node) ----
    R10 = sch.place("Device:R", "R10", "470", at=(330.2, 279.4))
    L(R10, "1", "DAC_L", dx=0, dy=-2.54); L(R10, "2", "PG_L", dx=0, dy=2.54)
    C28 = sch.place("Device:C", "C28", "2.2nF", at=(342.9, 279.4))
    L(C28, "1", "PG_L", dx=0, dy=-2.54); L(C28, "2", "AGND_PGUS", dx=0, dy=2.54)
    R11 = sch.place("Device:R", "R11", "470", at=(330.2, 304.8))
    L(R11, "1", "DAC_R", dx=0, dy=-2.54); L(R11, "2", "PG_R", dx=0, dy=2.54)
    C29 = sch.place("Device:C", "C29", "2.2nF", at=(342.9, 304.8))
    L(C29, "1", "PG_R", dx=0, dy=-2.54); L(C29, "2", "AGND_PGUS", dx=0, dy=2.54)
    sch.text("PG_L/PG_R = RC-filtered PCM5102A outputs -> audio sheet summer.\n"
              "Wavetable mix node / M62429 removed 2026-07-11 (see notes).",
              at=(254.0, 317.5))

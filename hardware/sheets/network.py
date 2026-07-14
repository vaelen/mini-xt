"""Network -- RTL8019AS NE2000-compatible Ethernet ISA card.

A transcription of Manawyrm's ISA8019 Rev A (CERN-OHL-P; `../ISA8019` --
`ISA8019.xml` netlist + KiCad project) onto this motherboard's ISA soft-card
bus, adapted to mini-xt conventions.

Deviations from the reference:
  * No boot ROM (BS0-4/PNP/BROM socket omitted) -- this board has no PXE/RPL
    use case; the pins are wired the same as the reference's "no BROM"
    strapping (BS0-4 and PNP left open/NC) rather than populating a socket.
  * All configuration straps are hardwired resistors, not the reference's
    physical DIP switch -- see the strap table below. RSTDRV-latched,
    internal ~100k pull-downs mean an unstrapped (floating) pin reads 0;
    only JP and IOS1 need an explicit pull-up to read 1.
  * Added: a 74LVC125A gate (U3) not present on the reference, driven by
    the central DIS_NIC level (mxbus.PRIV_DIS, from the addr_decode sheet's
    JP5 -- 2026-07-14: the old on-sheet JP1/~{NET_EN} jumper moved there,
    sense inverted to match the other disables: ENABLED by default, fit the
    jumper to disable). DIS_NIC low (default) = card behaves exactly like
    the reference. High = tri-states IRQ2 AND forces the chip's AEN input
    high (so it ignores all I/O cycles), releasing both the IRQ line and
    the address decode for a sidecar card sharing this bus. The gate stays
    LOCAL because the disable must reach inside the 5V island (the
    RTL8019AS decodes its own address; there is no external CS to gate).
  * RJ45 successor part (`mini-xt:RJ45_LED`, C386757) replacing the
    reference's magjack (C133529, now EOL at JLC) -- LED polarity verified
    from EasyEDA pin names, not assumed identical.

Three hardwired choices (see strap table / Q1-Q6 in
hardware/notes/questions-network.md for the full reasoning):
  * I/O base 0x340 (IOS[3:0] = 0010)
  * IRQ2/9 (IRQS[2:0] = 000 -> INT0)
  * PL[1:0] = 00 -> 10BaseT with link test enabled (auto-detect mode)

3.3V single-board redesign (spec 2026-07-14, task 7): U1 (RTL8019AS) and U2
(AT93C46 EEPROM, directly wired to U1's own EE* pins with no buffering
between them) stay at +5V -- the RTL8019AS's DC characteristics are
datasheet-specified at Vcc=5V+-5% with no documented 3.3V mode (same
situation as MAX3241 on com_port). Only U3, the IRQ/AEN gate that bridges
U1's 5V domain onto the board's shared 3.3V bus, moves to 74LVC125A @ +3V3 --
LVC grade is required here specifically because its inputs (INT0_RAW from
U1) see a full 5V swing while its own VCC is 3.3V.

Soft card: uses ONLY ISA bus signals + power (no private nets).
"""
import mxbus
from mxbus import pin

NAME = "network"
TITLE = "Network -- RTL8019AS NE2000-compatible Ethernet (ISA8019 transcription)"
PAPER = "A3"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR] +                # A0..A19
    [pin(s, "bidirectional") for s in mxbus.DATA] +        # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "~{MEMR}", "~{MEMW}",
                               "AEN", "RESET_DRV"]] +
    [pin("IOCHRDY", "output"), pin("IRQ2", "output"),      # IRQ2 via '125
     pin("DIS_NIC", "input")]   # addr_decode JP5 level: high = NIC disabled
)


def build(sch, lib):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, rail="+5V", gnd="GND"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", gnd, kind="label", dx=0, dy=2.54)

    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ============================================================ 1. RTL8019AS ==
    U1 = sch.place("mini-xt:RTL8019AS", "U1", at=(152.4, 152.4))

    for s in mxbus.ADDR:
        L(U1, "S" + s, s, dx=-2.54)                        # SA0..SA19 -> A0..A19
    for s in mxbus.DATA:
        L(U1, "S" + s, "S" + s + "_NIC", dx=-2.54)         # SD0..SD7 -> U4 '245 (5V isolation, NOT the shared 3.3V bus)

    L(U1, "IORB", "~{IOR}", dx=-2.54)
    L(U1, "IOWB", "~{IOW}", dx=-2.54)
    L(U1, "SMEMRB", "~{MEMR}", dx=-2.54)
    L(U1, "SMEMWB", "~{MEMW}", dx=-2.54)
    L(U1, "RSTDRV", "RESET_DRV", dx=-2.54)
    L(U1, "AEN", "AEN_CHIP", dx=-2.54)                     # from U3, NOT bus AEN
    L(U1, "IOCHRDY", "IOCHRDY", dx=2.54)
    L(U1, "INT0", "INT0_RAW", dx=2.54)                     # to U3, NOT IRQ2
    L(U1, "IOCS16B", "SLOT16", dx=2.54)
    L(U1, "JP", "JP_HI", dx=2.54)
    L(U1, "BD2", "IOS1_HI", dx=2.54)                       # BD2 = IOS1
    L(U1, "AUI", "GND", dx=2.54)

    L(U1, "EECS", "EECS", dx=2.54)
    L(U1, "EESK", "EESK", dx=2.54)
    L(U1, "EEDI", "EEDI", dx=2.54)
    L(U1, "EEDO", "EEDO", dx=2.54)

    L(U1, "X1", "XTAL1", dx=2.54)
    L(U1, "X2", "XTAL2", dx=2.54)

    L(U1, "TPOUT+", "TPOUT+", dx=2.54)
    L(U1, "TPOUT-", "TPOUT-", dx=2.54)
    L(U1, "TPIN+", "TPIN+", dx=2.54)
    L(U1, "TPIN-", "TPIN-", dx=2.54)

    L(U1, "LED0", "LED_LNK", dx=2.54)
    L(U1, "LED1", "LED_ACT", dx=2.54)

    for n in ("6", "17", "47", "57", "70", "89"):
        L(U1, n, "+5V", dx=0, dy=-2.54)
    for n in ("14", "28", "44", "52", "83", "86"):
        L(U1, n, "GND", dx=0, dy=2.54)

    for name in ("SD8", "SD9", "SD10", "SD11", "SD12", "SD13", "SD14", "SD15",
                 "INT1", "INT2", "INT3", "INT4", "INT5", "INT6", "INT7",
                 "PNP", "BS0", "BS1", "BS2", "BS3", "BS4", "BA15", "PL0",
                 "~{BCS}", "BD4", "BD3", "BD1", "BD0",
                 "TX+", "TX-", "RX+", "RX-", "CD+", "CD-",
                 "LEDBNC", "LED2"):
        sch.no_connect(U1.pin_xy(name))

    sch.text(
        "Hardwired config (RSTDRV-latched, internal 100k pull-downs; open=0):\n"
        "JP=1 strap mode, IOS[3:0]=0010 -> I/O 0x340, IRQS[2:0]=000 -> INT0=IRQ2/9,\n"
        "PL[1:0]=00 -> 10BaseT + link test, BS=00000/PNP=0 -> no BROM, no PnP.\n"
        "Only JP and IOS1 (BD2) get 10k pull-ups; all other config pins\n"
        "deliberately open.", at=(228.6, 76.2))
    sch.text(
        "SLOT16: 27k pull-down = 8-bit slot (datasheet-specified value,\n"
        "not a generic 10k).", at=(228.6, 101.6))
    sch.text(
        "93C46 holds the MAC -- ships blank; program once from DOS with\n"
        "RSET8019.EXE (Manawyrm repo, Programming utilities).", at=(228.6, 116.84))
    sch.text(
        "LED semantics default to COL/RX at power-up; RSET8019 sets LEDS0=1\n"
        "for link/activity -- same behavior as the real ISA8019.", at=(228.6, 132.08))

    # ================================= 1b. data-bus isolation buffer + decode ==
    # REVIEW FIX (2026-07-14, task 7): the RTL8019AS is a 5V-only part and its
    # SD0-7 pins drive 5V TTL during I/O reads. They must NOT sit directly on the
    # shared 3.3V bus (the RP2040/PicoGUS D0-7 inputs are NOT 5V-tolerant). U4, a
    # 74LVC245A powered at +3V3 (5V-tolerant B-side faces the NIC's 5V SD pins;
    # A-side outputs only ever swing 0-3.3V), isolates them. This is a mini-xt
    # 3.3V-bus addition, not on the 5V-native upstream ISA8019.
    #
    # DIR (pin "A->B", high = A->B on the mini-xt symbol -- verified via
    #   `pins.py mini-xt:74HCT245`, pin 1 literally named "A->B"):
    #     ~{IOR}=1 (write/idle) -> A->B: bus drives NIC (writes; NIC ignores unless
    #                                    addressed + IOW).
    #     ~{IOR}=0 (read)       -> B->A: NIC drives bus. Same idiom as storage.py U8.
    # ~{OE} (pin "CE", active low) = ~{NIC_SEL}, the 0x340 window decode below, so
    #   U4 is Hi-Z on BOTH sides whenever the NIC is not the addressed target ->
    #   no contention on other cards' I/O reads, and (AEN_CHIP high) full bus
    #   release when the NIC is disabled (addr_decode JP5). One LVC245 (~4 ns) in the read path is negligible
    #   vs ISA I/O timing.
    U4 = sch.place("mini-xt:74HCT245", "U4", "74LVC245A", at=(50.8, 190.5))
    L(U4, "VCC", "+3V3", dx=0, dy=-2.54); L(U4, "GND", "GND", dx=0, dy=2.54)
    L(U4, "A->B", "~{IOR}", dx=-2.54)          # DIR: write/idle A->B, read B->A
    L(U4, "CE", "~{NIC_SEL}", dx=-2.54)        # ~OE: enabled only in the 0x340 window
    for i, s in enumerate(mxbus.DATA):
        L(U4, "A%d" % i, s, dx=-2.54)          # A-side -> shared 3.3V bus D0..D7
        L(U4, "B%d" % i, "S" + s + "_NIC", dx=2.54)  # B-side -> NIC SD0..SD7 (5V-tolerant)
    decouple("C16", (63.5, 203.2), rail="+3V3")

    # ---- 0x340 I/O-window decode (one 74HC138, all inputs 3.3V-driven) ----
    # The RTL8019AS decodes 0x340 internally, but that decode is not exposed as a
    # pin, so U4's enable needs its own copy. 0x340 (10-bit ISA I/O) => A9..A5 =
    # 1 1 0 1 0, A4..A0 selected inside the NIC. Map onto the '138:
    #   sel inputs C,B,A = A8,A7,A6 -> need 1,0,1 = binary 101 = ~Y5
    #   ~E1 = AEN_CHIP (enabled when AEN low; parks off when disabled)
    #   ~E2 = A5       (enabled when A5 = 0)
    #    E3 = A9       (enabled when A9 = 1)
    # => ~Y5 low  <=>  A9.A8.~A7.A6.~A5.~AEN_CHIP  =  I/O read/write in 0x340-0x35F.
    # 74HC138 value override (like storage.py/cpu_core): all inputs are 3.3V-driven.
    U5 = sch.place("mini-xt:74HCT138", "U5", "74HC138", at=(50.8, 101.6))
    L(U5, "VCC", "+3V3", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "A0", "A6", dx=-2.54)                 # sel LSB
    L(U5, "A1", "A7", dx=-2.54)
    L(U5, "A2", "A8", dx=-2.54)                 # sel MSB  (C,B,A = A8,A7,A6 = 101)
    L(U5, "~{E0}", "AEN_CHIP", dx=-2.54)        # ~E1: AEN low (and DIS_NIC-gated off)
    L(U5, "~{E1}", "A5", dx=-2.54)              # ~E2: A5 = 0
    L(U5, "E2", "A9", dx=-2.54)                 #  E3: A9 = 1
    L(U5, "~{Y5}", "~{NIC_SEL}", dx=2.54)       # active-low select -> U4 ~OE
    for y in ("~{Y0}", "~{Y1}", "~{Y2}", "~{Y3}", "~{Y4}", "~{Y6}", "~{Y7}"):
        sch.no_connect(U5.pin_xy(y))
    decouple("C17", (63.5, 114.3), rail="+3V3")

    # ============================================================ 2. straps =====
    # JP_HI/IOS1_HI: the RTL8019AS strap pins that must read 1 (internal
    # ~100k pulldowns read 0 unstrapped) -- pulled to the chip's own +5V.
    # AEN_CHIP park (NIC disabled): +3V3, NOT +5V (Task-10 fix) -- the net
    # also feeds U5's ~{E0} (74HC138 @ +3V3); +5V would over-drive it, and
    # U1's 5V-TTL AEN input (Vih 2.0V) reads a 3.3V park as high.
    # One 4x10k basic array (isolated elements: rails differ; one spare).
    mxbus.r_pack4(sch, "RN1", "10kx4", (231.14, 25.4),
                  [("JP_HI", "+5V"), ("IOS1_HI", "+5V"), ("AEN_CHIP", "+3V3")])
    R3 = sch.place("Device:R", "R3", "27k", at=(254.0, 25.4))
    L(R3, "1", "SLOT16", dx=0, dy=-2.54); L(R3, "2", "GND", dx=0, dy=2.54)
    R4 = sch.place("Device:R", "R4", "1M", at=(152.4, 266.7))   # near Y1, clear of U1's body
    L(R4, "1", "XTAL1", dx=0, dy=-2.54); L(R4, "2", "XTAL2", dx=0, dy=2.54)
    R5 = sch.place("Device:R", "R5", "200", at=(304.8, 152.4))
    L(R5, "1", "TPIN+", dx=0, dy=-2.54); L(R5, "2", "TPIN-", dx=0, dy=2.54)
    # (AEN_CHIP's +3V3 park lives in RN1 with the straps, above)
    R8 = sch.place("Device:R", "R8", "1k", at=(368.3, 254.0))
    L(R8, "1", "+5V", dx=0, dy=-2.54); L(R8, "2", "LNK_A", dx=0, dy=2.54)
    R9 = sch.place("Device:R", "R9", "1k", at=(381.0, 254.0))
    L(R9, "1", "+5V", dx=0, dy=-2.54); L(R9, "2", "ACT_A", dx=0, dy=2.54)

    # ============================================================ 3. EEPROM =====
    U2 = sch.place("mini-xt:AT93C46", "U2", at=(254.0, 152.4))
    L(U2, "CS", "EECS", dx=-2.54)
    L(U2, "SK", "EESK", dx=-2.54)
    L(U2, "DI", "EEDI", dx=-2.54)
    L(U2, "DO", "EEDO", dx=2.54)
    L(U2, "ORG", "+5V", dx=2.54)                            # x16 org (upstream: U2-6 on +5V)
    L(U2, "VCC", "+5V", dx=0, dy=-2.54)
    L(U2, "GND", "GND", dx=0, dy=2.54)
    sch.no_connect(U2.pin_xy("NC"))
    decouple("C1", (266.7, 165.1))

    # ============================================================ 4. IRQ/AEN gate
    # 74LVC125A value override on the HCT125 body (spec 2026-07-14): the chip's
    # OWN INT0/AEN pins stay 5V (RTL8019AS is 5V-only, see U1 note above), so
    # this buffer's inputs see 5V while its outputs (IRQ2, AEN_CHIP) drive the
    # 3.3V-domain IRQ scan chain / RTL8019AS's own 5V-tolerant TTL input --
    # LVC grade is required here specifically for the 5V-tolerant input side.
    U3 = sch.place("mini-xt:74HCT125", "U3", "74LVC125A", at=(254.0, 203.2))
    L(U3, "VCC", "+3V3", dx=0, dy=-2.54); L(U3, "GND", "GND", dx=0, dy=2.54)
    L(U3, "P1", "DIS_NIC", dx=-2.54)                        # gate-1 OE (low = enabled)
    L(U3, "P2", "INT0_RAW", dx=-2.54)
    L(U3, "P3", "IRQ2", dx=2.54)                            # tri-stated when disabled
    L(U3, "P4", "DIS_NIC", dx=-2.54)                        # gate-2 OE
    L(U3, "P5", "AEN", dx=-2.54)                            # bus AEN in
    L(U3, "P6", "AEN_CHIP", dx=2.54)                        # R7 parks it high when disabled
    for oe in ("P10", "P13"):
        L(U3, oe, "+3V3", dx=-2.54)                         # spare OEs disabled (own rail)
    for ip in ("P9", "P12"):
        L(U3, ip, "GND", dx=-2.54)                          # spare inputs tied
    for op in ("P8", "P11"):
        sch.no_connect(U3.pin_xy(op))
    decouple("C2", (266.7, 216.0), rail="+3V3")

    # (The NIC-disable jumper is addr_decode JP5 -- DIS_NIC arrives on the
    # interface; enabled by default, fit that jumper to disable.)
    sch.text(
        "Disable = addr_decode JP5 (DIS_NIC high) -> '125 tri-states IRQ2\n"
        "AND forces chip AEN high (all I/O ignored). Fully releases the\n"
        "bus for a sidecar card. Enabled by default (no jumper).", at=(254.0, 266.7))

    # ---- placed well clear of U1's body (which spans y~81-226) to avoid stray
    # ---- wire-overlap merges with U1's own pin stubs ----
    Y1 = sch.place("Device:Crystal", "Y1", "20MHz", at=(152.4, 254.0))
    L(Y1, "1", "XTAL1", dx=-2.54)
    L(Y1, "2", "XTAL2", dx=2.54)
    Cx1 = sch.place("Device:C", "C3", "20pF", at=(139.7, 266.7))
    L(Cx1, "1", "XTAL1", dx=0, dy=-2.54); L(Cx1, "2", "GND", dx=0, dy=2.54)
    Cx2 = sch.place("Device:C", "C4", "20pF", at=(165.1, 266.7))
    L(Cx2, "1", "XTAL2", dx=0, dy=-2.54); L(Cx2, "2", "GND", dx=0, dy=2.54)

    # ============================================================ 7. magnetics ===
    T1 = sch.place("mini-xt:13F-39MNL", "T1", at=(330.2, 101.6))
    L(T1, "TD+", "TPOUT+", dx=-2.54)
    L(T1, "TD-", "TPOUT-", dx=-2.54)
    L(T1, "RD+", "TPIN+", dx=-2.54)
    L(T1, "RD-", "TPIN-", dx=-2.54)
    L(T1, "TX+", "ETH_TX+", dx=2.54)
    L(T1, "TX-", "ETH_TX-", dx=2.54)
    L(T1, "RX+", "ETH_RX+", dx=2.54)
    L(T1, "RX-", "ETH_RX-", dx=2.54)
    L(T1, "TDCT", "TDCT", dx=-2.54)
    L(T1, "RDCT", "RDCT", dx=-2.54)
    L(T1, "TXCT", "TXCT", dx=2.54)
    L(T1, "RXCT", "RXCT", dx=2.54)

    Ctdct = sch.place("Device:C", "C5", "1nF", at=(317.5, 63.5))
    L(Ctdct, "1", "TDCT", dx=0, dy=-2.54); L(Ctdct, "2", "GND", dx=0, dy=2.54)
    Crdct = sch.place("Device:C", "C6", "1nF", at=(317.5, 139.7))
    L(Crdct, "1", "RDCT", dx=0, dy=-2.54); L(Crdct, "2", "GND", dx=0, dy=2.54)
    # line-side CT caps sit on the Ethernet isolation barrier -> 2 kV rating
    # (upstream ISA8019 used 1nF/2kV 1206 here); chip-side C5/C6 stay 50 V.
    Ctxct = sch.place("Device:C", "C7", "1nF/2kV", at=(342.9, 63.5))
    L(Ctxct, "1", "TXCT", dx=0, dy=-2.54); L(Ctxct, "2", "EARTH", dx=0, dy=2.54)
    Crxct = sch.place("Device:C", "C8", "1nF/2kV", at=(342.9, 139.7))
    L(Crxct, "1", "RXCT", dx=0, dy=-2.54); L(Crxct, "2", "EARTH", dx=0, dy=2.54)

    J1 = sch.place("mini-xt:RJ45_LED", "J1", at=(381.0, 101.6))
    L(J1, "P1", "ETH_TX+", dx=-2.54)
    L(J1, "P2", "ETH_TX-", dx=-2.54)
    L(J1, "P3", "ETH_RX+", dx=-2.54)
    L(J1, "P6", "ETH_RX-", dx=-2.54)
    for n in ("P4", "P5", "P7", "P8"):
        sch.no_connect(J1.pin_xy(n))
    L(J1, "LA+", "LNK_A", dx=2.54)
    L(J1, "LA-", "LED_LNK", dx=2.54)
    L(J1, "LB+", "ACT_A", dx=2.54)
    L(J1, "LB-", "LED_ACT", dx=2.54)
    L(J1, "SH1", "EARTH", dx=2.54)
    L(J1, "SH2", "EARTH", dx=2.54)

    FB1 = sch.place("Device:FerriteBead", "FB1", "120R@100MHz", at=(381.0, 152.4))
    L(FB1, "1", "EARTH", dx=-2.54); L(FB1, "2", "GND", dx=2.54)
    pf = sch.place("power:PWR_FLAG", "#FLG1", at=(381.0, 165.1))
    sch.net(pf, "1", "EARTH", kind="label", dx=0, dy=-2.54)

    # ============================================================ 8. decoupling ==
    # Row placed well clear (y >= 292.1) of both U1's body (bottom ~226) and the
    # crystal group above (bottom ~273) to avoid stray wire-overlap net merges.
    for i, x in enumerate(range(101, 247, 29)):        # 6x 100nF row
        decouple("C%d" % (9 + i), (float(x), 292.1))
    C15 = sch.place("Device:C", "C15", "47uF", at=(274.32, 292.1))   # bulk, same row
    L(C15, "1", "+5V", dx=0, dy=-2.54); L(C15, "2", "GND", dx=0, dy=2.54)

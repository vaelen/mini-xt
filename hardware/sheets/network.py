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
  * Added: a JP1 "NIC enable" jumper + 74HCT125 buffer (U3) not present on
    the reference. Closed (default) = card behaves exactly like the
    reference. Open = R6 parks ~{NET_EN} high, which tri-states IRQ2 AND
    forces the chip's AEN input high (so it ignores all I/O cycles),
    releasing both the IRQ line and the address decode for a sidecar card
    sharing this bus. This is a mini-xt-specific addition for the shared
    soft-card bus, not an upstream feature.
  * RJ45 successor part (`mini-xt:RJ45_LED`, C386757) replacing the
    reference's magjack (C133529, now EOL at JLC) -- LED polarity verified
    from EasyEDA pin names, not assumed identical.

Three hardwired choices (see strap table / Q1-Q6 in
hardware/notes/questions-network.md for the full reasoning):
  * I/O base 0x340 (IOS[3:0] = 0010)
  * IRQ2/9 (IRQS[2:0] = 000 -> INT0)
  * PL[1:0] = 00 -> 10BaseT with link test enabled (auto-detect mode)

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
    [pin("IOCHRDY", "output"), pin("IRQ2", "output")]      # IRQ2 via '125; JP1 open frees it
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
        L(U1, "S" + s, s, dx=-2.54)                        # SD0..SD7 -> D0..D7

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

    # ============================================================ 2. straps =====
    R1 = sch.place("Device:R", "R1", "10k", at=(228.6, 25.4))
    L(R1, "1", "JP_HI", dx=0, dy=-2.54); L(R1, "2", "+5V", dx=0, dy=2.54)
    R2 = sch.place("Device:R", "R2", "10k", at=(241.3, 25.4))
    L(R2, "1", "IOS1_HI", dx=0, dy=-2.54); L(R2, "2", "+5V", dx=0, dy=2.54)
    R3 = sch.place("Device:R", "R3", "27k", at=(254.0, 25.4))
    L(R3, "1", "SLOT16", dx=0, dy=-2.54); L(R3, "2", "GND", dx=0, dy=2.54)
    R4 = sch.place("Device:R", "R4", "1M", at=(152.4, 266.7))   # near Y1, clear of U1's body
    L(R4, "1", "XTAL1", dx=0, dy=-2.54); L(R4, "2", "XTAL2", dx=0, dy=2.54)
    R5 = sch.place("Device:R", "R5", "200", at=(304.8, 152.4))
    L(R5, "1", "TPIN+", dx=0, dy=-2.54); L(R5, "2", "TPIN-", dx=0, dy=2.54)
    R6 = sch.place("Device:R", "R6", "10k", at=(342.9, 190.5))
    L(R6, "1", "~{NET_EN}", dx=0, dy=-2.54); L(R6, "2", "+5V", dx=0, dy=2.54)
    R7 = sch.place("Device:R", "R7", "10k", at=(355.6, 190.5))
    L(R7, "1", "AEN_CHIP", dx=0, dy=-2.54); L(R7, "2", "+5V", dx=0, dy=2.54)
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
    U3 = sch.place("mini-xt:74HCT125", "U3", at=(254.0, 203.2))
    L(U3, "VCC", "+5V", dx=0, dy=-2.54); L(U3, "GND", "GND", dx=0, dy=2.54)
    L(U3, "P1", "~{NET_EN}", dx=-2.54)                      # gate-1 OE (low = enabled)
    L(U3, "P2", "INT0_RAW", dx=-2.54)
    L(U3, "P3", "IRQ2", dx=2.54)                            # tri-stated when JP1 open
    L(U3, "P4", "~{NET_EN}", dx=-2.54)                      # gate-2 OE
    L(U3, "P5", "AEN", dx=-2.54)                            # bus AEN in
    L(U3, "P6", "AEN_CHIP", dx=2.54)                        # R7 parks it high when JP1 open
    for oe in ("P10", "P13"):
        L(U3, oe, "+5V", dx=-2.54)                          # spare OEs disabled
    for ip in ("P9", "P12"):
        L(U3, ip, "GND", dx=-2.54)                          # spare inputs tied
    for op in ("P8", "P11"):
        sch.no_connect(U3.pin_xy(op))
    decouple("C2", (266.7, 216.0))

    # ============================================================ 5. NIC-enable jp
    JP1 = sch.place("Connector_Generic:Conn_01x02", "JP1", "NET_EN", at=(254.0, 254.0))
    L(JP1, "1", "~{NET_EN}", dx=-2.54)
    L(JP1, "2", "GND", dx=-2.54)
    sch.text(
        "JP1 closed = NIC enabled; open = R6 parks ~{NET_EN} high -> '125\n"
        "tri-states IRQ2 AND forces chip AEN high (all I/O ignored). Fully\n"
        "releases the bus for a sidecar card.", at=(254.0, 266.7))

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
    Ctxct = sch.place("Device:C", "C7", "1nF", at=(342.9, 63.5))
    L(Ctxct, "1", "TXCT", dx=0, dy=-2.54); L(Ctxct, "2", "EARTH", dx=0, dy=2.54)
    Crxct = sch.place("Device:C", "C8", "1nF", at=(342.9, 139.7))
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

    FB1 = sch.place("Device:FerriteBead", "FB1", "100R@100MHz", at=(381.0, 152.4))
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

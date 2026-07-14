"""mini-xt signal contract.

This is the integration contract every sheet builds against. Connectivity is by
NAME: a sub-sheet drives a hierarchical label whose name appears in the sheet's
PINS list; the root harness (build.py) places a sheet symbol with those same pin
names and ties identically-named pins together across all sheets, drawing the
buffered ISA backplane. Using the SAME canonical names below is what makes the
independently-authored sheets connect.

Two classes of interface, mirroring design doc S2/S8:
  * ISA backplane signals  -- the canonical bus contract and firmware-portability
    guideline for card sections (spec 2026-07-14; one integrated board, not
    separate XT and cards).
  * PRIVATE motherboard signals -- side channels the motherboard MCUs may use
    (UART link, speed select, address-counter strobes, bus-master handshake,
    expansion-port isolation). Drawn as separate pins for visibility, not
    enforcement.

Active-low signals use KiCad overbar syntax ~{NAME}.
"""

# ----- power (treated as global power nets via power symbols, not hier pins) -----
POWER = ["+5V", "+3V3", "GND"]

# ----- ISA backplane: bus groups (label form -> member list) -----
def _members(prefix, lo, hi):
    return ["%s%d" % (prefix, i) for i in range(lo, hi + 1)]

BUS_ADDR = "A[0..19]"
BUS_DATA = "D[0..7]"
BUS_IRQ = "IRQ[2..15]"
ADDR = _members("A", 0, 19)        # A0..A19  (latched address)
DATA = _members("D", 0, 7)         # D0..D7
IRQ = _members("IRQ", 2, 15)       # IRQ2..IRQ15 (AT-style 15-line soft PIC)

BUSES = {BUS_ADDR: ADDR, BUS_DATA: DATA, BUS_IRQ: IRQ}

# ----- ISA backplane: individual control / status signals -----
ISA_CTRL = [
    "~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}",   # command strobes
    "BALE",                                       # buffered address latch enable
    "AEN",                                        # address enable (DMA owns bus)
    "IOCHRDY",                                    # wait-state (cards pull low)
    "~{IOCHCK}",                                  # I/O channel check -> NMI
    "RESET_DRV",                                  # bus reset
    "CLK",                                         # 7.16 MHz system/bus clock
    "TC",                                          # DMA terminal count
    "DRQ", "~{DACK}",                              # the board's ONE DMA channel (soft-8237
                                                   # ch1; was DRQ1/~{DACK1} -- renamed
                                                   # 2026-07-14 when ch2/3 retired)
    # OSC (14.318 MHz) and ~{REFRESH} RETIRED 2026-07-14 with the 50-pin
    # header squeeze: no on-board consumer, and the planned ISA backplane
    # board re-creates both locally for vintage cards that need them.
    # ~{REFRESH}'s GPIO47 was reclaimed as ~{EXT_DACK}.
]

# ----- PRIVATE motherboard-only signals (NOT part of the ISA contract) -----
# V20 <-> Bus MCU min-mode bus-master handshake and raw CPU strobes
PRIV_CPU = [
    "HOLD", "HLDA",            # bus grant handshake
    "~{HLDA}",                 # HLDA inverted -> gates bus_mcu's counter
                               # '244s. Derived on the parallel sheet's spare
                               # 74AHC14 Schmitt gate (the board's only spare
                               # 5V-tolerant inverter, 2026-07-14 -- replaced
                               # a 74LVC04A that existed for this one gate)
    "READY",                   # folded wait input to V20
    "~{RD}",                   # raw V20 read strobe (Bus MCU sense; ~{WR} and
                               # IO/~{M} stay cpu_core-internal, gated to
                               # MEMR/W,IOR/W there -- MCU GPIO budget)
    "INTR", "~{INTA}", "NMI",  # interrupt delivery V20 <-> Bus MCU
    "~{CPURESET}",             # Bus MCU sequences V20 reset
]
# external 20-bit loadable address counter control (Bus MCU <-> counter <-> A-bus)
PRIV_COUNTER = ["CNT_CLK", "CNT_LD0", "CNT_LD1", "CNT_LD2"]
# SRAM decode side channel: DOCUMENTATION ONLY -- the 0xA0000-0xBFFFF block
# strobe never leaves cpu_core (net Y5_INT there, feeds only the SRAM#2 NAND);
# no sheet may declare it as an interface pin (video must NOT see it).
PRIV_DECODE = []
# Central I/O chip selects (addr_decode sheet -> com_port/parallel/storage,
# 2026-07-14 chip-count reduction). Shared logic factored out of the sheets,
# not an isolation break: the signal is functionally equivalent to the gate
# chips it replaced, and breaking a block out to a standalone card just means
# the card's wrapper schematic re-adds the decode alongside the bus headers
# (questions-addr_decode.md).
PRIV_CS = ["~{COM1_CS}", "~{COM2_CS}", "~{LPT_CS}", "~{IDE_CS}"]
# Peripheral IRQ requests (com_port/parallel/storage -> addr_decode, which
# owns the IRQ mapping + per-peripheral disable jumpers and drives the real
# ISA IRQ lines through one shared 74LVC125A). IRQ_COMx = raw 16550 INTRPT
# (push-pull); ~{COMx_IRQEN} = its ~{OUT2} (the PC convention's software IRQ
# gate, still honored -- it is the '125 channel's ~OE); ~{IRQ_LPT}/~{IRQ_IDE}
# = active-low assert-IRQ-high requests (the '125 inputs strap high).
PRIV_IRQREQ = ["IRQ_COM1", "IRQ_COM2", "~{COM1_IRQEN}", "~{COM2_IRQEN}",
               "~{IRQ_LPT}", "~{IRQ_IDE}"]
# Disable levels for the peripherals whose gating hardware must stay local
# (addr_decode jumpers -> video). High = disabled; pulled low on
# addr_decode, so a bare board runs everything. DIS_VID is a firmware-read
# boot strap on the video MCU GPIO42 (polarity inverted vs the
# pre-2026-07-14 on-sheet VID_EN strap). (DIS_NIC left with the RTL8019AS
# NIC, removed 2026-07-14 -- tag full-board-with-nic has the last version.)
PRIV_DIS = ["DIS_VID"]
# speed select (Bus MCU -> clock mux), set while it holds the V20 in reset
PRIV_SPEED = ["SPEED_SEL"]
# PC-speaker PWM: Bus MCU (soft-PIT ch2 / port-61h gate) -> audio sheet
PRIV_AUDIO = ["SPKR"]
# CH224K power-good (open-drain, 3V3 pull-up): power sheet -> Supervisor GPIO16
PRIV_PWR = ["PD_PG"]
# Shared programming port (Supervisor J6/SW2 -> PicoGUS RP2040 USB). A
# DOCUMENTED isolation exception: the on-board PicoGUS is otherwise a pure
# soft card; to lift it onto a standalone ISA card, delete these two nets
# and fit a local USB connector (as the reference chip-down design has).
PRIV_PROG = ["PGUS_USB_DP", "PGUS_USB_DM"]
# cross-MCU UART link (Bus MCU <-> Supervisor), full-duplex
PRIV_LINK = ["LINK_B2S", "LINK_S2B"]   # Bus->Super TX, Super->Bus TX
# Expansion-port isolation bank (sidecar <-> Bus MCU). The port's inward
# lines land on DEDICATED nets, never the internal IRQ/DRQ nets: a floating
# external line must not fight an internal driver. EXT_IRQ3/4/5/7 merge with
# their internal equivalents through bus_mcu's '32 OR rank at the '165
# collector (2026-07-14 consolidation); EXT_IRQ2/6 have no internal
# counterpart and feed the '165 directly. EXP_DDIR: Bus MCU drives the port
# data transceiver direction (inward only for reads it knows are externally
# decoded; default outward).
# (EXT_IRQ8 retired 2026-07-14 with internal IRQ6/IRQ8: no header pin can
# ever drive it. IRQ8 events are firmware-only.)
# EXT_DRQ / ~{EXT_DACK} (2026-07-14, second pass): the port's OWN single DMA
# channel on the 50-pin header. EXT_DRQ is inward (sidecar '244 -> bus_mcu
# '165 lane D6); ~{EXT_DACK} is Bus-MCU-driven (GPIO47, freed by the
# ~{REFRESH} retirement) and reaches the header through the sidecar strobe
# '244. Deliberately SEPARATE nets from the internal ch1 DRQ/~{DACK}
# (PicoGUS): a port card must never see the on-board channel's acknowledge.
PRIV_EXP = (["EXP_DDIR", "~{EXT_DACK}"] +
            ["EXT_IRQ%d" % i for i in range(2, 8)] + ["EXT_DRQ"])
# Supervisor -> POST display + console
PRIV_SUPER = ["POST_A", "POST_B", "POST_C", "POST_D", "POST_E", "POST_F", "POST_G",
              "POST_DP", "POST_DIG0", "POST_DIG1", "CONSOLE_TX", "CONSOLE_RX"]

# convenience: full ISA interface a generic soft card might list
ISA_ALL_BUSES = [BUS_ADDR, BUS_DATA, BUS_IRQ]


def pin(name, direction="bidirectional"):
    """A pin spec: (name, direction). kind is inferred ('bus' if name has [..])."""
    kind = "bus" if "[" in name else "net"
    return {"name": name, "dir": direction, "kind": kind}


def emit_interface(sch, pins, at=(25.4, 25.4), pitch=2.54):
    """Drop a hierarchical label for each interface pin in a tidy column.

    Connectivity is by name: anywhere on the sheet a component pin carrying a
    local label of the same name joins this hierarchical (cross-sheet) net.
    Call once per sheet; wire components with sch.net(..., kind='label').
    """
    x, y = at
    for i, pd in enumerate(pins):
        py = y + i * pitch
        # anchor the hier label on a stub whose far end carries a same-name
        # local label: connectivity is still by name, but neither label
        # dangles for ERC.
        sch.wire((x - pitch, py), (x, py))
        sch.label(pd["name"], (x - pitch, py), 180, justify="right")
        sch.hier_label(pd["name"], (x, py), 0, pd["dir"])


def r_pack4(sch, ref, value, at, elems):
    """Place a Device:R_Pack04 (4 ISOLATED resistors -- element k = pins k and
    9-k, matching the 4D03WGJ 0603x4 convex arrays bound in parts.py).

    elems: up to 4 (signal_net, rail_net) tuples -- signal stubs down off pins
    1-4, rails up off pins 8-5. Elements are isolated, so rails may differ
    per element. Unused elements get both pins no-connected.
    """
    rp = sch.place("Device:R_Pack04", ref, value, at=at)
    for k in range(1, 5):
        if k <= len(elems):
            sig, rail = elems[k - 1]
            sch.net(rp, str(k), sig, kind="label", dx=0, dy=2.54)
            sch.net(rp, str(9 - k), rail, kind="label", dx=0, dy=-2.54)
        else:
            sch.no_connect(rp.pin_xy(str(k)))
            sch.no_connect(rp.pin_xy(str(9 - k)))
    return rp


def power_net(sch, lib, net, at, rot=0):
    """Place the appropriate power symbol for a power net at a location."""
    libid = {"+5V": "power:+5V", "+3V3": "power:+3V3", "GND": "power:GND"}[net]
    return sch.power(libid, "#PWR", at=at, rotation=rot)

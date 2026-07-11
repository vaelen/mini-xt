"""mini-xt signal contract.

This is the integration contract every sheet builds against. Connectivity is by
NAME: a sub-sheet drives a hierarchical label whose name appears in the sheet's
PINS list; the root harness (build.py) places a sheet symbol with those same pin
names and ties identically-named pins together across all sheets, drawing the
buffered ISA backplane. Using the SAME canonical names below is what makes the
independently-authored sheets connect.

Two classes of interface, mirroring design doc S2/S8:
  * ISA backplane signals  -- the portability contract; any soft card may use
    ONLY these. Naming a private signal here would be an isolation leak.
  * PRIVATE motherboard signals -- side channels the class-1 motherboard MCUs may
    use (UART link, speed select, address-counter strobes, bus-master handshake).
    Drawn as separate pins so leaks are visible.

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
    "OSC",                                         # 14.31818 MHz oscillator
    "TC",                                          # DMA terminal count
    "DRQ1", "DRQ2", "DRQ3",                       # DMA requests
    "~{DACK1}", "~{DACK2}", "~{DACK3}",           # DMA acknowledges
    "~{REFRESH}",                                  # refresh strobe (pin 35, Bus MCU drives)
]

# ----- PRIVATE motherboard-only signals (NOT part of the ISA contract) -----
# V20 <-> Bus MCU min-mode bus-master handshake and raw CPU strobes
PRIV_CPU = [
    "HOLD", "HLDA",            # bus grant handshake
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
        sch.hier_label(pd["name"], (x, y + i * pitch), 0, pd["dir"])


def power_net(sch, lib, net, at, rot=0):
    """Place the appropriate power symbol for a power net at a location."""
    libid = {"+5V": "power:+5V", "+3V3": "power:+3V3", "GND": "power:GND"}[net]
    return sch.power(libid, "#PWR", at=at, rotation=rot)

"""Shared ISA expansion connector -- STANDARD 8-bit ISA pinout on a 60-pin
2.54 mm header (2x30), laid out exactly like the PicoGUS `Bus_ISA_8bit` header so
our sidecar and dev cards are pin-compatible with real 8-bit ISA cards. The 60-pin
ribbon/header is far easier to source than a 64-pin one.

We don't use the ISA analog rails (design S13: no +-12V / -5V), so those three
pins are reclaimed for signals we DO need:

    pin  7 : -5V   -> ~{IOCHCK}   (I/O channel check -> NMI)
    pin 11 : -12V  -> GND         (extra return; improves ribbon signal integrity)
    pin 15 : +12V  -> IRQ8        (RTC interrupt)

Everything else follows the standard ISA edge pinout (our net names in []):
RESET DRV[RESET_DRV], SD0-7[D0-D7], SA0-19[A0-A19], SMEMR/W[~{MEMR}/~{MEMW}],
IOR/W[~{IOR}/~{IOW}], IO CH RDY[IOCHRDY], AEN, CLK, OSC, ALE[BALE], T/C[TC],
IRQ2-7, DRQ1-3, DACK1-3[~{DACK1..3}].  Pin 35 (the DACK0/REFRESH# pin) carries
~{REFRESH}, driven by the Bus MCU so DRAM-based ISA cards get refreshed.  Pin 13
(the reserved/0WS pin) is left
unconnected, as on the PicoGUS header.

Connectivity is by net NAME, so two headers with the same nets form a chainable
IN/OUT pass-through. `remap` renames pins for a specific board (e.g. a COM card
tapping IRQ4 as COM_IRQ); apply the same remap to both headers on that card.

Dropped vs. our previous 64-pin header: the non-standard IRQ10/11/14 (they were
spare/unused, and on a real AT live on the 16-bit extension connector, not here).
"""
import mxbus  # noqa: F401  (kept for callers; net names are spelled out below)
from mxbus import pin

_NC = None  # pin 13: reserved / 0WS# on real ISA -- left unconnected

# Standard 8-bit ISA pinout, pin 1..60 (odd = solder/B row, even = component/A
# row), with our three substitutions. Index i -> net on pin (i+1).
PIN_NETS = [
    "RESET_DRV",  "D7",    # 1  2
    "+5V",        "D6",    # 3  4
    "IRQ2",       "D5",    # 5  6
    "~{IOCHCK}",  "D4",    # 7(-5V->IOCHCK)  8
    "DRQ2",       "D3",    # 9  10
    "GND",        "D2",    # 11(-12V->GND)  12
    _NC,          "D1",    # 13(reserved)  14
    "IRQ8",       "D0",    # 15(+12V->IRQ8) 16
    "GND",        "IOCHRDY",   # 17 18
    "~{MEMW}",    "AEN",       # 19 20
    "~{MEMR}",    "A19",       # 21 22
    "~{IOW}",     "A18",       # 23 24
    "~{IOR}",     "A17",       # 25 26
    "~{DACK3}",   "A16",       # 27 28
    "DRQ3",       "A15",       # 29 30
    "~{DACK1}",   "A14",       # 31 32
    "DRQ1",       "A13",       # 33 34
    "~{REFRESH}", "A12",       # 35(DACK0/REFRESH# -- driven by Bus MCU)  36
    "CLK",        "A11",       # 37 38
    "IRQ7",       "A10",       # 39 40
    "IRQ6",       "A9",        # 41 42
    "IRQ5",       "A8",        # 43 44
    "IRQ4",       "A7",        # 45 46
    "IRQ3",       "A6",        # 47 48
    "~{DACK2}",   "A5",        # 49 50
    "TC",         "A4",        # 51 52
    "BALE",       "A3",        # 53 54
    "+5V",        "A2",        # 55 56
    "OSC",        "A1",        # 57 58
    "GND",        "A0",        # 59 60
]
assert len(PIN_NETS) == 60, "expected 60 pins, got %d" % len(PIN_NETS)

# Signals carried (the sheet interface; power stays global so it's excluded here).
_SIGNALS = [n for n in PIN_NETS if n and n not in ("+5V", "GND")]
ISA_PINS = [pin(n) for n in dict.fromkeys(_SIGNALS)]   # de-duped, order-preserving


def place_header(sch, ref, at, label=None, remap=None):
    """Place a 60-pin 2x30 ISA header (standard pinout) at `at`, labelling each
    pin with its bus net name. Two headers with identical nets pass through.
    `remap` {net: newname} renames pins for a specific board."""
    remap = remap or {}
    J = sch.place("Connector_Generic:Conn_02x30_Odd_Even", ref,
                  label or "ISA 8-bit (60p)", at=at)
    for i, net in enumerate(PIN_NETS):
        num = str(i + 1)
        if net is _NC:
            sch.no_connect(J.pin_xy(num))       # reserved / 0WS# -- unconnected
            continue
        dx = -2.54 if (i + 1) % 2 == 1 else 2.54  # odd = left row, even = right row
        sch.net(J, num, remap.get(net, net), kind="label", dx=dx)
    return J

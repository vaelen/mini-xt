"""Shared ISA expansion connector -- project-private 8-bit ISA subset on a
50-pin 2.54 mm header (2x25).  50-way IDC ribbons/headers are far easier to
source than 60-way ones; the cost is that this is OUR pinout now, not the
PicoGUS/standard-edge layout the old 60-pin header mirrored (2026-07-14).

vs. real 8-bit ISA the header carries everything a card needs EXCEPT:

  * OSC (14.318 MHz)   -- dropped to fit 50 pins; no on-board consumer.
  * ~{REFRESH}         -- dropped; no DRAM-refresh support on the port.
                          The planned ISA backplane board re-creates both
                          locally for any vintage card that needs them.
  * DRQ2/3, DACK0/2/3  -- ONE DMA channel exists (DRQ / ~{DACK}, the
                          soft-8237's ch1 timing), pins 9/13.
  * -5V / +-12V        -- never carried (design S13).

Pins 1-38 keep the classic ISA B/A-row ordering where possible (odd = B/left,
even = A/right); pins 41-50 pack the remaining address lines.  +5V on pin 3
(~3A at 2.54 mm header ratings; the motherboard fuses it at 2A), grounds on
11 and 39.

Connectivity is by net NAME, so two headers with the same nets form a chainable
IN/OUT pass-through. `remap` renames pins for a specific board (e.g. the
sidecar's port-local X_* nets); apply the same remap to both headers on a card.
"""
import mxbus  # noqa: F401  (kept for callers; net names are spelled out below)
from mxbus import pin

# Pin 1..50 (odd = left row, even = right row). Index i -> net on pin (i+1).
PIN_NETS = [
    "RESET_DRV",  "D7",        #  1  2
    "+5V",        "D6",        #  3  4
    "IRQ2",       "D5",        #  5  6
    "~{IOCHCK}",  "D4",        #  7  8
    "DRQ",        "D3",        #  9 10
    "GND",        "D2",        # 11 12
    "~{DACK}",    "D1",        # 13 14
    "TC",         "D0",        # 15 16
    "~{MEMW}",    "IOCHRDY",   # 17 18
    "~{MEMR}",    "AEN",       # 19 20
    "~{IOW}",     "A19",       # 21 22
    "~{IOR}",     "A18",       # 23 24
    "CLK",        "A17",       # 25 26
    "BALE",       "A16",       # 27 28
    "IRQ7",       "A15",       # 29 30
    "IRQ6",       "A14",       # 31 32
    "IRQ5",       "A13",       # 33 34
    "IRQ4",       "A12",       # 35 36
    "IRQ3",       "A11",       # 37 38
    "GND",        "A10",       # 39 40
    "A8",         "A9",        # 41 42
    "A6",         "A7",        # 43 44
    "A4",         "A5",        # 45 46
    "A2",         "A3",        # 47 48
    "A0",         "A1",        # 49 50
]
assert len(PIN_NETS) == 50, "expected 50 pins, got %d" % len(PIN_NETS)

# Signals carried (the sheet interface; power stays global so it's excluded here).
_SIGNALS = [n for n in PIN_NETS if n not in ("+5V", "GND")]
ISA_PINS = [pin(n) for n in dict.fromkeys(_SIGNALS)]   # de-duped, order-preserving


def place_header(sch, ref, at, label=None, remap=None):
    """Place a 50-pin 2x25 ISA header at `at`, labelling each pin with its bus
    net name. Two headers with identical nets pass through. `remap`
    {net: newname} renames pins for a specific board; apply the same remap to
    both headers on that board."""
    remap = remap or {}
    J = sch.place("Connector_Generic:Conn_02x25_Odd_Even", ref,
                  label or "ISA 8-bit (50p)", at=at)
    for i, net in enumerate(PIN_NETS):
        num = str(i + 1)
        dx = -2.54 if (i + 1) % 2 == 1 else 2.54  # odd = left row, even = right row
        sch.net(J, num, remap.get(net, net), kind="label", dx=dx)
    return J

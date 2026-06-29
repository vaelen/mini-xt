"""Shared ISA expansion connector.

A 2x32 (64-pin) 2.54 mm header carrying the FULL buffered 8-bit XT/ISA bus with
interleaved grounds, two +5V pins, and one keyed (no-connect) pin to prevent
reversed insertion (design doc S4.3). Connectivity is by net NAME, so placing two
headers with the same nets on a board makes a chainable IN/OUT pass-through.

Used by:
  * the motherboard `sidecar` sheet (one header), and
  * each standalone soft-card PCB (`card_*`), as two chainable headers so cards
    can be daisy-chained header-to-header during development.
"""
import mxbus
from mxbus import pin

# The full ISA bus exposed as a sheet interface (portability contract, S2/S8).
ISA_PINS = (
    [pin(s) for s in mxbus.ADDR] +
    [pin(s) for s in mxbus.DATA] +
    [pin(s) for s in mxbus.IRQ] +
    [pin(s) for s in ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN",
                      "IOCHRDY", "~{IOCHCK}", "CLK", "OSC", "RESET_DRV", "TC",
                      "DRQ1", "DRQ2", "DRQ3", "~{DACK1}", "~{DACK2}", "~{DACK3}"]]
)

_GND, _V5, _KEY = "GND", "+5V", None
_CTRL = ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN",
         "IOCHRDY", "~{IOCHCK}", "CLK", "OSC", "RESET_DRV"]
_DMA = ["TC", "DRQ1", "DRQ2", "DRQ3", "~{DACK1}", "~{DACK2}", "~{DACK3}"]
_IRQ = ["IRQ2", "IRQ3", "IRQ4", "IRQ5", "IRQ6", "IRQ7", "IRQ8",  # 8-bit + RTC
        "IRQ10", "IRQ11", "IRQ14"]                                # extended (S14)


def pin_sequence():
    """The 64-pin order. A GND is dropped at each functional-group boundary so a
    return runs alongside every signal cluster (interleaved-ground rule, S4.3)."""
    seq = [_V5, _GND]                          # 1-2   : top power pair
    seq += list(mxbus.ADDR[0:10]) + [_GND]     # 3-13  : A0-A9   + gnd
    seq += list(mxbus.ADDR[10:20]) + [_GND]    # 14-24 : A10-A19 + gnd
    seq += list(mxbus.DATA) + [_GND]           # 25-33 : D0-D7   + gnd
    seq += _CTRL + [_GND]                       # 34-45 : command/control + gnd
    seq += _DMA                                 # 46-52 : DMA group
    seq += _IRQ                                 # 53-62 : IRQ lines (incl IRQ8 = RTC)
    seq += [_KEY, _V5]                          # 63-64 : key pin, +5V
    assert len(seq) == 64, "header is 64 pins, got %d" % len(seq)
    return seq


def place_header(sch, ref, at, label=None, remap=None):
    """Place a 2x32 ISA header at `at`, labelling each pin with its bus net name.
    Returns the connector. Two headers with identical nets form a pass-through.

    `remap` {net: newname} renames pins for a specific board (e.g. a card that
    taps IRQ4 as its generic COM_IRQ). Apply the SAME remap to both headers so the
    pass-through stays consistent within that card's schematic."""
    remap = remap or {}
    J = sch.place("Connector_Generic:Conn_02x32_Odd_Even", ref,
                  label or "ISA 2x32", at=at)
    for i, net in enumerate(pin_sequence()):
        num = str(i + 1)
        if net is _KEY:
            sch.no_connect(J.pin_xy(num))       # keyed slot: plugged on the ribbon
            continue
        dx = -2.54 if (i + 1) % 2 == 1 else 2.54  # odd=left col, even=right col
        sch.net(J, num, remap.get(net, net), kind="label", dx=dx)
    return J

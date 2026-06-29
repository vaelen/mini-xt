"""Sidecar -- the motherboard's 2x32 (64-pin) IDC ISA expansion header (S4.3).

Instead of on-board slots, a single 2.54 mm 2x32 IDC ribbon header carries the
FULL buffered 8-bit XT/ISA signal set off-board. The header itself is the shared
`isa_conn` building block (also used as the IN/OUT headers on each standalone
soft-card PCB), so the motherboard edge and the dev cards speak the identical
pinout and chain together. Pure pass-through to the backplane -- no active parts.
"""
import mxbus
import isa_conn

NAME = "sidecar"
TITLE = "Sidecar -- 2x32 IDC ISA expansion header"

# Full ISA bus contract exposed as the sheet interface (S2/S8 portability rule).
PINS = isa_conn.ISA_PINS


def build(sch, lib, expose=True):
    if expose:
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    isa_conn.place_header(sch, "J1", (177.8, 152.4))
    # cable bypass / power anchors
    for n, x in [(1, 205.74), (2, 218.44)]:
        c = sch.place("Device:C", "C%d" % n, "100nF", at=(x, 134.62))
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)
    sch.text("J1: 2x32 IDC -- full buffered 8-bit ISA bus off-board (S4.3); "
             "same pinout as the soft-card IN/OUT headers (isa_conn).", (139.7, 106.68))
    sch.text("KEY = pin 63: no-connect / plugged ribbon hole -- prevents reversed "
             "insertion.", (139.7, 200.66))

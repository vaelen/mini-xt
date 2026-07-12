"""Sidecar -- the motherboard's 60-pin (2x30) ISA expansion header (S4.3).

Instead of on-board slots, a single 2.54 mm 2x30 (60-pin) ribbon header carries the
FULL buffered 8-bit XT/ISA signal set off-board. The header itself is the shared
`isa_conn` building block (also used as the IN/OUT headers on each standalone
soft-card PCB), so the motherboard edge and the dev cards speak the identical
pinout and chain together. The +5V feed is fused (2A polyfuse) + TVS-clamped
downstream (SMBJ5.0A) to protect the motherboard from a shorted or misbehaving
ISA card. Header power pins are ~3A each; keep daisy-chains to 2-3 cards.
Pure pass-through to the backplane -- no active parts otherwise.
"""
import mxbus
import isa_conn

NAME = "sidecar"
TITLE = "Sidecar -- 60-pin (2x30) ISA expansion header"

# Full ISA bus contract exposed as the sheet interface (S2/S8 portability rule).
PINS = isa_conn.ISA_PINS


def build(sch, lib, expose=True):
    if expose:
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    isa_conn.place_header(sch, "J1", (177.8, 152.4), remap={"+5V": "+5V_ISA"})
    # +5V feed protection (design review 2026-07-11): a shorted/misbehaving
    # expansion card must not drag down or back-drive the motherboard rail.
    F1 = sch.place("Device:Polyfuse", "F1", "2A", at=(203.2, 109.22))
    sch.net(F1, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(F1, "2", "+5V_ISA", kind="label", dx=0, dy=2.54)
    D1 = sch.place("Device:D_Zener", "D1", "SMBJ5.0A", at=(218.44, 109.22))
    sch.net(D1, "K", "+5V_ISA", kind="label", dx=0, dy=-2.54)   # clamp back-fed >5V
    sch.net(D1, "A", "GND", kind="label", dx=0, dy=2.54)
    C3 = sch.place("Device:C_Polarized", "C3", "22uF", at=(231.14, 134.62))
    sch.net(C3, "1", "+5V_ISA", kind="label", dx=0, dy=-2.54)   # bulk downstream of fuse
    sch.net(C3, "2", "GND", kind="label", dx=0, dy=2.54)
    # cable bypass / power anchors
    for n, x in [(1, 205.74), (2, 218.44)]:
        c = sch.place("Device:C", "C%d" % n, "100nF", at=(x, 134.62))
        sch.net(c, "1", "+5V_ISA", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)
    sch.text("J1: 60-pin (2x30) -- standard 8-bit ISA pinout off-board (S4.3); "
             "same as the soft-card IN/OUT headers (isa_conn). -5V/+-12V reclaimed "
             "for ~{IOCHCK}/GND/GND. +5V feed fused (2A polyfuse) + TVS-clamped; "
             "header power pins ~3A each so keep daisy-chains to 2-3 cards.", (139.7, 106.68))
    sch.text("Pin 13 = reserved/0WS# (unconnected), per the standard/PicoGUS header.",
             (139.7, 200.66))

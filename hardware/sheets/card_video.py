"""card_video -- standalone Video soft-card PCB with chainable ISA headers.

Post-3.3V-redesign target: the motherboard's internal bus is now 3.3V end to
end, so this card is a genuine 5V ISA card -- it plugs into the motherboard's
buffered expansion port (design doc S4.3), not a bare internal tap. It keeps
its own local level shifting: the video sheet's 4x 74LVC245A (kept as a
PIO-driven time-share address/data mux for RP2350B GPIO budget reasons) double
as the 3.3V<->5V bridge to that 5V ISA bus here, same as any real period
card would need.

Combines the video soft-card schematic with two 60-pin (2x30) ISA headers (J_IN / J_OUT,
the shared isa_conn building block). The bus enters J_IN, passes straight through
to J_OUT (same nets), and the card logic taps it by name -- so this soft card is
its own PCB and several can be daisy-chained header-to-header for development.
All bus signals AND power (+5V/GND) arrive via the headers, so
this sheet has no parent interface: it is a complete board.
"""
import isa_conn
import video as card

NAME = "card_video"
TITLE = "Video soft-card PCB (chainable ISA)"
PAPER = "A2"               # extra room for the soft card + two 60-pin ISA headers
PINS = []                  # standalone PCB -- bus + power come through the headers


def build(sch, lib):
    # Two chainable ISA headers; identical nets => J_IN <-> J_OUT pass-through.
    isa_conn.place_header(sch, "J_IN",  (445.0, 152.4), label="ISA IN")
    isa_conn.place_header(sch, "J_OUT", (508.0, 152.4), label="ISA OUT")
    # The soft-card logic, tied to the same bus net names (expose=False: no parent
    # hierarchical pins -- everything joins the on-card header nets by name).
    card.build(sch, lib, expose=False)
    # DIS_VID is a motherboard net (addr_decode JP5); standalone, the wrapper
    # re-adds the strap locally (the documented PRIV_* lift pattern): pulled
    # low = enabled by default, fit JP2 to disable. 3V3_VID levels -- the
    # strap feeds the module GPIO, not the 5V ISA side.
    JP2 = sch.place("Connector_Generic:Conn_01x02", "JP2", "DIS_VID", at=(121.92, 40.64))
    sch.net(JP2, "Pin_1", "DIS_VID", kind="label", dx=2.54)
    sch.net(JP2, "Pin_2", "3V3_VID", kind="label", dx=2.54)
    r = sch.place("Device:R", "R30", "10k", at=(121.92, 60.96))
    sch.net(r, "1", "DIS_VID", kind="label", dx=0, dy=-2.54)
    sch.net(r, "2", "GND", kind="label", dx=0, dy=2.54)
    sch.text("Standalone Video PCB: ISA bus chains J_IN -> J_OUT; card logic taps "
             "the bus by name. Daisy-chain cards header-to-header (isa_conn, S4.3).",
             (38.1, 12.7))

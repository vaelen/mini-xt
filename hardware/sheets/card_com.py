"""card_com -- standalone Serial (COM) soft-card PCB with chainable ISA headers.

Combines the com_port soft-card schematic with two 2x32 ISA headers (J_IN / J_OUT,
the shared isa_conn building block). The bus enters J_IN, passes straight through
to J_OUT (same nets), and the card logic taps it by name -- so this soft card is
its own PCB and several can be daisy-chained header-to-header for development
(design doc S4.3). All bus signals AND power (+5V/GND) arrive via the headers, so
this sheet has no parent interface: it is a complete board.
"""
import isa_conn
import com_port as card

NAME = "card_com"
TITLE = "Serial (COM) soft-card PCB (chainable ISA)"
PAPER = "A2"               # extra room for the soft card + two 64-pin headers
PINS = []                  # standalone PCB -- bus + power come through the headers


def build(sch, lib):
    # Two chainable ISA headers; identical nets => J_IN <-> J_OUT pass-through.
    isa_conn.place_header(sch, "J_IN",  (445.0, 152.4), label="ISA IN", remap={"IRQ4": "COM_IRQ"})
    isa_conn.place_header(sch, "J_OUT", (508.0, 152.4), label="ISA OUT", remap={"IRQ4": "COM_IRQ"})
    # The soft-card logic, tied to the same bus net names (expose=False: no parent
    # hierarchical pins -- everything joins the on-card header nets by name).
    card.build(sch, lib, expose=False)
    sch.text("Standalone Serial (COM) PCB: ISA bus chains J_IN -> J_OUT; card logic taps "
             "the bus by name. Daisy-chain cards header-to-header (isa_conn, S4.3).",
             (38.1, 12.7))

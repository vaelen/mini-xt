"""card_com -- standalone Serial (COM) soft-card PCB with chainable ISA headers.

Combines the com_port soft-card schematic with two 60-pin (2x30) ISA headers (J_IN / J_OUT,
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
PAPER = "A2"               # extra room for the soft card + two 60-pin ISA headers
PINS = []                  # standalone PCB -- bus + power come through the headers


def build(sch, lib):
    # Two chainable ISA headers; identical nets => J_IN <-> J_OUT pass-through.
    # (No IRQ remap here: the headers carry the standard IRQ3/IRQ4 nets and JP2
    # below jumpers COM_IRQ onto whichever matches the J2 base-address strap.)
    isa_conn.place_header(sch, "J_IN",  (445.0, 152.4), label="ISA IN")
    isa_conn.place_header(sch, "J_OUT", (508.0, 152.4), label="ISA OUT")
    # The soft-card logic, tied to the same bus net names (expose=False: no parent
    # hierarchical pins -- everything joins the on-card header nets by name).
    card.build(sch, lib, expose=False)
    # IRQ strap: follows the base-address strap (J2) -- IRQ4 for 0x3F8/COM1,
    # IRQ3 for 0x2F8/COM2 (previously hard-wired to IRQ4 regardless of J2).
    jp = sch.place("Connector_Generic:Conn_01x03", "JP2", "IRQ strap", at=(419.1, 152.4))
    sch.net(jp, "Pin_1", "IRQ4", kind="label", dx=2.54)
    sch.net(jp, "Pin_2", "COM_IRQ", kind="label", dx=2.54)
    sch.net(jp, "Pin_3", "IRQ3", kind="label", dx=2.54)
    sch.text("Standalone Serial (COM) PCB: ISA bus chains J_IN -> J_OUT; card logic taps "
             "the bus by name. Daisy-chain cards header-to-header (isa_conn, S4.3).",
             (38.1, 12.7))
    sch.text("JP2: 1-2 = IRQ4 (strap J2 to 0x3F8/COM1), 2-3 = IRQ3 (0x2F8/COM2)",
             (38.1, 17.78))

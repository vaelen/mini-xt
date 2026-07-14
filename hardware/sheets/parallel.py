"""parallel -- discrete 74HC parallel printer port (LPT1) @ I/O 0x378/0x278 + DB25.

Design doc S11.2. The bus-interface plumbing is central (2026-07-14
chip-count reduction): the block decode arrives ready-made as ~{LPT_CS} and
the IRQ leaves as an active-low request ~{IRQ_LPT} (mxbus.PRIV_CS /
PRIV_IRQREQ -- shared logic factored out, not an isolation break; a
standalone-card wrapper would re-add decode + IRQ driver alongside the bus
headers). addr_decode's shared '125 drives IRQ7 from the request; the
base address is hardwired 0x378 and the disable jumper is addr_decode JP3
(enabled by default, fit the jumper to disable). U9's spare gate also hosts
the motherboard's HLDA inversion (see the U9 comment).

Three classic registers in the 0x378 block (Centronics/SPP):
  * 0x378  Data    (R/W)  -- 74LVC574A output latch -> DB25 pins 2-9
                             read-back via 74LVC245A onto the bus
  * 0x379  Status  (RO )  -- 74LVC244A buffers Busy/Ack/PaperEnd/Select/Error
  * 0x37A  Control (R/W)  -- 74LVC574A output latch (Strobe/AutoFd/Init/SlctIn
                             + IRQ-enable); read-back via 74LVC244A

Address decode: 74HC138 selects the three registers (A0-A2) inside the
~{LPT_CS} block match from addr_decode. One 74HC32 (U10) ORs the register
selects with ~{IOR}/~{IOW} for the read enables and rising-edge '574 write
clocks; the fifth strobe (~{RD_CTRL}) is NAND-built from U12's spare gates
(U11, a '32 carrying that one gate, deleted 2026-07-14). IRQ7 is the
(gated) ~Ack edge -- normally polled.

3.3V single-board redesign (spec 2026-07-14, task 7): the whole sheet moves
to +3V3 (no chip on this sheet stays 5V -- unlike com_port/network/storage,
the DB25 Centronics connector carries no VCC pin, so there's no equivalent
"external device needs real 5V" case here). Every part with a pin tied
directly to a DB25-connected net (U1/U2/U4/U5, the data+control latches and
their read-backs; U3, the status read-back; U9, the ~Ack/Busy/Strobe/
AutoFeed/SelectIn inverter) moves to a 5V-tolerant-input grade (LVC or, for
U9's hex-inverter body, 74AHC14 -- see questions-parallel.md for why U5 and
U9 needed this even though the task-7 brief's swap table didn't list them).
Purely-internal decode glue (U6, U10, U12) is plain HC-grade.
"""
import mxbus
from mxbus import pin

NAME = "parallel"
TITLE = "Parallel port (LPT1) -- 74HCT574/244/245 @ 0x378 + DB25"

# ISA signals + power + the central ~{LPT_CS} / ~{IRQ_LPT}.  DB25 is LOCAL.
PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:3]] +           # A0..A2 (register select)
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin("~{IOR}", "input"), pin("~{IOW}", "input"),
     pin("~{LPT_CS}", "input")] +  # central block decode (addr_decode sheet);
                                   # no RESET_DRV: the '574s have no reset pin --
                                   # BIOS initializes 0x378/0x37A at POST
    [pin("~{IRQ_LPT}", "output"),  # active-low IRQ request -> addr_decode's
                                   # '125 drives IRQ7 (LPT1 convention)
     # NOT LPT signals: U9 gate 1 hosts the motherboard's HLDA inversion
     # (the board's only spare 5V-tolerant inverter -- see U9 comment)
     pin("HLDA", "input"), pin("~{HLDA}", "output")]
)


def build(sch, lib, expose=True):
    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # connectivity-by-name helper: stub a pin out to a local label
    def L(c, p, net, dx=2.54, dy=0.0):
        sch.net(c, p, net, kind="label", dx=dx, dy=dy)

    def pwr(c):
        L(c, "VCC", "+3V3", dx=0, dy=-2.54)
        L(c, "GND", "GND", dx=0, dy=2.54)

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+3V3", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # ============================================================
    # Address decode -- the 0x378/0x278 block match arrives ready-made as
    # ~{LPT_CS} from the central addr_decode sheet (2026-07-14 chip-count
    # reduction; the old on-card 2x 74HC08 AND tree lives there now).
    # A0..A2 -> register offset via U6 below.
    # ============================================================
    # 74AHC14 value override on the HCT04 body (spec 2026-07-14, not in the
    # task-7 brief's swap table -- added because this gate is directly wired
    # to the DB25 boundary on BOTH sides: P_ACK/P_BUSY are raw connector
    # inputs (no buffer ahead of them) and P_STROBE/P_AUTOFD/P_SLIN drive
    # DB25 pins directly. A plain 3.3V-VCC HC part is not guaranteed
    # 5V-tolerant on its inputs, so this needs the same 5V-tolerant-input
    # grade as U3/U5. 74AHC14 (Schmitt-trigger hex inverter, "5V-tolerant
    # in" per parts.py) is already bound on this body from picogus -- reused
    # here rather than adding a new (lib_id, value) entry for a bare LVC04A.
    U9 = sch.place("mini-xt:74HCT04", "U9", "74AHC14", at=(76.2, 177.8))   # inverters
    pwr(U9)
    # Gate 1 is a LODGER, not LPT logic: it hosts the motherboard's bus-grant
    # inversion, HLDA -> ~{HLDA} (mxbus.PRIV_CPU), which gates the address
    # counter's '244s on bus_mcu. It lives here because this AHC14 is the
    # board's only spare 5V-tolerant inverter (HLDA is a raw 5V V20 output)
    # -- using it deleted bus_mcu's U17, a 74LVC04A carrying 1 of 6 gates.
    # The Schmitt input is a bonus; a lifted standalone LPT card would just
    # ground this input again (the motherboard would need its inverter back).
    L(U9, "P1", "HLDA", dx=-2.54)              # V20 bus grant (5V) in
    L(U9, "P2", "~{HLDA}")                     # -> bus_mcu counter-'244 ~OE
    L(U9, "P3", "P_ACK", dx=-2.54); L(U9, "P4", "ACK_POS")        # ~Ack -> +pulse
    L(U9, "P5", "CTRL0", dx=-2.54); L(U9, "P6", "P_STROBE")       # Strobe (inv)
    L(U9, "P9", "CTRL1", dx=-2.54); L(U9, "P8", "P_AUTOFD")       # AutoFeed (inv)
    L(U9, "P11", "CTRL3", dx=-2.54); L(U9, "P10", "P_SLIN")       # SelectIn (inv)
    L(U9, "P13", "P_BUSY", dx=-2.54); L(U9, "P12", "BUSY_N")      # Busy -> ~Busy (status bit 7)

    # IRQ request: U12 NAND gate 1 makes ~{IRQ_LPT}, the active-low
    # assert-IRQ7 request -- low only for the ~Ack pulse while IRQ_EN
    # (control bit 4) is set, idle high otherwise. The tri-state line driver
    # itself is addr_decode's shared '125 (this request is its channel ~OE,
    # input strapped high there), so IRQ7 stays shareable exactly as before.
    # NOTE the ISA ~Ack pulse is 1-12 us and is NOT latched here (real SPP
    # behaviour): the Bus MCU's '165 IRQ poll loop must run faster than the
    # shortest pulse, or sample IRQ7 via PIO.
    # 74HC00 value override (spec 2026-07-14): ACK_POS is one hop downstream
    # of U9's buffering (not a raw DB25 tie), so plain HC-grade is correct.
    U12 = sch.place("mini-xt:74HCT00", "U12", "74HC00", at=(266.7, 76.2))
    pwr(U12)
    L(U12, "P1", "ACK_POS", dx=-2.54); L(U12, "P2", "IRQ_EN", dx=-2.54)
    L(U12, "P3", "~{IRQ_LPT}")
    # Gates 2-4: ~{RD_CTRL} = ~{SEL_CTRL} | ~{IOR}, built from the three
    # spare NANDs (2026-07-14 -- this absorbed U11, a 74HC32 that carried
    # only this one OR gate). OR = NAND of the inverted inputs; the two
    # extra gate delays (~20-30ns at HC/3.3V) are noise in an ISA read cycle.
    L(U12, "P4", "~{SEL_CTRL}", dx=-2.54); L(U12, "P5", "~{SEL_CTRL}", dx=-2.54)
    L(U12, "P6", "SEL_CTRL_POS")
    L(U12, "P9", "~{IOR}", dx=-2.54); L(U12, "P10", "~{IOR}", dx=-2.54)
    L(U12, "P8", "IOR_POS")
    L(U12, "P12", "SEL_CTRL_POS", dx=-2.54); L(U12, "P13", "IOR_POS", dx=-2.54)
    L(U12, "P11", "~{RD_CTRL}")

    # 74HC138 value override (spec 2026-07-14): purely internal address
    # decode (A0-2, AEN, ~{LPT_EN}, ADDR_MATCH), no DB25 exposure.
    U6 = sch.place("mini-xt:74HCT138", "U6", "74HC138", at=(139.7, 177.8))  # register select
    pwr(U6)
    L(U6, "A0", "A0", dx=-2.54); L(U6, "A1", "A1", dx=-2.54); L(U6, "A2", "A2", dx=-2.54)
    L(U6, "~{E0}", "~{LPT_CS}", dx=-2.54)  # central block match (AEN-gated there;
    L(U6, "~{E1}", "GND", dx=-2.54)        #  its DIS_LPT jumper is the disable)
    L(U6, "E2", "+3V3", dx=-2.54)
    L(U6, "~{Y0}", "~{SEL_DATA}")        # 0x378
    L(U6, "~{Y1}", "~{SEL_STAT}")        # 0x379
    L(U6, "~{Y2}", "~{SEL_CTRL}")        # 0x37A
    for y in ("~{Y3}", "~{Y4}", "~{Y5}", "~{Y6}", "~{Y7}"):
        sch.no_connect(U6.pin_xy(y))

    # OR register-select with the command strobes:
    #   write clocks rise at the end of the cycle (~IOW going high) -> latch
    #   read enables are active-low for the '244/'245 output buffers
    # 74HC32 value override (brief-specified): purely internal strobe combiners.
    U10 = sch.place("mini-xt:74HCT32", "U10", "74HC32", at=(203.2, 177.8))
    pwr(U10)
    L(U10, "P1", "~{SEL_DATA}", dx=-2.54); L(U10, "P2", "~{IOW}", dx=-2.54); L(U10, "P3", "WR_DATA")
    L(U10, "P4", "~{SEL_CTRL}", dx=-2.54); L(U10, "P5", "~{IOW}", dx=-2.54); L(U10, "P6", "WR_CTRL")
    L(U10, "P9", "~{SEL_DATA}", dx=-2.54); L(U10, "P10", "~{IOR}", dx=-2.54); L(U10, "P8", "~{RD_DATA}")
    L(U10, "P12", "~{SEL_STAT}", dx=-2.54); L(U10, "P13", "~{IOR}", dx=-2.54); L(U10, "P11", "~{RD_STAT}")

    # ============================================================
    # Data register  (0x378) -- 74HCT574 latch, always-enabled outputs
    # ('574 = '374 with flow-through pinout; the '374 is not stocked at JLC)
    # ============================================================
    # 74LVC574A value override (brief-specified): Q0-7 (PD0-7) tie directly
    # to DB25 pins 2-9 -- the connector boundary needs 5V-tolerant inputs.
    U1 = sch.place("mini-xt:74HCT574", "U1", "74LVC574A", at=(139.7, 76.2))
    pwr(U1)
    L(U1, "Cp", "WR_DATA", dx=-2.54)
    L(U1, "OE", "GND", dx=-2.54)
    for i in range(8):
        L(U1, "D%d" % i, "D%d" % i, dx=-2.54)         # bus -> latch
        L(U1, "Q%d" % i, "PD%d" % i)                  # latch -> DB25 data pin

    # data read-back: latched value driven onto the bus during a read of 0x378
    # 74LVC245A value override (brief-specified): A-side (PDx) shares the
    # same DB25-connected net as U1's Q-side.
    U4 = sch.place("mini-xt:74HCT245", "U4", "74LVC245A", at=(203.2, 76.2))
    pwr(U4)
    L(U4, "A->B", "+3V3", dx=-2.54)        # always A(latch)->B(bus) direction
    L(U4, "CE", "~{RD_DATA}", dx=-2.54)
    for i in range(8):
        L(U4, "A%d" % i, "PD%d" % i, dx=-2.54)
        L(U4, "B%d" % i, "D%d" % i)

    # ============================================================
    # Control register (0x37A) -- 74LVC574A latch + 74LVC244A read-back
    #   Q0 Strobe  Q1 AutoFeed  Q2 Init(direct)  Q3 SelectIn  Q4 IRQ-enable
    # ============================================================
    # 74LVC574A value override (brief-specified): Q2 (CTRL2/Init) ties
    # directly to DB25 pin 16 with no buffer in between.
    U2 = sch.place("mini-xt:74HCT574", "U2", "74LVC574A", at=(139.7, 127.0))
    pwr(U2)
    L(U2, "Cp", "WR_CTRL", dx=-2.54)
    L(U2, "OE", "GND", dx=-2.54)
    for i in range(5):
        L(U2, "D%d" % i, "D%d" % i, dx=-2.54)
    for i in range(5, 8):
        L(U2, "D%d" % i, "GND", dx=-2.54)             # unused control bits
    L(U2, "Q0", "CTRL0"); L(U2, "Q1", "CTRL1")
    L(U2, "Q2", "CTRL2")          # Init is non-inverted: latch -> DB25 pin 16 direct
    L(U2, "Q3", "CTRL3"); L(U2, "Q4", "IRQ_EN")
    for o in ("Q5", "Q6", "Q7"):
        sch.no_connect(U2.pin_xy(o))

    # 74LVC244A value override (spec 2026-07-14, not in the task-7 brief's
    # swap table -- added because 1A2 (CTRL2) is the SAME net as U2's Q2,
    # which ties directly to DB25 pin 16: this read-back buffer inherits the
    # connector exposure through that shared net, same reasoning as U3 below.
    U5 = sch.place("mini-xt:74HCT244", "U5", "74LVC244A", at=(203.2, 127.0))  # control read-back
    pwr(U5)
    L(U5, "1OE", "~{RD_CTRL}", dx=-2.54); L(U5, "2OE", "~{RD_CTRL}", dx=-2.54)
    cb = [("1A0", "1Y0", "CTRL0", "D0"), ("1A1", "1Y1", "CTRL1", "D1"),
          ("1A2", "1Y2", "CTRL2", "D2"), ("1A3", "1Y3", "CTRL3", "D3"),
          ("2A0", "2Y0", "IRQ_EN", "D4")]
    for a, y, src, d in cb:
        L(U5, a, src, dx=-2.54); L(U5, y, d)
    for a in ("2A1", "2A2", "2A3"):
        L(U5, a, "GND", dx=-2.54)
    for y in ("2Y1", "2Y2", "2Y3"):
        sch.no_connect(U5.pin_xy(y))

    # ============================================================
    # Status register (0x379) -- 74LVC244A buffers printer status onto the bus
    #   D7 ~Busy  D6 ~Ack  D5 PaperEnd  D4 Select  D3 ~Error  (D2..D0 = 0)
    # Bit 7 is INVERTED ON THE CARD (standard SPP semantics): BIOS INT 17h
    # spins on bit7=1 = "ready", so DB25 Busy passes through a U9 inverter.
    # 74LVC244A value override (brief-specified): P_ACK/P_PE/P_SEL/P_ERR are
    # raw DB25 inputs wired directly into this buffer -- the primary reason
    # the brief calls out LVC on this sheet's DB25-facing parts.
    # ============================================================
    U3 = sch.place("mini-xt:74HCT244", "U3", "74LVC244A", at=(203.2, 228.6))
    pwr(U3)
    L(U3, "1OE", "~{RD_STAT}", dx=-2.54); L(U3, "2OE", "~{RD_STAT}", dx=-2.54)
    sb = [("1A0", "1Y0", "BUSY_N", "D7"), ("1A1", "1Y1", "P_ACK", "D6"),
          ("1A2", "1Y2", "P_PE", "D5"), ("1A3", "1Y3", "P_SEL", "D4"),
          ("2A0", "2Y0", "P_ERR", "D3")]
    for a, y, src, d in sb:
        L(U3, a, src, dx=-2.54); L(U3, y, d)
    L(U3, "2A1", "GND", dx=-2.54); L(U3, "2Y1", "D2")
    L(U3, "2A2", "GND", dx=-2.54); L(U3, "2Y2", "D1")
    L(U3, "2A3", "GND", dx=-2.54); L(U3, "2Y3", "D0")

    # ============================================================
    # DB25 male -- standard SPP/Centronics LPT pinout
    # ============================================================
    J1 = sch.place("Connector:DB25_Pins", "J1", at=(355.6, 127.0))
    db = {
        "1": "P_STROBE",                                   # ~Strobe (out)
        "2": "PD0", "3": "PD1", "4": "PD2", "5": "PD3",
        "6": "PD4", "7": "PD5", "8": "PD6", "9": "PD7",    # D0..D7 (out)
        "10": "P_ACK",                                     # ~Ack  (in)
        "11": "P_BUSY",                                    # Busy  (in)
        "12": "P_PE",                                      # PaperEnd (in)
        "13": "P_SEL",                                     # Select (in)
        "14": "P_AUTOFD",                                  # ~AutoFeed (out)
        "15": "P_ERR",                                     # ~Error (in)
        "16": "CTRL2",                                     # ~Init (out, non-inverted)
        "17": "P_SLIN",                                    # ~SelectIn (out)
    }
    for num, net in db.items():
        L(J1, num, net, dx=-2.54)
    for num in range(18, 26):                              # pins 18-25 = signal GND
        L(J1, str(num), "GND", dx=-2.54)

    # ============================================================
    # Pull-ups on the printer status inputs
    # ============================================================
    # 4.7k pull-ups on the printer status inputs: with no printer attached these
    # float into the (now LVC/AHC-grade, 5V-tolerant-input) status buffers
    # (oscillation + phantom ~Ack IRQs). Real SPP cards shipped exactly this
    # network. Pulled to +3V3 (not +5V, spec 2026-07-14): 3.3V is a fully
    # valid logic-high for these inputs and there's no reason to overdrive
    # the idle level above the board's own rail.
    # (2026-07-14: one 4x4.7k basic array + one discrete replace 5 singles)
    mxbus.r_pack4(sch, "RN1", "4.7kx4", (314.96, 45.72),
                  [("P_ACK", "+3V3"), ("P_BUSY", "+3V3"),
                   ("P_PE", "+3V3"), ("P_SEL", "+3V3")])
    r = sch.place("Device:R", "R1", "4.7k", at=(340.36, 45.72))
    sch.net(r, "1", "+3V3", kind="label", dx=0, dy=-2.54)
    sch.net(r, "2", "P_ERR", kind="label", dx=0, dy=2.54)

    # Configuration note (all jumpers live on addr_decode now: JP1 = base
    # 0x378/0x278, JP5 = disable -- fitted jumper disables, default enabled)
    sch.text("Base hardwired 0x378; disable: addr_decode JP3; IRQ7 hardwired via its '125; U9.1 hosts the HLDA inverter",
             at=(299.72, 187.96), size=2.5)

    # ============================================================
    # decoupling
    # ============================================================
    for i, x in enumerate([30.48, 60.96, 91.44, 121.92, 152.4, 182.88, 213.36, 243.84, 274.32]):
        decouple("C%d" % (i + 1), (x, 264.16))

    cb = sch.place("Device:C", "C14", "10uF", at=(30.48, 238.76))
    sch.net(cb, "1", "+3V3", kind="label", dx=0, dy=-2.54)
    sch.net(cb, "2", "GND", kind="label", dx=0, dy=2.54)

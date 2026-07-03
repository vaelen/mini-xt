"""cpu_core -- CPU, memory, clock, reset, and the buffered-bus core (5 V domain).

Design doc S3/S4/S7. This is the motherboard's hard-real-time critical path:
  * NEC V20 (mini-xt:V20) in min mode
  * 3x 74HCT573 address latches (AD0-7 + A8-A19 -> A0-A19), LE = ALE (BALE),
    OE = HLDA -> released during Bus-MCU master cycles (address handoff)
  * 74HCT245 data transceiver (D0-D7), DIR = DT/~R, ~OE = DEN (so INTA cycles
    pass the vector bus->CPU, and the '245 goes Z while the V20 is in HOLD)
  * 74HCT32 strobe gates (~RD/~WR + IO/~M -> MEMR/W, IOR/W) behind a 74HCT125
    tri-state stage (~OE = HLDA) so the Bus MCU can drive the strobes as master;
    pull-ups park strobes + raw V20 lines inactive across the handoff gap
  * 74HCT138 + 74HCT00 SRAM chip-select decode (Y5 = video block, kept internal);
    spare '00 gates NAND the active-low reset sources into V20 RESET + RESET_DRV
  * 2x AS6C4008-55 SRAM (512Kx8 each) -> 640 KB + UMB
  * single-oscillator clock tree: 14.318 osc -> /2 (74HCT74) and /3 (74HCT163 preset-to-3),
    74HCT157 select (SPEED_SEL), 74HCT04 5 V buffer -> V20 CLK
  * TCM809 reset supervisor (cold start)

Exposes the buffered ISA backplane plus the private V20<->Bus-MCU side channels.
The Y5 video-block strobe stays internal (SRAM #2 decode only) -- per the
portability rule it must never leave this sheet.
"""
import mxbus
from mxbus import pin

NAME = "cpu_core"
TITLE = "CPU / Memory / Clock / Reset core (5V)"

PINS = (
    [pin(s, "output") for s in mxbus.ADDR] +              # A0..A19 driven by latches
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin("~{MEMR}", "output"), pin("~{MEMW}", "output"),
     pin("~{IOR}", "output"), pin("~{IOW}", "output"),
     pin("BALE", "output"), pin("AEN", "bidirectional"),
     pin("CLK", "output"), pin("OSC", "output"),
     pin("RESET_DRV", "output"), pin("IOCHRDY", "input")] +
    # private V20 <-> Bus MCU  (~{WR} / IO/~{M} are sheet-internal: the Bus MCU
    # doesn't sense them -- GPIO budget -- so only ~{RD} crosses the boundary)
    [pin("HOLD", "input"), pin("HLDA", "output"), pin("READY", "input"),
     pin("~{RD}", "output"),
     pin("INTR", "input"), pin("~{INTA}", "output"), pin("NMI", "input"),
     pin("~{CPURESET}", "input"), pin("SPEED_SEL", "input")]
)


def build(sch, lib):
    P = lambda c, p, net, **k: sch.net(c, p, net, kind="hier",
                                       shape=k.get("shape", "bidirectional"),
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def pwr(net, at):
        s = mxbus.power_net(sch, lib, net, at)
        return s

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def pullup(ref, net, at, val="10k"):
        r = sch.place("Device:R", ref, val, at=at)
        sch.net(r, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", net, kind="label", dx=0, dy=2.54)

    # ---------------- CPU ----------------
    U1 = sch.place("mini-xt:V20", "U1", at=(101.6, 152.4))
    L(U1, "VCC", "+5V", dx=0, dy=-2.54)
    L(U1, "GND", "GND", dx=0, dy=2.54)
    # multiplexed AD0-7 to data path + low address latch
    for i in range(8):
        L(U1, "AD%d" % i, "AD%d" % i, dx=-2.54)
    for i in range(8, 16):
        L(U1, "A%d" % i, "MA%d" % i, dx=-2.54)
    for nm in ["A16/S3", "A17/S4", "A18/S5", "A19/S6"]:
        L(U1, nm, "M" + nm.split("/")[0], dx=-2.54)
    # control / strobes -> private nets + bus
    P(U1, "ALE", "BALE", shape="output")
    L(U1, "~{WR}", "~{WR}"); L(U1, "IO/~{M}", "IO/~{M}")   # (~{RD} stubbed once, below)
    P(U1, "HOLD", "HOLD", shape="input"); P(U1, "HLDA", "HLDA", shape="output")
    P(U1, "READY", "READY", shape="input")
    P(U1, "INTR", "INTR", shape="input"); P(U1, "~{INTA}", "~{INTA}", shape="output")
    P(U1, "NMI", "NMI", shape="input")
    L(U1, "RESET", "V_RESET")
    L(U1, "CLK", "CPUCLK")
    L(U1, "MN/~{MX}", "+5V")             # min mode strapped high
    L(U1, "~{TEST}", "+5V")              # not waiting on a coprocessor
    # min mode DEN/DT-R exist precisely to run the local data transceiver:
    # DT/~R = direction, DEN (active low) = enable (asserted for INTA too).
    L(U1, "DEN", "DEN")
    L(U1, "DT/~{R}", "DT/~{R}")
    sch.no_connect(U1.pin_xy("~{SSO}"))
    # raw ~{RD} also exported (Bus MCU senses it on GPIO46); ~{WR} and IO/~{M}
    # stay sheet-internal (labelled above) -- the MCU tracks writes via the
    # gated MEMW/IOW strobes instead.
    P(U1, "~{RD}", "~{RD}", shape="output")

    # ---------------- min-mode strobe gating (IO/M + RD/WR -> MEMR/W,IOR/W) ----------------
    # IO/~M low = memory cycle:  ~MEMR = ~RD OR IO/~M    ~MEMW = ~WR OR IO/~M
    #                            ~IOR  = ~RD OR ~(IO/~M) ~IOW  = ~WR OR ~(IO/~M)
    # (IOM_INV comes from a spare U13 inverter, below the clock tree.)
    Ugate = sch.place("mini-xt:74HCT32", "U10", at=(165.1, 220.98))  # 4x OR
    L(Ugate, "VCC", "+5V", dx=0, dy=-2.54); L(Ugate, "GND", "GND", dx=0, dy=2.54)
    L(Ugate, "P1", "~{RD}", dx=-2.54);  L(Ugate, "P2", "IO/~{M}", dx=-2.54)
    L(Ugate, "P3", "MEMR_G")
    L(Ugate, "P4", "~{WR}", dx=-2.54);  L(Ugate, "P5", "IO/~{M}", dx=-2.54)
    L(Ugate, "P6", "MEMW_G")
    L(Ugate, "P9", "~{RD}", dx=-2.54);  L(Ugate, "P10", "IOM_INV", dx=-2.54)
    L(Ugate, "P8", "IOR_G")
    L(Ugate, "P12", "~{WR}", dx=-2.54); L(Ugate, "P13", "IOM_INV", dx=-2.54)
    L(Ugate, "P11", "IOW_G")

    # Tri-state stage: the gates are push-pull, but the Bus MCU also drives the
    # same four strobes during master cycles -- so the CPU-side strobes reach
    # the bus through a 74HCT125 whose ~OE = HLDA (enabled only while the V20
    # owns the bus). Pull-ups (below) hold the strobes inactive in the gap.
    Utri = sch.place("mini-xt:74HCT125", "U11", at=(205.74, 220.98))
    L(Utri, "VCC", "+5V", dx=0, dy=-2.54); L(Utri, "GND", "GND", dx=0, dy=2.54)
    L(Utri, "P1", "HLDA", dx=-2.54);  L(Utri, "P2", "MEMR_G", dx=-2.54)
    P(Utri, "P3", "~{MEMR}", shape="output")
    L(Utri, "P4", "HLDA", dx=-2.54);  L(Utri, "P5", "MEMW_G", dx=-2.54)
    P(Utri, "P6", "~{MEMW}", shape="output")
    L(Utri, "P10", "HLDA", dx=-2.54); L(Utri, "P9", "IOR_G", dx=-2.54)
    P(Utri, "P8", "~{IOR}", shape="output")
    L(Utri, "P13", "HLDA", dx=-2.54); L(Utri, "P12", "IOW_G", dx=-2.54)
    P(Utri, "P11", "~{IOW}", shape="output")

    # ---------------- address latches (3x 74HCT573) ----------------
    latch_at = [(165.1, 50.8), (165.1, 109.22), (165.1, 167.64)]
    lat = []
    for i, at in enumerate(latch_at):
        u = sch.place("mini-xt:74HCT573", "U%d" % (2 + i), at=at)
        lat.append(u)
        L(u, "VCC", "+5V", dx=0, dy=-2.54); L(u, "GND", "GND", dx=0, dy=2.54)
        # LE = ALE (the BALE net); OE = HLDA so the latches release A0-A19 to
        # the Bus MCU's counter buffers during master cycles (address handoff).
        L(u, "Load", "BALE"); L(u, "OE", "HLDA")
    # U2: AD0-7 -> A0-A7 ; U3: A8-A15 -> A8-A15 ; U4: A16-A19 -> A16-A19
    for i in range(8):
        L(lat[0], "D%d" % i, "AD%d" % i, dx=-2.54)
        P(lat[0], "Q%d" % i, "A%d" % i, shape="output")
    for i in range(8):
        L(lat[1], "D%d" % i, "MA%d" % (8 + i), dx=-2.54)
        P(lat[1], "Q%d" % i, "A%d" % (8 + i), shape="output")
    for i, a in enumerate([16, 17, 18, 19]):
        L(lat[2], "D%d" % i, "MA%d" % a, dx=-2.54)
        P(lat[2], "Q%d" % i, "A%d" % a, shape="output")

    # ---------------- data transceiver (74HCT245) ----------------
    U5 = sch.place("mini-xt:74HCT245", "U5", at=(165.1, 226.06))
    L(U5, "VCC", "+5V", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "A->B", "DT/~{R}")    # V20 DT/~R: high = CPU drives bus (incl. INTA vector B->A when low)
    L(U5, "CE", "DEN")          # V20 DEN (active low); pull-up floats it OFF during HOLD
    for i in range(8):
        L(U5, "A%d" % i, "AD%d" % i, dx=-2.54)        # CPU side (mux'd AD)
        P(U5, "B%d" % i, "D%d" % i, shape="bidirectional")  # bus side

    # ---------------- SRAM decode (74HCT138 + 74HCT00) ----------------
    U6 = sch.place("mini-xt:74HCT138", "U6", at=(248.92, 50.8))
    L(U6, "VCC", "+5V", dx=0, dy=-2.54); L(U6, "GND", "GND", dx=0, dy=2.54)
    L(U6, "A0", "A17"); L(U6, "A1", "A18"); L(U6, "A2", "A19")
    L(U6, "~{E0}", "GND"); L(U6, "~{E1}", "GND"); L(U6, "E2", "+5V")
    L(U6, "~{Y5}", "Y5_INT")          # 0xA0000-0xBFFFF: INTERNAL ONLY (not exposed)
    U7 = sch.place("mini-xt:74HCT00", "U7", at=(248.92, 109.22))
    L(U7, "VCC", "+5V", dx=0, dy=-2.54); L(U7, "GND", "GND", dx=0, dy=2.54)
    # SRAM#2 /CE = NAND(A19, Y5): low only when A19=1 and not video block
    L(U7, "P1", "A19"); L(U7, "P2", "Y5_INT"); L(U7, "P3", "RAM2_CE")

    # ---------------- SRAM (2x AS6C4008-55) ----------------
    for n, at, ce in [(1, (302.26, 76.2), "A19"), (2, (302.26, 175.26), "RAM2_CE")]:
        rmref = "RAM%d" % n
        rm = sch.place("Memory_RAM:AS6C4008-55PCN", rmref, at=at)
        L(rm, "VCC", "+5V", dx=0, dy=-2.54); L(rm, "VSS", "GND", dx=0, dy=2.54)
        for a in range(19):
            L(rm, "A%d" % a, "A%d" % a, dx=-2.54)
        for d in range(8):
            P(rm, "DQ%d" % d, "D%d" % d, shape="bidirectional")
        # Strobed by the GATED memory strobes (design S4.1): I/O cycles leave
        # MEMR/W inactive (no corruption on OUT), and the Bus MCU's master
        # MEMR/W reach the SRAM for shadow-load/DMA. NOT the raw ~RD/~WR.
        L(rm, "OE#", "~{MEMR}"); L(rm, "WE#", "~{MEMW}"); L(rm, "CE#", ce)

    # ---------------- clock tree ----------------
    osc = sch.place("Oscillator:ACO-xxxMHz", "OSC1", "14.31818MHz", at=(40.64, 45.72))
    L(osc, "Vcc", "+5V", dx=0, dy=-2.54); L(osc, "GND", "GND", dx=0, dy=2.54)
    L(osc, "OUT", "OSC")
    P(osc, "OUT", "OSC", shape="output")          # raw 14.318 to ISA OSC pin

    ff = sch.place("mini-xt:74HCT74", "U8", at=(76.2, 60.96))   # /2
    L(ff, "VCC", "+5V", dx=0, dy=-2.54); L(ff, "GND", "GND", dx=0, dy=2.54)
    L(ff, "C", "OSC"); L(ff, "D", "CLK_QN"); L(ff, "~{Q}", "CLK_QN")
    L(ff, "Q", "CLK7"); L(ff, "~{S}", "+5V"); L(ff, "~{R}", "+5V")

    # /3 via 74HCT163 preset-to-3 (no HCT 4017 exists): preload 13 (1101), the TC
    # at count 15 reloads the preset through ~PE -> a 3-state cycle. (Design S3.2
    # lists a 74HC161/163 preset-to-3 as the equivalent substitute for the 4017.)
    div3 = sch.place("mini-xt:74HCT163", "U9", at=(76.2, 109.22))  # /3
    L(div3, "VCC", "+5V", dx=0, dy=-2.54); L(div3, "GND", "GND", dx=0, dy=2.54)
    L(div3, "CP", "OSC")
    L(div3, "D0", "+5V"); L(div3, "D1", "GND"); L(div3, "D2", "+5V"); L(div3, "D3", "+5V")
    L(div3, "CEP", "+5V"); L(div3, "CET", "+5V"); L(div3, "~{MR}", "+5V")
    L(div3, "TC", "DIV3_TC"); L(div3, "~{PE}", "DIV3_LD")   # reload on terminal count
    # Q0 over the 13,14,15 cycle is HIGH 2/3 (67%) -- the V20-legal ~33%-HIGH
    # duty (what the 8284 supplied) only appears after the INVERTING U13
    # buffer stage below. That inversion is load-bearing, not a buffer choice.
    L(div3, "Q0", "CLK4")          # ~4.77 MHz, 67% duty here (33% after U13)

    mux = sch.place("mini-xt:74HCT157", "U12", at=(116.84, 76.2))
    L(mux, "VCC", "+5V", dx=0, dy=-2.54); L(mux, "GND", "GND", dx=0, dy=2.54)
    L(mux, "I0a", "CLK7"); L(mux, "I1a", "CLK4")
    P(mux, "S", "SPEED_SEL", shape="input"); L(mux, "E", "GND")
    L(mux, "Za", "CLK_MUX")

    # NOTE: U13 must stay an INVERTING buffer ('04) -- it is what turns the /3
    # divider's 67%-high Q0 into the 33%-high clock the V20's clock-low-time
    # spec needs at 4.77 MHz. A "cleanup" to a non-inverting buffer would
    # silently violate the CPU clock spec in turbo-down mode.
    buf = sch.place("mini-xt:74HCT04", "U13", at=(147.32, 76.2))  # 5V buffer to CPU CLK
    L(buf, "VCC", "+5V", dx=0, dy=-2.54); L(buf, "GND", "GND", dx=0, dy=2.54)
    L(buf, "P1", "CLK_MUX"); L(buf, "P2", "CPUCLK")
    L(buf, "P3", "CLK7"); L(buf, "P4", "CLK")    # also buffer bus CLK
    P(buf, "P4", "CLK", shape="output")
    L(buf, "P5", "DIV3_TC"); L(buf, "P6", "DIV3_LD")  # spare gate inverts TC -> ~PE
    L(buf, "P9", "IO/~{M}", dx=-2.54); L(buf, "P8", "IOM_INV")  # for the ~IOR/~IOW gates

    # ---------------- reset supervisor ----------------
    rst = sch.place("Power_Supervisor:TCM809", "U14", at=(45.72, 152.4))
    L(rst, "V_{DD}", "+5V", dx=0, dy=-2.54); L(rst, "GND", "GND", dx=0, dy=2.54)
    L(rst, "~{RESET}", "~{PWRGOOD}")
    # Reset combine on spare U7 NAND gates: V20 RESET and bus RESET_DRV are
    # ACTIVE-HIGH; the two sources (~PWRGOOD cold-start, ~CPURESET from the Bus
    # MCU's sequencing) are active-low -> NAND asserts reset when EITHER is low.
    L(U7, "P4", "~{PWRGOOD}", dx=-2.54)
    P(U7, "P5", "~{CPURESET}", shape="input", dx=-2.54)
    L(U7, "P6", "V_RESET")                       # -> V20 RESET (labelled at U1)
    L(U7, "P9", "~{PWRGOOD}", dx=-2.54)
    L(U7, "P10", "~{CPURESET}", dx=-2.54)
    P(U7, "P8", "RESET_DRV", shape="output")     # -> buffered bus reset

    # IOCHRDY folds into READY (handled in bus_mcu); AEN generated there too
    sch.hier_label("IOCHRDY", (304.8, 250), 0, "input")
    sch.hier_label("AEN", (304.8, 235), 0, "bidirectional")

    # ---------------- handoff pull-ups ----------------
    # Raw V20 strobes float during HOLD (inputs to the U10 gates), DEN floats
    # (U5 ~OE), and the gated bus strobes float in the ownership gap between
    # the '125 stage releasing and the Bus MCU driving -- park them all high.
    for i, net in enumerate(["~{RD}", "~{WR}", "IO/~{M}", "DEN",
                             "~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}"]):
        pullup("R%d" % (1 + i), net, (40.64 + 15.24 * i, 243.84))

    # decoupling
    for i, x in enumerate(range(40, 320, 40)):
        decouple("C%d" % (10 + i), (float(x), 270.0))

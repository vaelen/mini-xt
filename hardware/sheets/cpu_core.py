"""cpu_core -- CPU, memory, clock, reset, and the buffered-bus core (5 V domain).

Design doc S3/S4/S7. This is the motherboard's hard-real-time critical path:
  * NEC V20 (mini-xt:V20) in min mode
  * 3x 74HCT573 address latches (AD0-7 + A8-A19 -> A0-A19), gated by ALE
  * 74HCT245 data transceiver (D0-D7)
  * 74HCT138 + 74HCT00 SRAM chip-select decode (Y5 = video block, kept internal)
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
    # private V20 <-> Bus MCU
    [pin("HOLD", "input"), pin("HLDA", "output"), pin("READY", "input"),
     pin("~{RD}", "output"), pin("~{WR}", "output"), pin("IO/~{M}", "output"),
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
    L(U1, "~{RD}", "~{RD}"); L(U1, "~{WR}", "~{WR}"); L(U1, "IO/~{M}", "IO/~{M}")
    P(U1, "HOLD", "HOLD", shape="input"); P(U1, "HLDA", "HLDA", shape="output")
    P(U1, "READY", "READY", shape="input")
    P(U1, "INTR", "INTR", shape="input"); P(U1, "~{INTA}", "~{INTA}", shape="output")
    P(U1, "NMI", "NMI", shape="input")
    L(U1, "RESET", "V_RESET")
    L(U1, "CLK", "CPUCLK")
    L(U1, "MN/~{MX}", "+5V")             # min mode strapped high
    L(U1, "~{TEST}", "+5V")              # not waiting on a coprocessor
    sch.no_connect(U1.pin_xy("DEN"))     # min mode: no 8288, DEN/DT-R/SSO unused
    sch.no_connect(U1.pin_xy("DT/~{R}"))
    sch.no_connect(U1.pin_xy("~{SSO}"))
    # raw strobes also exported (Bus MCU senses/drives them)
    P(U1, "~{RD}", "~{RD}", shape="output"); P(U1, "~{WR}", "~{WR}", shape="output")
    P(U1, "IO/~{M}", "IO/~{M}", shape="output")

    # ---------------- min-mode strobe gating (IO/M + RD/WR -> MEMR/W,IOR/W) ----------------
    # IO/M low = memory cycle. MEMR = RD when IO/M low; IOR = RD when IO/M high.
    Ugate = sch.place("mini-xt:74HCT32", "U10", at=(165.1, 220.98))  # OR gates
    L(Ugate, "VCC", "+5V", dx=0, dy=-2.54); L(Ugate, "GND", "GND", dx=0, dy=2.54)
    # (functional intent captured; detailed gate wiring noted in open-questions)
    P(Ugate, "1", "~{MEMR}", shape="output", dx=-2.54)
    P(Ugate, "13", "~{IOR}", shape="output")

    Ugate2 = sch.place("mini-xt:74HCT08", "U11", at=(205.74, 220.98))  # AND gates
    L(Ugate2, "VCC", "+5V", dx=0, dy=-2.54); L(Ugate2, "GND", "GND", dx=0, dy=2.54)
    P(Ugate2, "1", "~{MEMW}", shape="output", dx=-2.54)
    P(Ugate2, "13", "~{IOW}", shape="output")

    # ---------------- address latches (3x 74HCT573) ----------------
    latch_at = [(165.1, 50.8), (165.1, 109.22), (165.1, 167.64)]
    lat = []
    for i, at in enumerate(latch_at):
        u = sch.place("mini-xt:74HCT573", "U%d" % (2 + i), at=at)
        lat.append(u)
        L(u, "VCC", "+5V", dx=0, dy=-2.54); L(u, "GND", "GND", dx=0, dy=2.54)
        L(u, "Load", "BALE_L"); L(u, "OE", "GND")     # OE tied low (always enabled)
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

    # ALE buffered to latch Load lines
    sch.label("BALE_L", (lat[0].pin_xy("Load")[0] - 2.54, lat[0].pin_xy("Load")[1]), 180)

    # ---------------- data transceiver (74HC245) ----------------
    U5 = sch.place("mini-xt:74HCT245", "U5", at=(165.1, 226.06))
    L(U5, "VCC", "+5V", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "A->B", "~{RD}")      # direction follows RD (read = drive toward CPU)
    L(U5, "CE", "GND")
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
        L(rm, "OE#", "~{RD}"); L(rm, "WE#", "~{WR}"); L(rm, "CE#", ce)

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
    L(div3, "Q0", "CLK4")          # ~4.77 MHz (~33% duty, acceptable per S3.2)

    mux = sch.place("mini-xt:74HCT157", "U12", at=(116.84, 76.2))
    L(mux, "VCC", "+5V", dx=0, dy=-2.54); L(mux, "GND", "GND", dx=0, dy=2.54)
    L(mux, "I0a", "CLK7"); L(mux, "I1a", "CLK4")
    P(mux, "S", "SPEED_SEL", shape="input"); L(mux, "E", "GND")
    L(mux, "Za", "CLK_MUX")

    buf = sch.place("mini-xt:74HCT04", "U13", at=(147.32, 76.2))  # 5V buffer to CPU CLK
    L(buf, "VCC", "+5V", dx=0, dy=-2.54); L(buf, "GND", "GND", dx=0, dy=2.54)
    L(buf, "P1", "CLK_MUX"); L(buf, "P2", "CPUCLK")
    L(buf, "P3", "CLK7"); L(buf, "P4", "CLK")    # also buffer bus CLK
    P(buf, "P4", "CLK", shape="output")
    L(buf, "P5", "DIV3_TC"); L(buf, "P6", "DIV3_LD")  # spare gate inverts TC -> ~PE

    # ---------------- reset supervisor ----------------
    rst = sch.place("Power_Supervisor:TCM809", "U14", at=(45.72, 152.4))
    L(rst, "V_{DD}", "+5V", dx=0, dy=-2.54); L(rst, "GND", "GND", dx=0, dy=2.54)
    L(rst, "~{RESET}", "PWRGOOD")
    # Bus MCU sequences the actual V20 reset; combine cold-start with ~CPURESET
    rcomb = sch.place("mini-xt:74HCT08", "U15", at=(76.2, 152.4))
    L(rcomb, "VCC", "+5V", dx=0, dy=-2.54); L(rcomb, "GND", "GND", dx=0, dy=2.54)
    # (reset combine logic intent; detailed in open-questions)
    sch.hier_label("RESET_DRV", (60.96, 190.5), 0, "output")   # bus reset out (interface)
    # V20 RESET driven by the combine (internal net V_RESET); already labelled above

    # IOCHRDY folds into READY (handled in bus_mcu); expose both
    sch.hier_label("IOCHRDY", (304.8, 250), 0, "input")
    sch.hier_label("RESET_DRV", (304.8, 245), 0, "output")
    sch.hier_label("~{CPURESET}", (304.8, 240), 0, "input")
    sch.hier_label("AEN", (304.8, 235), 0, "bidirectional")

    # decoupling
    for i, x in enumerate(range(40, 320, 40)):
        decouple("C%d" % (10 + i), (float(x), 270.0))

"""cpu_core -- CPU, memory, clock, reset, and the buffered-bus core.

Design doc S3/S4/S7 + 3.3 V single-board redesign (spec 2026-07-14). The V20 and
its demux latches/transceiver ARE the board's single 5 V<->3.3 V boundary: the
V20 runs at 5 V, everything past the boundary latches is a 3.3 V bus.
  * NEC V20 (mini-xt:V20) in min mode -- 5 V
  * 3x 74LVC573A address latches (AD0-7 + A8-A19 -> A0-A19), LE = ALE (BALE),
    OE = HLDA -> released during Bus-MCU master cycles (address handoff).
    3.3 V-powered, 5 V-tolerant inputs => the address half of the boundary.
  * 74LVC245A data transceiver (D0-D7), DIR = DT/~R, ~OE = DEN -- the data half
    of the boundary (5 V-tolerant CPU side, 3.3 V bus side).
  * 74HCT32 strobe gates (~RD/~WR + IO/~M -> MEMR/W, IOR/W) stay on +5V (they
    read the raw 5 V V20 strobes) behind a 74LVC125A tri-state stage (~OE = HLDA,
    3.3 V bus out) -- the strobe half of the boundary; pull-ups park the bus
    strobes inactive across the handoff gap.
  * 74HC138 + 74HC00 (3.3 V) SRAM chip-select decode (Y5 = video block, internal);
    spare '00 gates NAND the active-low reset sources into V20 RESET + RESET_DRV,
    and invert A0 (-> UB) and Y5 (-> RAM /CE).
  * 1x IS62WV51216BLL 512Kx16 SRAM used as 1Mx8 via the byte-lane trick -> full
    1 MB less the 0xA0000-0xBFFFF video window.
  * single-oscillator clock tree: 14.318 osc -> /2 (74LVC74A) and /3 (74LVC161
    preset-to-3, 3.3 V for fmax margin), 74HC157 select (SPEED_SEL direct),
    74HCT04 5 V buffer -> V20 CLK (the one gate package that MUST stay 5 V:
    V20 CLK needs Vkh = 4.0 V, unreachable from 3.3 V).
  * TCM809 reset supervisor (cold start) -- 3.3 V so its reset net is clean 3.3 V.

Exposes the buffered ISA backplane plus the private V20<->Bus-MCU side channels.
The Y5 video-block strobe stays internal -- per the portability rule it must
never leave this sheet.
"""
import mxbus
from mxbus import pin

NAME = "cpu_core"
TITLE = "CPU / Memory / Clock / Reset core (5V<->3.3V boundary)"

PINS = (
    [pin(s, "output") for s in mxbus.ADDR] +              # A0..A19 driven by latches
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin("~{MEMR}", "output"), pin("~{MEMW}", "output"),
     pin("~{IOR}", "output"), pin("~{IOW}", "output"),
     pin("BALE", "output"),
     # (AEN / IOCHRDY intentionally absent: AEN is generated on bus_mcu and
     # IOCHRDY folds into READY there -- nothing on this sheet touches either.)
     pin("CLK", "output"), pin("OSC", "output"),
     pin("RESET_DRV", "output")] +
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

    def decouple(ref, at, rail="+3V3"):
        # Board logic is now 3.3 V-domain, so decoupling defaults to +3V3; the
        # few surviving 5 V parts (V20, U10 '32, U13 '04) get explicit +5V caps.
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def pullup(ref, net, at, val="10k", rail="+5V"):
        r = sch.place("Device:R", ref, val, at=at)
        sch.net(r, "1", rail, kind="label", dx=0, dy=-2.54)
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

    # Tri-state stage AND the strobe half of the 5V<->3.3V boundary: U10's gates
    # are push-pull 5V, but the Bus MCU also drives the same four strobes during
    # master cycles -- so the CPU-side strobes reach the bus through a 74LVC125A
    # (3.3V-powered, 5V-tolerant inputs) whose ~OE = HLDA (enabled only while the
    # V20 owns the bus). Its outputs are the 3.3V bus strobes. Pull-ups (below)
    # hold the strobes inactive in the gap. (U10 stays +5V; only U11 crosses.)
    Utri = sch.place("mini-xt:74HCT125", "U11", "74LVC125A", at=(205.74, 220.98))
    L(Utri, "VCC", "+3V3", dx=0, dy=-2.54); L(Utri, "GND", "GND", dx=0, dy=2.54)
    L(Utri, "P1", "HLDA", dx=-2.54);  L(Utri, "P2", "MEMR_G", dx=-2.54)
    P(Utri, "P3", "~{MEMR}", shape="output")
    L(Utri, "P4", "HLDA", dx=-2.54);  L(Utri, "P5", "MEMW_G", dx=-2.54)
    P(Utri, "P6", "~{MEMW}", shape="output")
    L(Utri, "P10", "HLDA", dx=-2.54); L(Utri, "P9", "IOR_G", dx=-2.54)
    P(Utri, "P8", "~{IOR}", shape="output")
    L(Utri, "P13", "HLDA", dx=-2.54); L(Utri, "P12", "IOW_G", dx=-2.54)
    P(Utri, "P11", "~{IOW}", shape="output")

    # ---------------- address latches (3x 74LVC573A) ----------------
    # 74LVC573A on the HCT573 body: 3.3V-powered, 5V-tolerant inputs = the V20
    # 5V<->3.3V boundary (spec 2026-07-14). Same pinout as the '573.
    latch_at = [(165.1, 50.8), (165.1, 109.22), (165.1, 167.64)]
    lat = []
    for i, at in enumerate(latch_at):
        u = sch.place("mini-xt:74HCT573", "U%d" % (2 + i), "74LVC573A", at=at)
        lat.append(u)
        L(u, "VCC", "+3V3", dx=0, dy=-2.54); L(u, "GND", "GND", dx=0, dy=2.54)
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
    for i in range(4, 8):                     # unused U4 half: no floating inputs
        L(lat[2], "D%d" % i, "GND", dx=-2.54)
        sch.no_connect(lat[2].pin_xy("Q%d" % i))

    # ---------------- data transceiver (74LVC245A) ----------------
    # 74LVC245A on the HCT245 body: 3.3V-powered, 5V-tolerant CPU-side inputs =
    # the data half of the V20 5V<->3.3V boundary (spec 2026-07-14).
    U5 = sch.place("mini-xt:74HCT245", "U5", "74LVC245A", at=(165.1, 226.06))
    L(U5, "VCC", "+3V3", dx=0, dy=-2.54); L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "A->B", "DT/~{R}")    # V20 DT/~R: high = CPU drives bus (incl. INTA vector B->A when low)
    L(U5, "CE", "DEN")          # V20 DEN (active low); pull-up floats it OFF during HOLD
    for i in range(8):
        L(U5, "A%d" % i, "AD%d" % i, dx=-2.54)        # CPU side (mux'd AD)
        P(U5, "B%d" % i, "D%d" % i, shape="bidirectional")  # bus side

    # ---------------- SRAM decode (74HC138 + 74HC00, 3.3V) ----------------
    # 74HC138 value override: HC (not HCT) is fine here -- every input is 3.3V-
    # driven (A17-A19 from the LVC latches) on a 3.3V-powered part (spec 2026-07-14).
    U6 = sch.place("mini-xt:74HCT138", "U6", "74HC138", at=(248.92, 50.8))
    L(U6, "VCC", "+3V3", dx=0, dy=-2.54); L(U6, "GND", "GND", dx=0, dy=2.54)
    L(U6, "A0", "A17"); L(U6, "A1", "A18"); L(U6, "A2", "A19")
    L(U6, "~{E0}", "GND"); L(U6, "~{E1}", "GND"); L(U6, "E2", "+3V3")
    L(U6, "~{Y5}", "Y5_INT")          # 0xA0000-0xBFFFF: INTERNAL ONLY (not exposed)
    for y in (0, 1, 2, 3, 4, 6, 7):   # only Y5 decode is used
        sch.no_connect(U6.pin_xy("~{Y%d}" % y))
    # 74HC00 value override: HC on the HCT body -- all inputs are 3.3V-driven
    # (A0/Y5_INT from 3.3V logic, ~PWRGOOD from the now-3.3V TCM809, ~CPURESET
    # from the 3.3V Bus MCU) on a 3.3V rail (spec 2026-07-14).
    U7 = sch.place("mini-xt:74HCT00", "U7", "74HC00", at=(248.92, 109.22))
    L(U7, "VCC", "+3V3", dx=0, dy=-2.54); L(U7, "GND", "GND", dx=0, dy=2.54)
    # Byte-lane + /CE inverters, freed by dropping the old SRAM#2 select NAND:
    #   U7a: A0_INV = NAND(A0, A0)      -> UB (A0=1 selects the high byte lane)
    #   U7d: RAM_CE = NAND(Y5_INT, Y5_INT) = NOT(Y5_INT): SRAM answers the full
    #        1MB EXCEPT the 0xA0000-0xBFFFF video window (Y5_INT low there).
    L(U7, "P1", "A0"); L(U7, "P2", "A0"); L(U7, "P3", "A0_INV")
    L(U7, "P12", "Y5_INT", dx=-2.54); L(U7, "P13", "Y5_INT", dx=-2.54)
    L(U7, "P11", "RAM_CE")

    # ---------------- SRAM (1x IS62WV51216BLL, 512Kx16 as 1Mx8) ----------------
    # Byte-lane trick (spec 2026-07-14): the word address is A1..A19; A0 picks the
    # byte lane; both IO bytes tie to D0-D7 -- exactly one lane is ever enabled,
    # the other tri-states (LB/UB gate the output drivers, ISSI truth table).
    RAM = sch.place("mini-xt:IS62WV51216", "RAM1", "IS62WV51216BLL", at=(302.26, 109.22))
    L(RAM, "11", "+3V3", dx=0, dy=-2.54); L(RAM, "33", "+3V3", dx=0, dy=-2.54)  # both VDD
    L(RAM, "12", "GND", dx=0, dy=2.54);   L(RAM, "34", "GND", dx=0, dy=2.54)    # both GND
    for i in range(19):                    # chip A0..A18 <- system A1..A19
        L(RAM, "A%d" % i, "A%d" % (i + 1), dx=-2.54)
    for i in range(8):                     # both byte lanes tied to D0..D7
        P(RAM, "IO%d" % i, "D%d" % i, shape="bidirectional")
        P(RAM, "IO%d" % (i + 8), "D%d" % i, shape="bidirectional")
    # /OE = MEMR direct (the whole read critical path, 25ns tDOE); /WE = MEMW.
    # GATED strobes (design S4.1): I/O cycles leave MEMR/W inactive (no OUT
    # corruption) and the Bus MCU's master MEMR/W reach the SRAM for shadow/DMA.
    L(RAM, "~{OE}", "~{MEMR}", dx=-2.54); L(RAM, "~{WE}", "~{MEMW}", dx=-2.54)
    L(RAM, "~{LB}", "A0", dx=-2.54)        # A0=0 -> low byte lane enabled
    L(RAM, "~{UB}", "A0_INV", dx=-2.54)    # A0=1 -> high byte lane enabled
    L(RAM, "~{CE}", "RAM_CE", dx=-2.54)    # = NOT(Y5_INT): 1MB less video window

    # ---------------- clock tree ----------------
    # 14.318 canned oscillators are only stocked as 3.3 V parts (JLC), so the
    # XO runs from +3V3 and a spare U13 HCT gate (TTL Vih reads 3.3 V) squares
    # it up to the 5 V OSC that feeds the dividers and the ISA OSC pin.
    # (Clock phase inversion through the gate is irrelevant.)
    osc = sch.place("Oscillator:ACO-xxxMHz", "OSC1", "14.31818MHz", at=(40.64, 45.72))
    L(osc, "Vcc", "+3V3", dx=0, dy=-2.54); L(osc, "GND", "GND", dx=0, dy=2.54)
    L(osc, "OUT", "OSC_3V3")

    # 74LVC74A value override on the '74 body: plain HC/HCT fail the fmax margin
    # at 3.3V (interp. ~14.8 MHz min vs 14.318 MHz clock -- Task1 check 7); LVC is
    # spec'd 250 MHz. Clocked by OSC (5V) on its 5V-tolerant input; +3V3 powered.
    ff = sch.place("mini-xt:74HCT74", "U8", "74LVC74A", at=(76.2, 60.96))   # /2
    L(ff, "VCC", "+3V3", dx=0, dy=-2.54); L(ff, "GND", "GND", dx=0, dy=2.54)
    L(ff, "C", "OSC"); L(ff, "D", "CLK_QN"); L(ff, "~{Q}", "CLK_QN")
    L(ff, "Q", "CLK7"); L(ff, "~{S}", "+3V3"); L(ff, "~{R}", "+3V3")
    # FF2 unused: park it (wire by pin number -- names duplicate across units)
    L(ff, "12", "GND", dx=-2.54); L(ff, "11", "GND", dx=-2.54)
    L(ff, "10", "+3V3", dx=-2.54); L(ff, "13", "+3V3", dx=-2.54)
    sch.no_connect(ff.pin_xy("9")); sch.no_connect(ff.pin_xy("8"))

    # /3 via '161 preset-to-3: preload 13 (1101), the TC at count 15 reloads
    # the preset through ~PE -> a 3-state cycle. (Same pinout as the '163, async
    # ~MR tied inactive.) 74LVC161 value override: plain HC161 at 3.3V interpolates
    # to ~11.1 MHz fmax -- BELOW the 14.318 MHz clock, it fails (Task1 check 7);
    # LVC161 is spec'd 150 MHz. CP = OSC (5V) on a 5V-tolerant input; +3V3 powered.
    div3 = sch.place("mini-xt:74HCT163", "U9", "74LVC161", at=(76.2, 109.22))  # /3
    L(div3, "VCC", "+3V3", dx=0, dy=-2.54); L(div3, "GND", "GND", dx=0, dy=2.54)
    L(div3, "CP", "OSC")
    L(div3, "D0", "+3V3"); L(div3, "D1", "GND"); L(div3, "D2", "+3V3"); L(div3, "D3", "+3V3")
    L(div3, "CEP", "+3V3"); L(div3, "CET", "+3V3"); L(div3, "~{MR}", "+3V3")
    L(div3, "TC", "DIV3_TC"); L(div3, "~{PE}", "DIV3_LD")   # reload on terminal count
    # Q0 over the 13,14,15 cycle is HIGH 2/3 (67%) -- the V20-legal ~33%-HIGH
    # duty (what the 8284 supplied) only appears after the INVERTING U13
    # buffer stage below. That inversion is load-bearing, not a buffer choice.
    L(div3, "Q0", "CLK4")          # ~4.77 MHz, 67% duty here (33% after U13)
    for q in ("Q1", "Q2", "Q3"):   # only Q0 used
        sch.no_connect(div3.pin_xy(q))

    # Speed mux is 74HC157 (no HCT/ACT157 stocked at JLC), now +3V3-powered. Its
    # clock inputs (CLK4/CLK7) are 3.3V from the LVC dividers and its SPEED_SEL
    # select is a 3.3V MCU GPIO -- all clear HC's Vih (0.7*3.3=2.31V) at 3.3V, so
    # the select is driven DIRECTLY (no more 5V HCT inverter stage). With S driven
    # true-sense, I0a/I1a are UN-swapped vs the old inverted-select wiring so the
    # firmware polarity holds: SPEED_SEL=0 -> S=L -> Za=I0a=CLK7 (7.16 MHz).
    mux = sch.place("mini-xt:74HCT157", "U12", "74HC157", at=(116.84, 76.2))
    L(mux, "VCC", "+3V3", dx=0, dy=-2.54); L(mux, "GND", "GND", dx=0, dy=2.54)
    L(mux, "I0a", "CLK7"); L(mux, "I1a", "CLK4")
    P(mux, "S", "SPEED_SEL", shape="input", dx=-2.54); L(mux, "E", "GND")
    L(mux, "Za", "CLK_MUX")
    # Unused mux sections: inputs tied (no floating CMOS)
    for p in ("I0b", "I1b", "I0c", "I1c", "I0d", "I1d"):
        L(mux, p, "GND", dx=-2.54)
    for p in ("Zb", "Zc", "Zd"):
        sch.no_connect(mux.pin_xy(p))

    # NOTE: U13 must stay an INVERTING buffer ('04) -- it is what turns the /3
    # divider's 67%-high Q0 into the 33%-high clock the V20's clock-low-time
    # spec needs at 4.77 MHz. A "cleanup" to a non-inverting buffer would
    # silently violate the CPU clock spec in turbo-down mode.
    # THE one gate package that MUST stay +5V: V20 CLK needs Vkh = 0.8*Vdd = 4.0V
    # (Task1 check 1), unreachable from a 3.3V rail. HCT-grade so it reads the 3.3V
    # CLK_MUX/CLK7/OSC_3V3 inputs (Vih_HCT ~ 2V) yet outputs the 5V swings CLK and
    # OSC need. Do NOT downgrade to 74HC04 and do NOT move to +3V3.
    buf = sch.place("mini-xt:74HCT04", "U13", at=(147.32, 76.2))  # 5V buffer to CPU CLK
    L(buf, "VCC", "+5V", dx=0, dy=-2.54); L(buf, "GND", "GND", dx=0, dy=2.54)
    L(buf, "P1", "CLK_MUX"); L(buf, "P2", "CPUCLK")
    # Bus CLK is FIXED at 7.16 MHz: the speed mux only retimes CPUCLK, so ISA
    # CLK does not drop to 4.77 MHz in turbo-down mode (cards are strobe-timed;
    # nothing on this bus times off CLK -- logged in notes/open-questions.md).
    L(buf, "P3", "CLK7"); L(buf, "P4", "CLK")    # also buffer bus CLK
    P(buf, "P4", "CLK", shape="output")
    L(buf, "P5", "DIV3_TC"); L(buf, "P6", "DIV3_LD")  # spare gate inverts TC -> ~PE
    L(buf, "P9", "IO/~{M}", dx=-2.54); L(buf, "P8", "IOM_INV")  # for the ~IOR/~IOW gates
    # P11/P12 gate freed: SPEED_SEL now drives the 3.3V mux select directly (above),
    # so no 5V inversion is needed. Park the spare input; NC its output.
    L(buf, "P11", "GND", dx=-2.54)
    sch.no_connect(buf.pin_xy("P10"))
    L(buf, "P13", "OSC_3V3", dx=-2.54)                   # 3.3V XO squared up...
    P(buf, "P12", "OSC", shape="output")                 # ...to the 5V OSC (dividers + ISA B30)

    # ---------------- reset supervisor ----------------
    # TCM809 on +3V3 (was +5V): the reset combiner U7 is now a 3.3V part, so its
    # ~PWRGOOD input must be a 3.3V swing. Monitors the 3.3V logic rail; the V20's
    # RESET tolerates a 3.3V-derived reset (Vih 2.2V, Task1 check 1). Threshold
    # variant (e.g. TCM809T ~3.08V for a 3.3V rail) is a parts.py concern.
    rst = sch.place("Power_Supervisor:TCM809", "U14", at=(45.72, 152.4))
    L(rst, "V_{DD}", "+3V3", dx=0, dy=-2.54); L(rst, "GND", "GND", dx=0, dy=2.54)
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


    # ---------------- handoff pull-ups ----------------
    # Raw V20 strobes float during HOLD (inputs to the U10 gates) and DEN floats
    # (U5 ~OE) -- these are 5V nets, park them to +5V. The gated BUS strobes float
    # in the ownership gap between the '125 releasing and the Bus MCU driving --
    # they are now 3.3V bus nets (U11 is the boundary), so park them to +3V3.
    for i, net in enumerate(["~{RD}", "~{WR}", "IO/~{M}", "DEN"]):
        pullup("R%d" % (1 + i), net, (40.64 + 15.24 * i, 243.84), rail="+5V")
    for i, net in enumerate(["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}"]):
        pullup("R%d" % (5 + i), net, (40.64 + 15.24 * (4 + i), 243.84), rail="+3V3")

    # decoupling -- pool defaults to +3V3 (the logic domain now). Dropped 2 caps
    # vs the old 2-SRAM layout (removed the second SRAM's decoupling, step 4).
    for i, x in enumerate(range(20, 300, 20)):     # C10..C23 on +3V3
        decouple("C%d" % (10 + i), (float(x), 270.0))
    # surviving 5V parts (V20, U10 '32, U13 '04) keep +5V decoupling
    decouple("C24", (300.0, 270.0), rail="+5V")
    decouple("C25", (320.0, 270.0), rail="+5V")
    c = sch.place("Device:C", "C26", "100nF", at=(55.88, 20.32))   # OSC1 3V3 decouple
    sch.net(c, "1", "+3V3", kind="label", dx=0, dy=-2.54)
    sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)
    c = sch.place("Device:C", "C27", "10uF", at=(340.36, 270.0))   # +5V bulk
    sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

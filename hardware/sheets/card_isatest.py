"""card_isatest -- standalone ISA card tester: a stock Raspberry Pi Pico acts as
the ISA host / bus master to exercise a device-under-test (DUT) card over USB
serial. See docs/superpowers/specs/2026-07-01-isa-test-card-design.md.

Post-3.3V-redesign target: the motherboard's internal bus is 3.3V end to end,
so this jig -- like card_video -- is a genuine 5V ISA card/host, exercising
DUTs over its own ISA slot + sidecar header or the motherboard's buffered
expansion port, and it keeps its own local level shifters (below) rather than
relying on any motherboard-side buffering.

The Pico drives the full 8-bit ISA bus through 74LVC245A 3.3<->5V transceivers:
  * data D0-7   : direct Pico GPIO (MD0-7), dir = DATADIR
  * address A0-19: 74HC595 OUT chain (split address / control latches)
  * control out : strobes direct + AEN/RESET_DRV/TC/DACK/BALE on the OUT chain
  * status in   : IRQ/DRQ/IOCHCK# on a 74HC165 IN chain; IOCHRDY/CLK sensed direct
A 14.318 MHz can-oscillator clock tree (/2, /3, PIO override) makes CLK/OSC.
Standalone board: bus + power arrive via its own ISA slot + sidecar header, so
there is no parent interface (PINS = []), like the other card_* PCBs.
"""
import isa_conn
import mxbus  # noqa: F401  (canonical names spelled out below)

NAME = "card_isatest"
TITLE = "ISA Card Tester -- Pico host/bus-master"
PAPER = "A2"               # room for the Pico + 8x '245 + shift chains + slot
PINS = []                  # standalone PCB: bus + power come through the connectors

# Pico GPIO -> internal net (MCU side). 24 of 26 used; GP27/GP28 spare.
GPIO_NET = {
    0: "MD0", 1: "MD1", 2: "MD2", 3: "MD3", 4: "MD4", 5: "MD5", 6: "MD6", 7: "MD7",
    8: "DATADIR",
    9: "M_MEMR", 10: "M_MEMW", 11: "M_IOR", 12: "M_IOW",
    13: "IOCHRDY_S", 14: "M_REFRESH",
    15: "SER", 16: "SRCLK", 17: "RCLK_ADDR", 18: "RCLK_CTRL",
    19: "IN_PL", 20: "IN_QH", 21: "~{BUF_EN}", 22: "PIO_CLK",
    26: "CLK_S",
}


def build(sch, lib):
    # ---- shared helpers -------------------------------------------------
    def N(comp, key, name, dx=2.54, dy=0.0):
        return sch.net(comp, key, name, dx=dx, dy=dy, kind="label")

    def decouple(ref, at, hi="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", hi, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def xcvr(ref, at, dir_net, vcc="+3V3"):
        """74LVC245A buffer. dir_net -> A->B pin; CE(~OE) -> ~{BUF_EN}."""
        u = sch.place("mini-xt:74LVC245A", ref, "74LVC245A", at=at)
        N(u, "VCC", vcc, dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "A->B", dir_net)
        N(u, "CE", "~{BUF_EN}")
        return u

    def s595(ref, at, rclk):
        """74HC595 SIPO @3V3. SRCLK shared; per-segment RCLK; OE tied on."""
        u = sch.place("74xx:74HC595", ref, "74HC595", at=at)
        N(u, "VCC", "+3V3", dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "SRCLK", "SRCLK")
        N(u, "RCLK", rclk)
        N(u, "~{OE}", "GND")        # internal side always driven; bus gated by '245
        N(u, "~{SRCLR}", "+3V3")
        return u

    def s165(ref, at):
        """'165 PISO @3V3 -- must be the 74HC grade: HCT is only specified for
        VCC 4.5-5.5 V (this is a supply-range limit, not a threshold choice).
        The mini-xt:74HCT165 symbol body is reused with a value override."""
        u = sch.place("mini-xt:74HCT165", ref, "74HC165", at=at)
        N(u, "VCC", "+3V3", dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "CP", "SRCLK")
        N(u, "~{PL}", "IN_PL")
        N(u, "~{CE}", "GND")
        return u

    def pull(ref, at, net, rail):
        r = sch.place("Device:R", ref, "10k", at=at)
        sch.net(r, "1", net, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", rail, kind="label", dx=0, dy=2.54)

    # ---- M1: Raspberry Pi Pico module -----------------------------------
    M1 = sch.place("mini-xt:Pico", "M1", "Pico (RP2040)", at=(101.6, 152.4))
    # Power: VBUS = USB 5V; VSYS from the board 5V rail (jack or USB); 3V3 OUT
    # powers all the 3V3 logic on this card. (Power block wired in Task 7.)
    N(M1, "VBUS", "+5V_USB", dx=0, dy=-2.54)
    N(M1, "VSYS", "V5RAW", dx=0, dy=-2.54)
    N(M1, "3V3", "+3V3", dx=0, dy=-2.54)
    N(M1, "GND", "GND", dx=0, dy=2.54)
    for nm in ("3V3_EN", "RUN", "ADC_VREF"):
        sch.no_connect(M1.pin_xy(nm))
    for idx, net in GPIO_NET.items():
        N(M1, "GP%d" % idx, net)
    for idx in (27, 28):
        sch.no_connect(M1.pin_xy("GP%d" % idx))   # spare GPIO
    sch.text("Pico host/bus-master: USB serial console; drives full 8-bit ISA bus "
             "via 74LVC245A buffers. 24/26 GPIO used.", (38.1, 96.52))

    # ==== BLOCKS BELOW ADDED BY LATER TASKS (keep this marker) ============
    # [transceivers] [out-chain] [in-chain] [clock] [power] [connectors]

    # ---- bus transceivers: 8x 74LVC245A (3V3<->5V), OE = ~{BUF_EN} -------
    # Data (bidirectional): dir = DATADIR. A = MD (Pico), B = D (bus).
    UD = xcvr("U1", (203.2, 76.2), "DATADIR")
    for i in range(8):
        N(UD, "A%d" % i, "MD%d" % i)
        N(UD, "B%d" % i, "D%d" % i)
    # Address (output only): dir tied high (+3V3 => A->B). A = MA, B = A(bus).
    UA0 = xcvr("U2", (203.2, 152.4), "+3V3")
    UA1 = xcvr("U3", (279.4, 152.4), "+3V3")
    UA2 = xcvr("U4", (355.6, 152.4), "+3V3")
    for i in range(8):
        N(UA0, "A%d" % i, "MA%d" % i);        N(UA0, "B%d" % i, "A%d" % i)
        N(UA1, "A%d" % i, "MA%d" % (8 + i));  N(UA1, "B%d" % i, "A%d" % (8 + i))
    for i in range(4):
        N(UA2, "A%d" % i, "MA%d" % (16 + i)); N(UA2, "B%d" % i, "A%d" % (16 + i))
    for i in range(4, 8):
        sch.no_connect(UA2.pin_xy("A%d" % i)); sch.no_connect(UA2.pin_xy("B%d" % i))
    # Control OUT (output only): dir tied high. A = M_* (internal), B = bus.
    UCO0 = xcvr("U5", (203.2, 228.6), "+3V3")
    co0 = [("M_MEMR", "~{MEMR}"), ("M_MEMW", "~{MEMW}"), ("M_IOR", "~{IOR}"),
           ("M_IOW", "~{IOW}"), ("M_AEN", "AEN"), ("M_RESETDRV", "RESET_DRV"),
           ("M_TC", "TC"), ("M_BALE", "BALE")]
    for i, (a, b) in enumerate(co0):
        N(UCO0, "A%d" % i, a); N(UCO0, "B%d" % i, b)
    UCO1 = xcvr("U6", (279.4, 228.6), "+3V3")
    co1 = [("M_DACK1", "~{DACK1}"), ("M_DACK2", "~{DACK2}"),
           ("M_DACK3", "~{DACK3}"), ("M_REFRESH", "~{REFRESH}")]
    for i, (a, b) in enumerate(co1):
        N(UCO1, "A%d" % i, a); N(UCO1, "B%d" % i, b)
    for i in range(4, 8):
        sch.no_connect(UCO1.pin_xy("A%d" % i)); sch.no_connect(UCO1.pin_xy("B%d" % i))
    # Control IN (input only): dir tied low (GND => B->A). B = bus, A = *_S.
    # NOTE: IRQ8 no longer exists on the isa_conn header (pin 15 -> GND; the
    # RTC is on-board).  The IRQ8 lane is kept so the firmware bit map is
    # stable; its card-local pull-down (R12 below) makes it always read 0.
    UCI0 = xcvr("U7", (355.6, 228.6), "GND")
    ci0 = ["IRQ2", "IRQ3", "IRQ4", "IRQ5", "IRQ6", "IRQ7", "IRQ8", "DRQ1"]
    for i, b in enumerate(ci0):
        N(UCI0, "B%d" % i, b); N(UCI0, "A%d" % i, b + "_S")
    UCI1 = xcvr("U8", (431.8, 228.6), "GND")
    ci1 = [("DRQ2", "DRQ2_S"), ("DRQ3", "DRQ3_S"), ("~{IOCHCK}", "IOCHCK_S"),
           ("IOCHRDY", "IOCHRDY_S"), ("CLK", "CLK_S")]
    for i, (b, a) in enumerate(ci1):
        N(UCI1, "B%d" % i, b); N(UCI1, "A%d" % i, a)
    for i in range(5, 8):
        sch.no_connect(UCI1.pin_xy("A%d" % i)); sch.no_connect(UCI1.pin_xy("B%d" % i))
    decouple("C3", (190.5, 40.64), "+3V3")   # transceiver bank
    decouple("C4", (355.6, 40.64), "+3V3")

    # ---- OUT shift chain: 4x 74HC595 @3V3, split latches ----------------
    # U9/U10/U11 = address (RCLK_ADDR); U12 = control byte (RCLK_CTRL).
    UO0 = s595("U9",  (60.96, 304.8), "RCLK_ADDR")
    N(UO0, "SER", "SER")
    for i, q in enumerate(["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]):
        N(UO0, q, "MA%d" % i)
    UO1 = s595("U10", (137.16, 304.8), "RCLK_ADDR")
    N(UO0, "QH'", "SER_A01"); N(UO1, "SER", "SER_A01")
    for i, q in enumerate(["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]):
        N(UO1, q, "MA%d" % (8 + i))
    UO2 = s595("U11", (213.36, 304.8), "RCLK_ADDR")
    N(UO1, "QH'", "SER_A12"); N(UO2, "SER", "SER_A12")
    for i, q in enumerate(["QA", "QB", "QC", "QD"]):
        N(UO2, q, "MA%d" % (16 + i))
    # address-latch spare outputs carry the clock config selects. These are
    # rewritten by every 24-bit address shift (RCLK_ADDR), so firmware MUST
    # include the same select bits in each address word. DUT_PWR_EN does NOT
    # live here -- one slip would glitch DUT power mid-test; it rides the
    # control latch (U12 QH) that address updates never touch.
    N(UO2, "QE", "SPEED_SEL")
    N(UO2, "QF", "CLK_SRC")
    sch.no_connect(UO2.pin_xy("QG"))
    sch.no_connect(UO2.pin_xy("QH"))
    UOC = s595("U12", (289.56, 304.8), "RCLK_CTRL")
    N(UO2, "QH'", "SER_A2C"); N(UOC, "SER", "SER_A2C")
    ctl = ["M_AEN", "M_RESETDRV", "M_TC", "M_DACK1", "M_DACK2", "M_DACK3", "M_BALE"]
    for q, net in zip(["QA", "QB", "QC", "QD", "QE", "QF", "QG"], ctl):
        N(UOC, q, net)
    N(UOC, "QH", "DUT_PWR_EN")     # on the CONTROL latch: safe from addr shifts
    sch.no_connect(UOC.pin_xy("QH'"))
    decouple("C5", (60.96, 274.32), "+3V3")
    sch.text("OUT chain: address (U9-U11, RCLK_ADDR) + control byte (U12, "
             "RCLK_CTRL). Address-only updates shift 24b; controls stay latched.",
             (60.96, 335.28))

    # ---- IN shift chain: 2x 74HCT165 @3V3 (full-duplex, shared SRCLK) ----
    # U13 nearest Pico (Q7 -> IN_QH); U14 cascades in via DS.
    UI0 = s165("U13", (365.76, 304.8))
    in0 = ["IRQ2_S", "IRQ3_S", "IRQ4_S", "IRQ5_S", "IRQ6_S", "IRQ7_S",
           "IRQ8_S", "DRQ1_S"]
    for i, d in enumerate(in0):
        N(UI0, "D%d" % i, d)
    N(UI0, "Q7", "IN_QH")
    N(UI0, "DS", "IN_CASCADE")
    sch.no_connect(UI0.pin_xy("~{Q7}"))
    UI1 = s165("U14", (441.96, 304.8))
    in1 = ["DRQ2_S", "DRQ3_S", "IOCHCK_S"]
    for i, d in enumerate(in1):
        N(UI1, "D%d" % i, d)
    for i in range(3, 8):
        N(UI1, "D%d" % i, "GND")          # unused parallel inputs tied low
    N(UI1, "Q7", "IN_CASCADE")
    N(UI1, "DS", "GND")                    # far end of the cascade
    sch.no_connect(UI1.pin_xy("~{Q7}"))
    decouple("C6", (365.76, 274.32), "+3V3")
    sch.text("IN chain: IRQ2-8 / DRQ1-3 / IOCHCK# -> IN_QH (U14 cascades into "
             "U13). Sampled occasionally; off the hot path.", (365.76, 335.28))

    # ---- clock tree: 14.318 can osc -> /2, /3 -> speed mux -> src mux ----
    #      -> 5V buffer -> bus CLK.  OSC drives the bus OSC pin directly.
    # Powered from V5RAW (UNswitched, spec S8): CLK/OSC generation and the
    # CLK_SENSE frequency report must work before DUT power is enabled, and an
    # unpowered tree would be back-powered through its clamp diodes by the
    # Pico's 3.3 V PIO_CLK / '595 select lines.
    # 14.318 canned XOs are only stocked as 3.3 V parts: the oscillator runs
    # from +3V3 (unswitched, Pico rail) and a spare U19 HCT gate squares it up
    # to the 5 V OSC net. HC-grade '161/'157 (no HCT/HC163 or HCT157 at JLC)
    # are fine in the 5 V clock chain, EXCEPT that their 3.3 V-driven inputs
    # (SPEED_SEL / CLK_SRC selects from the '595, PIO_CLK from the Pico) must
    # come through U19's HCT gates -- inverting, so the mux I0/I1 pairs are
    # swapped to keep firmware polarity, and PIO_CLK's phase flip is harmless.
    osc = sch.place("Oscillator:ACO-xxxMHz", "OSC1", "14.31818MHz", at=(60.96, 45.72))
    N(osc, "Vcc", "+3V3", dx=0, dy=-2.54)
    N(osc, "GND", "GND", dx=0, dy=2.54)
    N(osc, "OUT", "OSC_3V3")
    ff = sch.place("mini-xt:74HCT74", "U15", at=(137.16, 45.72))     # /2
    N(ff, "VCC", "V5RAW", dx=0, dy=-2.54); N(ff, "GND", "GND", dx=0, dy=2.54)
    N(ff, "C", "OSC"); N(ff, "D", "CLK_QN"); N(ff, "~{Q}", "CLK_QN"); N(ff, "Q", "CLK7")
    N(ff, "~{S}", "V5RAW"); N(ff, "~{R}", "V5RAW")
    # FF2 unused: inputs tied (pin numbers due to duplicate names across units)
    N(ff, "12", "GND"); N(ff, "11", "GND")        # FF2 D and CP
    N(ff, "10", "V5RAW"); N(ff, "13", "V5RAW")   # FF2 ~S and ~R
    sch.no_connect(ff.pin_xy("9")); sch.no_connect(ff.pin_xy("8"))   # FF2 Q and ~Q
    d3 = sch.place("mini-xt:74HCT163", "U16", "74HC161", at=(213.36, 45.72))  # /3 (preset-to-3)
    N(d3, "VCC", "V5RAW", dx=0, dy=-2.54); N(d3, "GND", "GND", dx=0, dy=2.54)
    N(d3, "CP", "OSC")
    N(d3, "D0", "V5RAW"); N(d3, "D1", "GND"); N(d3, "D2", "V5RAW"); N(d3, "D3", "V5RAW")
    N(d3, "CEP", "V5RAW"); N(d3, "CET", "V5RAW"); N(d3, "~{MR}", "V5RAW")
    N(d3, "TC", "DIV3_TC"); N(d3, "~{PE}", "DIV3_LD")   # TC -> U19 inverter -> ~PE (reload)
    N(d3, "Q0", "CLK4")
    m1 = sch.place("mini-xt:74HCT157", "U17", "74HC157", at=(60.96, 106.68))  # speed mux
    N(m1, "VCC", "V5RAW", dx=0, dy=-2.54); N(m1, "GND", "GND", dx=0, dy=2.54)
    N(m1, "I0a", "CLK4"); N(m1, "I1a", "CLK7"); N(m1, "S", "SPEED_INV")
    N(m1, "E", "GND"); N(m1, "Za", "CLK_HW")
    # Unused mux sections tied
    for p in ("I0b", "I1b", "I0c", "I1c", "I0d", "I1d"):
        N(m1, p, "GND")
    for p in ("Zb", "Zc", "Zd"):
        sch.no_connect(m1.pin_xy(p))
    m2 = sch.place("mini-xt:74HCT157", "U18", "74HC157", at=(137.16, 106.68)) # source mux
    N(m2, "VCC", "V5RAW", dx=0, dy=-2.54); N(m2, "GND", "GND", dx=0, dy=2.54)
    N(m2, "I0a", "PIO_CLK_5V"); N(m2, "I1a", "CLK_HW"); N(m2, "S", "CLKSRC_INV")
    N(m2, "E", "GND"); N(m2, "Za", "CLK_PRE")
    # Unused mux sections tied
    for p in ("I0b", "I1b", "I0c", "I1c", "I0d", "I1d"):
        N(m2, p, "GND")
    for p in ("Zb", "Zc", "Zd"):
        sch.no_connect(m2.pin_xy(p))
    buf = sch.place("mini-xt:74HCT04", "U19", at=(213.36, 106.68))   # HCT: reads 3.3V, drives 5V
    N(buf, "VCC", "V5RAW", dx=0, dy=-2.54); N(buf, "GND", "GND", dx=0, dy=2.54)
    N(buf, "P1", "CLK_PRE"); N(buf, "P2", "CLK")
    # active-high TC inverted into the '161's active-low ~PE: reload the preset
    # at count 15 -> states 13,14,15 = divide-by-3 (same trick as cpu_core U13).
    N(buf, "P3", "DIV3_TC"); N(buf, "P4", "DIV3_LD")
    N(buf, "P5", "SPEED_SEL"); N(buf, "P6", "SPEED_INV")     # 3.3V '595 -> 5V (inv)
    N(buf, "P9", "CLK_SRC"); N(buf, "P8", "CLKSRC_INV")      # 3.3V '595 -> 5V (inv)
    N(buf, "P11", "PIO_CLK"); N(buf, "P10", "PIO_CLK_5V")    # 3.3V Pico -> 5V (inv, harmless)
    N(buf, "P13", "OSC_3V3"); N(buf, "P12", "OSC")           # 3.3V XO -> 5V OSC
    decouple("C7", (60.96, 76.2), "V5RAW")
    sch.text("Clock: 14.318 OSC -> /2 (U15) & /3 (U16) -> SPEED_SEL mux (U17) -> "
             "CLK_SRC mux (U18, PIO override) -> buffer (U19) -> bus CLK. CLK "
             "sensed back to Pico via U8 (CLK_S). /3 preset per cpu_core.",
             (60.96, 132.08))

    # ---- power: USB 5V + external jack -> OR-ing -> P-FET -> bus +5V -----
    jack = sch.place("Connector:Barrel_Jack", "J3", "5V jack", at=(495.3, 60.96))
    N(jack, "1", "VEXT"); N(jack, "2", "GND")
    dext = sch.place("Device:D_Schottky", "D1", at=(520.7, 60.96))   # jack OR-ing
    N(dext, "2", "VEXT"); N(dext, "1", "V5RAW")                       # 2=A, 1=K
    dusb = sch.place("Device:D_Schottky", "D2", at=(520.7, 76.2))    # USB OR-ing
    N(dusb, "2", "+5V_USB"); N(dusb, "1", "V5RAW")
    q = sch.place("Device:Q_PMOS", "Q1", at=(546.1, 68.58))          # high-side switch
    N(q, "S", "V5RAW"); N(q, "D", "+5V"); N(q, "G", "PFET_G")
    # Gate drive: a 3.3 V GPIO/'595 level can neither reach Vgs=0 (off) nor be
    # pulled to +3V3 without leaving the FET half-on (Vgs=-1.7V from a 5V
    # source). So the gate is pulled to the SOURCE rail (V5RAW, R5 = off by
    # default) and driven low through an open-collector NPN (Q2): DUT_PWR_EN
    # high -> Q2 on -> gate ~0V -> Vgs=-5V -> DUT powered.
    pull("R5", (546.1, 45.72), "PFET_G", "V5RAW")     # FET OFF by default
    q2 = sch.place("Transistor_BJT:2N3904", "Q2", at=(546.1, 96.52))
    N(q2, "C", "PFET_G"); N(q2, "E", "GND")
    r4 = sch.place("Device:R", "R4", "4.7k", at=(525.78, 96.52))
    sch.net(r4, "1", "DUT_PWR_EN", kind="label", dx=0, dy=-2.54)
    sch.net(r4, "2", "PFET_B", kind="label", dx=0, dy=2.54)
    N(q2, "B", "PFET_B")
    # Bulk + soft-start on DUT power path
    cb = sch.place("Device:C_Polarized", "C9", "22uF", at=(508.0, 91.44))   # V5RAW bulk
    sch.net(cb, "1", "V5RAW", kind="label", dx=0, dy=-2.54)
    sch.net(cb, "2", "GND", kind="label", dx=0, dy=2.54)
    cg = sch.place("Device:C", "C10", "100nF", at=(533.4, 45.72))   # Q1 gate-source: soft-start ramp
    sch.net(cg, "1", "V5RAW", kind="label", dx=0, dy=-2.54)
    sch.net(cg, "2", "PFET_G", kind="label", dx=0, dy=2.54)
    # TVS clamp on the switched DUT rail
    dt = sch.place("Device:D_Zener", "D3", "SMBJ5.0A", at=(571.5, 91.44))   # DUT rail clamp
    sch.net(dt, "K", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(dt, "A", "GND", kind="label", dx=0, dy=2.54)
    # idle network (tester = motherboard): buffers default OFF; ready idle high.
    pull("R1", (152.4, 96.52), "~{BUF_EN}", "+3V3")   # buffers default disabled
    pull("R2", (571.5, 45.72), "IOCHRDY", "+5V")      # IOCHRDY idle high (ready)
    pull("R3", (571.5, 76.2), "DUT_PWR_EN", "GND")    # DUT power OFF until firmware drives
    # spec S4/S9: IRQ/DRQ idle pull-downs -- a DUT that tri-states its IRQ (the
    # PC convention) must read as 0 at the '165 IN chain, not float.
    for i, net in enumerate(["IRQ2", "IRQ3", "IRQ4", "IRQ5", "IRQ6", "IRQ7",
                             "IRQ8", "DRQ1", "DRQ2", "DRQ3"]):
        pull("R%d" % (6 + i), (38.1 + 15.24 * i, 370.84), net, "GND")
    decouple("C8", (490.22, 91.44), "+5V")            # bus rail bulk/decoupling
    sch.text("Power: USB 5V (logic) + external jack (bus/DUT) OR-ed via D1/D2 to "
             "V5RAW; Q1 P-FET switches bus +5V. Soft-start: C10 ramps Q1 gate. "
             "DUT rail protected by bulk C9 + TVS clamp D3. Gate pulled to V5RAW (off), pulled "
             "low by Q2 NPN when DUT_PWR_EN=1.", (470.0, 30.48))

    # ---- extra decoupling: ~1 cap per 1-2 ICs ---------------------------
    decouple("C11", (241.3, 40.64), "+3V3")     # xcvr bank
    decouple("C12", (302.26, 40.64), "+3V3")    # xcvr bank
    decouple("C13", (419.1, 40.64), "+3V3")     # xcvr bank
    decouple("C14", (137.16, 274.32), "+3V3")   # '595 chain
    decouple("C15", (213.36, 274.32), "+3V3")   # '595 chain
    decouple("C16", (441.96, 274.32), "+3V3")   # '165 chain
    decouple("C17", (167.64, 76.2), "V5RAW")    # clock tree

    # ---- DUT connectors -------------------------------------------------
    # J1: real 8-bit ISA card-edge slot (Connector:Bus_ISA_8bit, true pinout).
    #     -5V/-12V/+12V/UNUSED are left NC (we provide no analog rails).
    slot = sch.place("Connector:Bus_ISA_8bit", "J1", "ISA slot (8-bit)",
                     at=(508.0, 254.0))
    slot_map = {
        "GND": "GND", "VCC": "+5V", "RESET": "RESET_DRV",
        "~{SMEMW}": "~{MEMW}", "~{SMEMR}": "~{MEMR}", "~{IOW}": "~{IOW}",
        "~{IOR}": "~{IOR}", "~{DACK3}": "~{DACK3}", "DRQ3": "DRQ3",
        "~{DACK1}": "~{DACK1}", "DRQ1": "DRQ1", "~{DACK0}": "~{REFRESH}",
        "CLK": "CLK", "IRQ7": "IRQ7", "IRQ6": "IRQ6", "IRQ5": "IRQ5",
        "IRQ4": "IRQ4", "IRQ3": "IRQ3", "IRQ2": "IRQ2", "~{DACK2}": "~{DACK2}",
        "TC": "TC", "ALE": "BALE", "OSC": "OSC", "IO": "~{IOCHCK}",
        "IO_READY": "IOCHRDY", "AEN": "AEN", "DRQ2": "DRQ2",
    }
    for i in range(20):
        slot_map["BA%02d" % i] = "A%d" % i
    for i in range(8):
        slot_map["DB%d" % i] = "D%d" % i
    NC = {"-5V", "-12V", "+12V", "UNUSED"}

    def sdir(comp, num, length=5.08):
        a = comp.sdef.pin(num).angle % 360
        if a == 0:   return (-length, 0.0)
        if a == 180: return (length, 0.0)
        if a == 90:  return (0.0, length)
        return (0.0, -length)

    for p in slot.sdef.pins:
        if p.name in NC:
            sch.no_connect(slot.pin_xy(p.number)); continue
        net = slot_map.get(p.name)
        if net is None:
            sch.no_connect(slot.pin_xy(p.number)); continue
        dx, dy = sdir(slot, p.number)
        sch.net(slot, p.number, net, kind="label", dx=dx, dy=dy)

    # J2: 60-pin sidecar header (shared isa_conn building block; soft-card compat).
    isa_conn.place_header(sch, "J2", (571.5, 152.4), label="ISA SIDECAR")

    # ---- decoupling (representative) ------------------------------------
    decouple("C1", (40.64, 50.8), "+3V3")
    decouple("C2", (55.88, 50.8), "+3V3")

    sch.text("Standalone ISA card tester PCB (card_isatest). Bus + power via the "
             "on-board ISA slot (J1) and 60-pin sidecar header (J2).", (38.1, 12.7))

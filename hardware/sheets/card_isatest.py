"""card_isatest -- standalone ISA card tester: a stock Raspberry Pi Pico acts as
the ISA host / bus master to exercise a device-under-test (DUT) card over USB
serial. See docs/superpowers/specs/2026-07-01-isa-test-card-design.md.

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
        """74HCT165 PISO @3V3. CP shared with SRCLK; ~{PL}=IN_PL."""
        u = sch.place("mini-xt:74HCT165", ref, "74HCT165", at=at)
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
    # address-latch spare outputs carry the STATIC config selects (set once)
    N(UO2, "QE", "SPEED_SEL")
    N(UO2, "QF", "CLK_SRC")
    N(UO2, "QG", "DUT_PWR_EN")
    sch.no_connect(UO2.pin_xy("QH"))
    UOC = s595("U12", (289.56, 304.8), "RCLK_CTRL")
    N(UO2, "QH'", "SER_A2C"); N(UOC, "SER", "SER_A2C")
    ctl = ["M_AEN", "M_RESETDRV", "M_TC", "M_DACK1", "M_DACK2", "M_DACK3", "M_BALE"]
    for q, net in zip(["QA", "QB", "QC", "QD", "QE", "QF", "QG"], ctl):
        N(UOC, q, net)
    sch.no_connect(UOC.pin_xy("QH"))
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
    osc = sch.place("Oscillator:ACO-xxxMHz", "OSC1", "14.31818MHz", at=(60.96, 45.72))
    N(osc, "Vcc", "+5V", dx=0, dy=-2.54)
    N(osc, "GND", "GND", dx=0, dy=2.54)
    N(osc, "OUT", "OSC")
    ff = sch.place("mini-xt:74HCT74", "U15", at=(137.16, 45.72))     # /2
    N(ff, "VCC", "+5V", dx=0, dy=-2.54); N(ff, "GND", "GND", dx=0, dy=2.54)
    N(ff, "C", "OSC"); N(ff, "D", "CLK_QN"); N(ff, "~{Q}", "CLK_QN"); N(ff, "Q", "CLK7")
    N(ff, "~{S}", "+5V"); N(ff, "~{R}", "+5V")
    d3 = sch.place("mini-xt:74HCT163", "U16", at=(213.36, 45.72))    # /3 (preset-to-3)
    N(d3, "VCC", "+5V", dx=0, dy=-2.54); N(d3, "GND", "GND", dx=0, dy=2.54)
    N(d3, "CP", "OSC")
    N(d3, "D0", "+5V"); N(d3, "D1", "GND"); N(d3, "D2", "+5V"); N(d3, "D3", "+5V")
    N(d3, "CEP", "+5V"); N(d3, "CET", "+5V"); N(d3, "~{MR}", "+5V")
    N(d3, "TC", "DIV3_TC"); N(d3, "~{PE}", "DIV3_LD")   # preset-to-3 per cpu_core
    N(d3, "Q0", "CLK4")
    m1 = sch.place("mini-xt:74HCT157", "U17", at=(60.96, 106.68))    # speed mux
    N(m1, "VCC", "+5V", dx=0, dy=-2.54); N(m1, "GND", "GND", dx=0, dy=2.54)
    N(m1, "I0a", "CLK7"); N(m1, "I1a", "CLK4"); N(m1, "S", "SPEED_SEL")
    N(m1, "E", "GND"); N(m1, "Za", "CLK_HW")
    m2 = sch.place("mini-xt:74HCT157", "U18", at=(137.16, 106.68))   # source mux
    N(m2, "VCC", "+5V", dx=0, dy=-2.54); N(m2, "GND", "GND", dx=0, dy=2.54)
    N(m2, "I0a", "CLK_HW"); N(m2, "I1a", "PIO_CLK"); N(m2, "S", "CLK_SRC")
    N(m2, "E", "GND"); N(m2, "Za", "CLK_PRE")
    buf = sch.place("mini-xt:74HCT04", "U19", at=(213.36, 106.68))   # 5V buffer
    N(buf, "VCC", "+5V", dx=0, dy=-2.54); N(buf, "GND", "GND", dx=0, dy=2.54)
    N(buf, "P1", "CLK_PRE"); N(buf, "P2", "CLK")
    for p in ("P3", "P5", "P9", "P11", "P13"):
        N(buf, p, "GND")                                # tie unused inverter inputs
    for p in ("P4", "P6", "P8", "P10", "P12"):
        sch.no_connect(buf.pin_xy(p))
    decouple("C7", (60.96, 76.2), "+5V")
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
    N(q, "S", "V5RAW"); N(q, "D", "+5V"); N(q, "G", "DUT_PWR_EN")
    # idle network (tester = motherboard): buffers default OFF; ready idle high.
    pull("R1", (152.4, 96.52), "~{BUF_EN}", "+3V3")   # buffers default disabled
    pull("R2", (571.5, 45.72), "IOCHRDY", "+5V")      # IOCHRDY idle high (ready)
    pull("R3", (571.5, 76.2), "DUT_PWR_EN", "+3V3")   # FET off until firmware drives
    decouple("C8", (490.22, 91.44), "+5V")            # bus rail bulk/decoupling
    sch.text("Power: USB 5V (logic) + external jack (bus/DUT) OR-ed via D1/D2 to "
             "V5RAW; Q1 P-FET (DUT_PWR_EN) switches bus +5V. See questions doc for "
             "gate-drive/level detail.", (470.0, 30.48))

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

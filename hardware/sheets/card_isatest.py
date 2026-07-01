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

    # ---- decoupling (representative) ------------------------------------
    decouple("C1", (40.64, 50.8), "+3V3")
    decouple("C2", (55.88, 50.8), "+3V3")

    sch.text("Standalone ISA card tester PCB (card_isatest). Bus + power via the "
             "on-board ISA slot (J1) and 60-pin sidecar header (J2).", (38.1, 12.7))

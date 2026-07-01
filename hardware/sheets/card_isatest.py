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

    # ---- decoupling (representative) ------------------------------------
    decouple("C1", (40.64, 50.8), "+3V3")
    decouple("C2", (55.88, 50.8), "+3V3")

    sch.text("Standalone ISA card tester PCB (card_isatest). Bus + power via the "
             "on-board ISA slot (J1) and 60-pin sidecar header (J2).", (38.1, 12.7))

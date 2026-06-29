"""bus_mcu -- Bus Master MCU (RP2350B): soft chipset + bus master (design doc S5).

This is the heaviest sheet: the RP2350B "fast hands" node sits on the buffered
XT/ISA backplane as **slave and master**.  It carries:

  * M1  Core2350B module (RP2350B) -- the Bus MCU; self-powers 3V3 from +5V.  Soft dual-8259 PIC, 8254 PIT, 8255/8042 KBC,
        8237 DMA, NMI mask, POST snoop -- all in firmware on core0+PIO / core1.
  * Local 74LVC245A level shifters, powered from the module's own 3V3 (3V3_BUS):
        - U2  data group   D0-D7   (DIR = DATADIR, read/write of the cycle)
        - U6  control grp  IOR/IOW/MEMR/MEMW/AEN/RESET_DRV/TC/BALE (DIR = HLDA, §5.2)
        - U3/U4/U5 address group A0-A19  (DIR = HLDA, bus master/slave role)
        Per §4.2 the Bus MCU needs BIDIRECTIONAL transceivers (it is also a bus
        master), unlike a pure-slave soft card -- hence the role-driven DIR.
  * External 20-bit loadable address counter (§5.1): U7..U11, 5x 74HCT163
        cascaded.  Outputs drive A0-A19; loaded from D0-D7 (3 byte-lanes steered
        by CNT_LD0/1/2); advanced one byte per CNT_CLK pulse.  Cuts master-cycle
        address cost from ~20 GPIO to ~4.
  * IRQ collector (§5.2): U12, 74HCT165 PISO -- collects IRQ lines onto 3 pins
        (IRQ_LOAD / IRQ_CLK / IRQ_SER).
  * UART cross-MCU link to the Supervisor (§5.3): LINK_B2S (TX), LINK_S2B (RX).
  * SPEED_SEL (out) -> clock mux in cpu_core: set before releasing V20 reset
    (moved here from the Supervisor; Supervisor sends the choice over the link).
    Address/control transceiver DIR is HLDA-derived externally to free the GPIO.

Addr/ctrl xcvr DIR = HLDA (master/slave role, §5.2); DATADIR is the data
read/write direction.  See hardware/notes/questions-bus_mcu.md for design picks.
"""
import mxbus
from mxbus import pin

NAME = "bus_mcu"
TITLE = "Bus Master MCU (RP2350B) -- soft chipset + bus master"

# ---- interface (hierarchical) pins, with sensible directions --------------
_DIR = {
    # ISA control / status
    "~{MEMR}": "bidirectional", "~{MEMW}": "bidirectional",
    "~{IOR}": "bidirectional", "~{IOW}": "bidirectional",
    "BALE": "input", "AEN": "bidirectional", "IOCHRDY": "bidirectional",
    "~{IOCHCK}": "input", "CLK": "input", "RESET_DRV": "output", "TC": "output",
    "DRQ1": "input", "DRQ2": "input", "DRQ3": "input",
    "~{DACK1}": "output", "~{DACK2}": "output", "~{DACK3}": "output",
    # private V20 <-> Bus MCU
    "HOLD": "output", "HLDA": "input", "READY": "output",
    "~{RD}": "input", "~{WR}": "input", "IO/~{M}": "input",
    "INTR": "output", "~{INTA}": "input", "NMI": "output", "~{CPURESET}": "output",
    # counter strobes + link
    "CNT_CLK": "output", "CNT_LD0": "output", "CNT_LD1": "output", "CNT_LD2": "output",
    "LINK_B2S": "output", "LINK_S2B": "input",
}
_CTRL = ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN", "IOCHRDY",
         "~{IOCHCK}", "CLK", "RESET_DRV", "TC", "DRQ1", "DRQ2", "DRQ3",
         "~{DACK1}", "~{DACK2}", "~{DACK3}"]

PINS = (
    [pin(s, "bidirectional") for s in mxbus.ADDR] +
    [pin(s, "bidirectional") for s in mxbus.DATA] +
    [pin(s, "input") for s in mxbus.IRQ] +
    [pin(s, _DIR[s]) for s in _CTRL] +
    [pin(s, _DIR[s]) for s in mxbus.PRIV_CPU] +
    [pin(s, _DIR[s]) for s in mxbus.PRIV_COUNTER] +
    [pin("LINK_B2S", "output"), pin("LINK_S2B", "input"),
     pin("SPEED_SEL", "output")]
)

# RP2350B GPIO -> internal/interface net (MCU-side names).  ~48 GPIO budget (§5.2).
GPIO_NET = {}
for i in range(8):
    GPIO_NET[i] = "MD%d" % i            # data, MCU side of U2
for i in range(8):
    GPIO_NET[8 + i] = "MA%d" % i        # low address sense (slave I/O decode)
GPIO_NET.update({
    16: "M_IOR", 17: "M_IOW", 18: "M_MEMR", 19: "M_MEMW",
    20: "M_BALE", 21: "M_AEN", 22: "M_RESETDRV",
    23: "IOCHRDY", 24: "~{IOCHCK}",                 # direct input sense
    25: "HOLD", 26: "HLDA",
    27: "INTR", 28: "~{INTA}", 29: "NMI",
    30: "IRQ_LOAD", 31: "IRQ_CLK", 32: "IRQ_SER",   # '165 collector
    33: "DRQ1", 34: "~{DACK1}", 35: "M_TC",         # on-board DMA channel
    36: "CNT_CLK", 37: "CNT_LD0", 38: "CNT_LD1", 39: "CNT_LD2",
    40: "LINK_B2S", 41: "LINK_S2B",                 # UART link to Supervisor
    42: "SPEED_SEL", 43: "DATADIR",                 # SPEED_SEL out; data DIR
    44: "READY", 45: "~{CPURESET}",                 # V20 handshake (private)
    46: "~{RD}", 47: "~{WR}",                       # raw V20 strobe sense
})
# net -> hier-label shape, so MCU stubs carry the right cross-sheet direction
_NET_SHAPE = {"IOCHRDY": "bidirectional", "~{IOCHCK}": "input",
              "HOLD": "output", "HLDA": "input", "INTR": "output",
              "~{INTA}": "input", "NMI": "output", "READY": "output",
              "~{CPURESET}": "output", "~{RD}": "input", "~{WR}": "input",
              "DRQ1": "input", "~{DACK1}": "output",
              "CNT_CLK": "output", "CNT_LD0": "output", "CNT_LD1": "output",
              "CNT_LD2": "output", "LINK_B2S": "output", "LINK_S2B": "input",
              "SPEED_SEL": "output"}
_HIER = set(_NET_SHAPE) | {"IRQ_LOAD", "IRQ_CLK", "IRQ_SER"}  # IRQ_* are internal labels


def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 30.48))

    # -- stub a pin out in the direction it physically faces (by pin angle) --
    def sdir(comp, key, length):
        a = comp.sdef.pin(key).angle % 360
        if a == 0:   return (-length, 0.0)     # left-edge pin -> stub left
        if a == 180: return (length, 0.0)      # right-edge pin -> stub right
        if a == 90:  return (0.0, length)      # bottom pin -> stub down
        if a == 270: return (0.0, -length)     # top pin -> stub up
        return (length, 0.0)

    def N(comp, key, name, kind="label", shape="bidirectional", length=5.08):
        dx, dy = sdir(comp, key, length)
        return sch.net(comp, key, name, kind=kind, shape=shape, dx=dx, dy=dy)

    def decouple(ref, at, hi="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", hi, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # =================================================================
    #  M1 -- Waveshare Core2350B module (RP2350B).  Order the 0MB-PSRAM
    #  variant: this is the pin-bound node, so GPIO47 stays free for ~{WR}.
    # =================================================================
    M1 = sch.place("mini-xt:Core2350B", "M1", "Core2350B (0MB PSRAM)",
                   at=(101.6, 152.4))
    # Self-powered: +5V -> module VBUS; the module's onboard ME6217 LDO makes its
    # own 3V3 (3V3_BUS), which also powers THIS card's level shifters. 3V3_BUS is a
    # sheet-local rail -- NOT tied to +3V3 or the other module's 3V3 (no paralleling).
    N(M1, "VBUS", "+5V", length=2.54)
    N(M1, "3V3", "3V3_BUS", length=2.54)
    N(M1, "59", "GND", length=2.54)
    N(M1, "60", "GND", length=2.54)
    for nm in ("3V3_EN", "RUN", "ADC_VREF", "USB_DP", "USB_DM", "BOOTSEL",
               "SWCLK", "SWDIO"):
        sch.no_connect(M1.pin_xy(nm))    # 3V3_EN held high by module's 100k; flash/PSRAM internal
    # GPIO -> interface/internal nets (same §5.2 map as the bare chip)
    for idx, net in GPIO_NET.items():
        key = "GPIO%d" % idx
        if net in _NET_SHAPE:
            N(M1, key, net, kind="hier", shape=_NET_SHAPE[net])
        else:
            N(M1, key, net)
    sch.text("Core2350B module (RP2350B): soft PIC x2 / PIT / KBC / DMA / NMI / POST.", (50.8, 86.36))
    sch.text("Self-powers 3V3 from +5V (onboard ME6217 LDO); user LED on GPIO39 (=CNT_LD2).", (50.8, 88.9))

    # =================================================================
    #  Level shifters (74LVC245A) -- value override on mini-xt:74LVC245A
    # =================================================================
    def xcvr(ref, at, dir_net):
        u = sch.place("mini-xt:74LVC245A", ref, "74LVC245A", at=at)
        N(u, "VCC", "3V3_BUS", length=2.54)
        N(u, "GND", "GND", length=2.54)
        N(u, "A->B", dir_net)              # DIR
        N(u, "CE", "GND")                  # OE active-low: always on here (Q3)
        return u

    # data group: MCU MD0-7 <-> bus D0-7, dir = DATADIR (read/write)
    U2 = xcvr("U2", (200.66, 76.2), "DATADIR")
    for i in range(8):
        N(U2, "A%d" % i, "MD%d" % i)
        N(U2, "B%d" % i, "D%d" % i)

    # control group: dir = HLDA (bus role, HLDA-derived per §5.2)
    U6 = xcvr("U6", (200.66, 152.4), "HLDA")
    ctrl_pairs = [("M_IOR", "~{IOR}"), ("M_IOW", "~{IOW}"),
                  ("M_MEMR", "~{MEMR}"), ("M_MEMW", "~{MEMW}"),
                  ("M_AEN", "AEN"), ("M_RESETDRV", "RESET_DRV"),
                  ("M_TC", "TC"), ("M_BALE", "BALE")]
    for i, (a, b) in enumerate(ctrl_pairs):
        N(U6, "A%d" % i, a)
        N(U6, "B%d" % i, b)

    # address group: 3x '245, MCU/counter side MAx <-> bus Ax, dir = HLDA
    U3 = xcvr("U3", (281.94, 76.2), "HLDA")
    U4 = xcvr("U4", (358.14, 76.2), "HLDA")
    U5 = xcvr("U5", (281.94, 152.4), "HLDA")
    for i in range(8):
        N(U3, "A%d" % i, "MA%d" % i);        N(U3, "B%d" % i, "A%d" % i)
        N(U4, "A%d" % i, "MA%d" % (8 + i));  N(U4, "B%d" % i, "A%d" % (8 + i))
    for i in range(4):
        N(U5, "A%d" % i, "MA%d" % (16 + i)); N(U5, "B%d" % i, "A%d" % (16 + i))
    for i in range(4, 8):                     # U5 upper nibble unused
        sch.no_connect(U5.pin_xy("A%d" % i))
        sch.no_connect(U5.pin_xy("B%d" % i))

    # =================================================================
    #  External 20-bit loadable address counter (5x 74HCT163), §5.1
    # =================================================================
    # Each '163 = 4 bits.  Load steered in 3 byte-lanes from D0-D7:
    #   CNT_LD0 -> bits 0-7, CNT_LD1 -> bits 8-15, CNT_LD2 -> bits 16-19.
    # Carry chained TC->CET; all CP = CNT_CLK; outputs drive bus A0-A19.
    cnt_cfg = [  # (ref, x, Dsrc[4], Adst[4], PE, CETin, TCout)
        ("U7",  60.96, [0, 1, 2, 3], [0, 1, 2, 3],     "CNT_LD0", "+5V",     "CNT_TC0"),
        ("U8", 127.00, [4, 5, 6, 7], [4, 5, 6, 7],     "CNT_LD0", "CNT_TC0", "CNT_TC1"),
        ("U9", 193.04, [0, 1, 2, 3], [8, 9, 10, 11],   "CNT_LD1", "CNT_TC1", "CNT_TC2"),
        ("U10", 259.08, [4, 5, 6, 7], [12, 13, 14, 15], "CNT_LD1", "CNT_TC2", "CNT_TC3"),
        ("U11", 325.12, [0, 1, 2, 3], [16, 17, 18, 19], "CNT_LD2", "CNT_TC3", None),
    ]
    for ref, x, dsrc, adst, pe, cetin, tcout in cnt_cfg:
        u = sch.place("mini-xt:74HCT163", ref, at=(x, 271.78))
        N(u, "VCC", "+5V", length=2.54)
        N(u, "GND", "GND", length=2.54)
        for q in range(4):
            N(u, "D%d" % q, "D%d" % dsrc[q])      # load byte-lane from data bus
            N(u, "Q%d" % q, "A%d" % adst[q])      # drives buffered address bus
        N(u, "~{PE}", pe)                          # active-low parallel load
        N(u, "CP", "CNT_CLK")                      # advance one byte per pulse
        N(u, "CEP", "+5V")
        N(u, "CET", cetin)                         # cascade carry-in
        N(u, "~{MR}", "+5V")                       # no async master reset (Q)
        if tcout:
            N(u, "TC", tcout)                      # carry to next stage
        else:
            sch.no_connect(u.pin_xy("TC"))
    sch.text("§5.1 20-bit loadable address counter: load D0-D7 (3 lanes), tick CNT_CLK",
             (60.96, 248.92))

    # =================================================================
    #  IRQ collector -- 74HCT165 PISO, §5.2 (IRQ2..IRQ9; cascade DS for the rest)
    # =================================================================
    U12 = sch.place("mini-xt:74HCT165", "U12", at=(200.66, 233.68))
    N(U12, "VCC", "+5V", length=2.54)
    N(U12, "GND", "GND", length=2.54)
    for i in range(8):
        N(U12, "D%d" % i, "IRQ%d" % (2 + i))       # IRQ2..IRQ9
    N(U12, "~{PL}", "IRQ_LOAD")                     # parallel load strobe
    N(U12, "CP", "IRQ_CLK")                         # shift clock
    N(U12, "~{CE}", "GND")                          # clock enable (active low)
    N(U12, "DS", "GND")                             # serial-in: cascade 2nd '165 here
    N(U12, "Q7", "IRQ_SER")                         # serial out to MCU
    sch.no_connect(U12.pin_xy("~{Q7}"))
    sch.text("§5.2 74HCT165 IRQ collector -> 3 MCU pins (IRQ2..IRQ9; DS chains rest)",
             (180.34, 210.82))

    # Addr/ctrl xcvr DIR uses HLDA (master/slave role, §5.2); derived from the
    # MCU here (GPIO42).  DATADIR (GPIO43) flips with the cycle read/write.
    sch.text("Addr/ctrl DIR = HLDA (bus role, §5.2);  DATADIR = data read/write dir",
             (200.66, 116.84))

    # =================================================================
    #  Decoupling
    # =================================================================
    # module is self-decoupled; these are bulk/decoupling for the local 3V3_BUS
    # rail that powers the level shifters.
    decouple("C1", (40.64, 50.8), "3V3_BUS")
    decouple("C2", (55.88, 50.8), "3V3_BUS")
    bulk = sch.place("Device:C", "C3", "10uF", at=(71.12, 50.8))
    sch.net(bulk, "1", "3V3_BUS", kind="label", dx=0, dy=-2.54)
    sch.net(bulk, "2", "GND", kind="label", dx=0, dy=2.54)
    decouple("C6", (190.5, 40.64), "3V3_BUS")      # data xcvr
    decouple("C7", (271.78, 40.64), "3V3_BUS")     # addr xcvrs
    decouple("C8", (350.52, 40.64), "+3V3")
    decouple("C9", (50.8, 220.98), "+5V")          # counters
    decouple("C10", (190.5, 198.12), "+5V")        # '165

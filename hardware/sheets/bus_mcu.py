"""bus_mcu -- Bus Master MCU (RP2350B): soft chipset + bus master (design doc S5).

This is the heaviest sheet: the RP2350B "fast hands" node sits on the buffered
XT/ISA backplane as **slave and master**.  It carries:

  * M1  Core2350B module (RP2350B) -- the Bus MCU; self-powers 3V3 from +5V via D1 (SS34 Schottky diode-OR).  Soft dual-8259 PIC, 8254 PIT, 8255/8042 KBC,
        8237 DMA, NMI mask, POST snoop -- all in firmware on core0+PIO / core1.
        Ports 0x70/0x71 (RTC index/data) are ALSO emulated here in firmware --
        backed by the PCF8563 I2C RTC on the Supervisor sheet (off-bus), time
        synced over the existing UART link at boot (spec 2026-07-14; see
        hardware/notes/questions-supervisor.md).
  * NO local transceivers (3.3V bus redesign, spec 2026-07-14): the RP2350B GPIOs
        sit on the 3.3V ISA bus DIRECTLY -- they are 5V-tolerant and tri-state
        natively for master/slave role changes.  The six 74LVC245A that bridged
        the old 5V bus (U2 data, U6 strobes, U3/U4/U5 address+BALE, U13 AEN/TC)
        and their DIR logic are DELETED; each GPIO now carries its bus net 1:1
        (see GPIO_NET).  DATADIR's sole consumer (U2 DIR) is gone, freeing GPIO43
        -> reused as EXP_DDIR.  RN3/RN4 (10kx4 arrays) park AEN/TC/HLDA at a defined level
        during the MCU-Hi-Z (BOOTSEL/reset) window (AEN idle-low so cards read
        their I/O decode deasserted; HLDA low so the counter's '244s stay off).
  * External 20-bit loadable address counter (§5.1): U7..U11, 5x 74HCT163
        cascaded.  Loaded from D0-D7 (3 byte-lanes steered by CNT_LD0/1/2);
        advanced one byte per CNT_CLK pulse.  Cuts master-cycle address cost
        from ~20 GPIO to ~4.  The '163 has NO output enable, so the counter
        reaches A0-A19 through U14-U16 (74HC244 @ 3V3, ~OE = ~HLDA): enabled only
        while the MCU owns the bus, opposite the cpu_core '573s (OE = HLDA) --
        the 8282-style address handoff.  These '244s STAY in the 3.3V design
        (they are the counter's only tri-state; deleting them would fight the
        '573 latches on A0-A19 during CPU cycles).
  * RESET_DRV is NOT driven here: the MCU sequences reset via ~{CPURESET} and
        cpu_core's NAND combine drives V20 RESET + bus RESET_DRV.
  * IRQ collector (§5.2): 2x 74HCT165 PISO (U12, U19) -- collects 16 IRQ lines onto 3 pins
        (IRQ_LOAD / IRQ_CLK / IRQ_SER): 16-bit shift, U12 IRQ2-9 then U19 IRQ10-15.
  * UART cross-MCU link to the Supervisor (§5.3): LINK_B2S (TX), LINK_S2B (RX).
  * SPEED_SEL (out) -> clock mux in cpu_core: set before releasing V20 reset
    (moved here from the Supervisor; Supervisor sends the choice over the link).
    Address/control transceiver DIR is HLDA-derived externally to free the GPIO.
  * ~{REFRESH} (out) -> bus REFRESH# (pin 35): driven from the same internal
    ~15 us refresh timer as the 0x61-bit-4 toggle, so DRAM-based ISA cards on the
    bus get refreshed. A refresh cycle reuses the bus-master engine -- it walks the
    refresh row address on A0-A7 via the §5.1 counter and pulses MEMR# -- so only
    the REFRESH# strobe itself needs a GPIO (reclaimed from the raw ~WR sense).
  * SPKR (out) -> audio sheet: PIT ch2 tone / port-61h speaker gate PWM (GPIO22; the bus-CLK
    sense was dropped for it -- PIO tracks bus timing from BALE/strobes).

Data/address/strobe are wired GPIO<->bus directly (no transceivers, no DIR
nets); master/slave role is a firmware tri-state.  HLDA still gates the
counter's '244 output stage (inverted to ~{HLDA} on the parallel sheet's
spare Schmitt gate -- the old U17 hex inverter is deleted).  The EXT scan chain
(U19/U20 '165, PRIV_EXP EXT_*) extends the IRQ collector to sample the
expansion port's isolated IRQ/DRQ lines.
See hardware/notes/questions-bus_mcu.md for design picks.
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
    "BALE": "input", "AEN": "output", "IOCHRDY": "bidirectional",
    "~{IOCHCK}": "input", "TC": "output",
    "DRQ1": "input", "DRQ2": "input", "DRQ3": "input",
    "~{DACK1}": "output", "~{DACK2}": "output", "~{DACK3}": "output",
    # private V20 <-> Bus MCU
    "HOLD": "output", "HLDA": "input", "~{HLDA}": "input", "READY": "output",
    "~{RD}": "input",
    "INTR": "output", "~{INTA}": "input", "NMI": "output", "~{CPURESET}": "output",
    "LINK_B2S": "output", "LINK_S2B": "input",
}
_CTRL = ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN", "IOCHRDY",
         "~{IOCHCK}", "TC", "DRQ1", "DRQ2", "DRQ3",
         "~{DACK1}", "~{DACK2}", "~{DACK3}"]

PINS = (
    [pin(s, "bidirectional") for s in mxbus.ADDR] +
    [pin(s, "bidirectional") for s in mxbus.DATA] +
    # Only the IRQs with a real internal source: IRQ3-5/7 (on-board cards)
    # and IRQ14 (storage). IRQ9-13/15 have no possible driver -- re-add
    # alongside a second '165 if a 16-bit source ever appears. IRQ2, IRQ6 and
    # IRQ8 are RETIRED as internal nets (2026-07-14): nothing on the board can
    # drive them -- IRQ2's NIC was removed (tag full-board-with-nic; a
    # sidecar NIC would arrive as EXT_IRQ2), the floppy raises IRQ6 as a
    # firmware event (a sidecar FDC would arrive as EXT_IRQ6), and IRQ8's RTC
    # is firmware-emulated with the PCF8563 polled over I2C. Their '165 lanes
    # (U12 D0/D4/D6, U19 D6) tie LOW so the firmware bit map is unchanged.
    [pin("IRQ%d" % n, "input") for n in (3, 4, 5, 7, 14)] +
    [pin(s, _DIR[s]) for s in _CTRL] +
    # (~{WR} / IO/~{M} are not in PRIV_CPU anymore: not sensed here -- GPIO
    # budget -- writes are tracked via the gated MEMW/IOW strobes instead.)
    [pin(s, _DIR[s]) for s in mxbus.PRIV_CPU] +
    # (PRIV_COUNTER dropped from the interface: the 20-bit counter chain lives
    # on this sheet, so CNT_* never leaves it.)
    [pin("LINK_B2S", "output"), pin("LINK_S2B", "input"),
     pin("SPEED_SEL", "output"), pin("~{REFRESH}", "output"), pin("SPKR", "output")] +
    # expansion-port isolation bank (mxbus.PRIV_EXP): EXP_DDIR drives the sidecar
    # data-xcvr direction (out); the ten EXT_* are the port's inward IRQ/DRQ,
    # collected on the EXT scan chain -- NEVER merged with the internal IRQ/DRQ
    # nets in hardware (firmware ORs them into the soft-PIC / soft-8237).
    [pin("EXP_DDIR", "output")] +
    [pin(n, "input") for n in mxbus.PRIV_EXP if n != "EXP_DDIR"]
)

# RP2350B GPIO -> internal/interface net.  ~48 GPIO budget (§5.2).  The 3.3V bus
# redesign deleted every 74LVC245A: each GPIO that fed a '245's MCU-side channel
# now carries the SAME bus net that '245 channel bridged, 1:1 (no GPIO moved).
# The RP2350B GPIOs are 5V-tolerant and tri-state natively, so they sit on the
# 3.3V bus directly and flip master/slave role in firmware.
GPIO_NET = {}
for i in range(8):
    GPIO_NET[i] = "D%d" % i             # data bus, direct (was MD%d via U2)
for i in range(8):
    GPIO_NET[8 + i] = "A%d" % i         # low address A0-A7, direct (was MA%d via U3); slave I/O decode
GPIO_NET.update({
    16: "~{IOR}", 17: "~{IOW}", 18: "~{MEMR}", 19: "~{MEMW}",  # strobes direct (were M_* via U6)
    20: "BALE", 21: "AEN", 22: "SPKR",     # BALE sense + AEN drive direct (were via U5/U13); SPKR: PIT ch2 / port-61h
    23: "IOCHRDY", 24: "~{IOCHCK}",                 # direct input sense
    # GPIO25 HOLD: ***FIRMWARE MUST DRIVE HOLD INVERTED (active-low here)*** --
    # cpu_core re-buffers this net through ONE inverting U13 '04 gate to reach the
    # V20's 5V-class HOLD input at a clean full swing (Task-10 fix), so a bus-master
    # request = GPIO25 LOW.  The mxbus "HOLD" contract NAME is unchanged; only its
    # active sense flips.  See questions-bus_mcu.md + questions-cpu_core.md Q10.
    25: "HOLD", 26: "HLDA",                         # HLDA also inverted (parallel U9) -> ~{HLDA} ('244 ~OE)
    27: "INTR", 28: "~{INTA}", 29: "NMI",
    30: "IRQ_LOAD", 31: "IRQ_CLK", 32: "IRQ_SER",   # '165 scan chain
    33: "DRQ1", 34: "~{DACK1}", 35: "TC",           # on-board DMA channel; TC drive direct (was M_TC via U13)
    36: "CNT_CLK", 37: "CNT_LD0", 38: "CNT_LD1", 39: "CNT_LD2",
    40: "LINK_B2S", 41: "LINK_S2B",                 # UART link to Supervisor
    42: "SPEED_SEL", 43: "EXP_DDIR",                # SPEED_SEL out; GPIO43 freed by U2 deletion (was DATADIR) -> expansion data-xcvr dir
    44: "READY", 45: "~{CPURESET}",                 # V20 handshake (private)
    46: "~{RD}",                                    # raw V20 read-strobe sense
    47: "~{REFRESH}",     # drives bus REFRESH# (was raw ~WR; writes are tracked via
})                        # the gated MEMW/IOW it already senses on GPIO17/19)
# net -> hier-label shape, so MCU stubs carry the right cross-sheet direction
_NET_SHAPE = {"IOCHRDY": "bidirectional", "~{IOCHCK}": "input",
              "HOLD": "output", "HLDA": "input", "INTR": "output",
              "~{INTA}": "input", "NMI": "output", "READY": "output",
              "~{CPURESET}": "output", "~{RD}": "input",
              "DRQ1": "input", "~{DACK1}": "output",
              "LINK_B2S": "output", "LINK_S2B": "input",
              "SPEED_SEL": "output", "~{REFRESH}": "output", "SPKR": "output"}
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
    # Self-powered: +5V -> D1 -> module VBUS; the module's onboard ME6217 LDO makes its
    # own 3V3 (3V3_BUS), which also powers THIS card's level shifters. 3V3_BUS is a
    # sheet-local rail -- NOT tied to +3V3 or the other module's 3V3 (no paralleling).
    N(M1, "VBUS", "VBUS_MCU", length=2.54)
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

    # VBUS diode-OR: the Core2350B has NO on-module diode between its USB
    # connector and the VBUS pin (vendor schematic), so the board feeds the
    # module through D1 -- a PC plugged into the module's USB for flashing
    # powers the module but can never back-power the +5V rail, and a powered
    # board never back-drives the PC port. ME6217 LDO is fine at ~4.7 V in.
    d1 = sch.place("Device:D_Schottky", "D1", "SS34", at=(40.64, 116.84))
    sch.net(d1, "2", "+5V", kind="label", dx=0, dy=-2.54)       # 2 = anode
    sch.net(d1, "1", "VBUS_MCU", kind="label", dx=0, dy=2.54)   # 1 = cathode
    pf = sch.place("power:PWR_FLAG", "#FLG1", at=(12.7, 12.7))  # VBUS_MCU is diode-fed
    sch.net(pf, "1", "VBUS_MCU", kind="label", dx=0, dy=-2.54)

    # =================================================================
    #  (3.3V bus) NO level shifters.  The six 74LVC245A -- U2 data, U6 strobes,
    #  U3/U4/U5 address+BALE, U13 AEN/TC -- and their DIR logic are DELETED.
    #  Every MCU-side channel now sits on its bus net directly through GPIO_NET
    #  (1:1; see the map above).  D0-7=GPIO0-7, A0-7=GPIO8-15, ~{IOR/IOW/MEMR/
    #  MEMW}=GPIO16-19, BALE=GPIO20, AEN=GPIO21, TC=GPIO35.  A8-A19 are no longer
    #  sensed here (they never had a GPIO -- the old U4/U5 upper channels were
    #  unbonded sense taps).  DATADIR (ex-U2 DIR, GPIO43) is freed -> EXP_DDIR.
    #  AEN (R1) and TC (R17) get an idle-low park below so cards read them
    #  deasserted during the MCU-Hi-Z (BOOTSEL/reset) window; HLDA parks low (R18).
    # =================================================================
    #  External 20-bit loadable address counter (5x 74HCT163), §5.1
    # =================================================================
    # Counters are 74HC161 (same pinout as the '163; async ~MR tied inactive;
    # no HC/HCT163 is stocked at JLC) and run in the 3.3 V DOMAIN (VCC =
    # 3V3_BUS): every control input (CNT_CLK/CNT_LD*/CNT_RUN) is a 3.3 V MCU
    # signal, and the load DATA comes from D0-D7 directly (GPIO0-7 sit on the
    # 3.3 V data bus now; the MCU drives them during master-cycle loads).  74HC
    # at 3.3 V is fine here -- these load/count clocks are slow (Task-1 check-7's
    # fmax concern was only the 14.318 MHz cpu_core dividers).  The 3.3 V CA
    # outputs feed U14-U16 (74HC244 @ 3V3), which tri-state them onto the bus.
    # Load steered in 3 byte-lanes: CNT_LD0 -> bits 0-7, CNT_LD1 -> 8-15,
    # CNT_LD2 -> 16-19.  Carry chained TC->CET; all CP = CNT_CLK.
    cnt_cfg = [  # (ref, x, Dsrc[4], Adst[4], PE, CETin, TCout)
        ("U7",  60.96, [0, 1, 2, 3], [0, 1, 2, 3],     "CNT_LD0", "3V3_BUS", "CNT_TC0"),
        ("U8", 127.00, [4, 5, 6, 7], [4, 5, 6, 7],     "CNT_LD0", "CNT_TC0", "CNT_TC1"),
        ("U9", 193.04, [0, 1, 2, 3], [8, 9, 10, 11],   "CNT_LD1", "CNT_TC1", "CNT_TC2"),
        ("U10", 259.08, [4, 5, 6, 7], [12, 13, 14, 15], "CNT_LD1", "CNT_TC2", "CNT_TC3"),
        ("U11", 325.12, [0, 1, 2, 3], [16, 17, 18, 19], "CNT_LD2", "CNT_TC3", None),
    ]
    for ref, x, dsrc, adst, pe, cetin, tcout in cnt_cfg:
        u = sch.place("mini-xt:74HCT163", ref, "74HC161", at=(x, 271.78))
        N(u, "VCC", "3V3_BUS", length=2.54)        # 3.3 V domain (see above)
        N(u, "GND", "GND", length=2.54)
        for q in range(4):
            N(u, "D%d" % q, "D%d" % dsrc[q])      # load byte-lane from 3.3V data bus
            N(u, "Q%d" % q, "CA%d" % adst[q])     # -> U14-U16 '244s -> A0-A19
        N(u, "~{PE}", pe)                          # active-low parallel load
        N(u, "CP", "CNT_CLK")                      # advance one byte per pulse
        N(u, "CEP", "CNT_RUN")                     # held while any lane loads (U18)
        N(u, "CET", cetin)                         # cascade carry-in
        N(u, "~{MR}", "3V3_BUS")                   # async master reset unused ('161)
        if tcout:
            N(u, "TC", tcout)                      # carry to next stage
        else:
            sch.no_connect(u.pin_xy("TC"))
    sch.text("§5.1 20-bit loadable address counter: load D0-D7 (3 lanes), tick CNT_CLK",
             (60.96, 248.92))

    # Load-cascade guard: '163 load is SYNCHRONOUS, so each lane-load's CP edge
    # would also *count* the stages not being loaded (a stale stage at TC could
    # carry into a just-loaded lane).  CNT_RUN = LD0·LD1·LD2 gates every CEP:
    # during any load pulse the non-loading stages hold (load overrides CEP on
    # the loading stage, so it still loads).
    # 74HC08 in the counters' 3.3 V domain: its CNT_LD inputs are 3.3 V MCU
    # strobes and its CNT_RUN output must not exceed the HC161s' 3.3 V VCC.
    gate = sch.place("mini-xt:74HCT08", "U18", "74HC08", at=(398.78, 203.2))
    N(gate, "VCC", "3V3_BUS", length=2.54)
    N(gate, "GND", "GND", length=2.54)
    N(gate, "P1", "CNT_LD0"); N(gate, "P2", "CNT_LD1"); N(gate, "P3", "CNT_LD01")
    N(gate, "P4", "CNT_LD01"); N(gate, "P5", "CNT_LD2"); N(gate, "P6", "CNT_RUN")
    for p in ("P9", "P10", "P12", "P13"):
        N(gate, p, "GND")
    for p in ("P8", "P11"):
        sch.no_connect(gate.pin_xy(p))
    decouple("C11", (398.78, 182.88), "3V3_BUS")   # U18 (3.3 V domain)

    # Counter -> bus output-enable stage: 74HC244 x3 @ 3V3, enabled ONLY during
    # master cycles (~OE = ~HLDA).  Complements the cpu_core '573s (OE = HLDA)
    # for a contention-free address handoff.  These STAY in the 3.3V design:
    # the '163 counter has no output enable, so without them the counter would
    # fight the '573 latches on A0-A19 during CPU cycles.
    # ~{HLDA} arrives on the interface (2026-07-14): the inversion moved to
    # the parallel sheet's spare 74AHC14 Schmitt gate -- the board's only
    # spare 5V-tolerant inverter (HLDA is a raw 5V V20 output) -- deleting
    # U17, a 74LVC04A that existed for that single gate. Park-safety is
    # unchanged: R18 parks HLDA low, so ~{HLDA} idles high = '244s off.
    buf_cfg = [("U14", 281.94, [0, 1, 2, 3], [4, 5, 6, 7]),
               ("U15", 327.66, [8, 9, 10, 11], [12, 13, 14, 15]),
               ("U16", 373.38, [16, 17, 18, 19], None)]
    for ref, x, lo, hi in buf_cfg:
        u = sch.place("mini-xt:74HCT244", ref, "74HC244", at=(x, 233.68))
        N(u, "VCC", "+3V3", length=2.54)
        N(u, "GND", "GND", length=2.54)
        N(u, "1OE", "~{HLDA}")
        for q, bit in enumerate(lo):
            N(u, "1A%d" % q, "CA%d" % bit)
            N(u, "1Y%d" % q, "A%d" % bit)
        if hi:
            N(u, "2OE", "~{HLDA}")
            for q, bit in enumerate(hi):
                N(u, "2A%d" % q, "CA%d" % bit)
                N(u, "2Y%d" % q, "A%d" % bit)
        else:                                  # U16 upper half unused
            N(u, "2OE", "+3V3")                # disabled
            for q in range(4):
                N(u, "2A%d" % q, "GND")        # don't float CMOS inputs
                sch.no_connect(u.pin_xy("2Y%d" % q))
    sch.text("counter->bus OE stage: '244 ~OE = ~HLDA (master only); '573s release via OE = HLDA",
             (236.22, 213.36))

    # =================================================================
    #  IRQ + EXT scan chain -- 3x 74HC165 PISO @ 3V3, §5.2.  Serial cascade,
    #  all sharing IRQ_LOAD/IRQ_CLK and costing just the 3 MCU pins
    #  (IRQ_LOAD/IRQ_CLK/IRQ_SER):
    #
    #    MCU(IRQ_SER) <- U12.Q7  U12.DS <- U19.Q7  U19.DS <- U20.Q7  U20.DS=GND
    #
    #  CHAIN ORDER (each '165 shifts D7 first): firmware clocks 24 bits --
    #    U12 (internal: IRQ3-5/7 + IRQ14; D0/D4/D6 = retired IRQ2/IRQ6/IRQ8, tied low),
    #    then U19 (expansion port EXT_IRQ2-7; D6 = retired EXT_IRQ8, tied low),
    #    then U20 (expansion port EXT_DRQ1-3).
    #  U20 is FURTHEST from the MCU (DS=GND, end of chain).  The EXT_* are the
    #  sidecar's ISOLATED lines -- collected here, ORed into the soft-PIC /
    #  soft-8237 in firmware, never wired onto the internal IRQ/DRQ nets.
    # =================================================================
    U12 = sch.place("mini-xt:74HCT165", "U12", "74HC165", at=(200.66, 233.68))
    N(U12, "VCC", "+3V3", length=2.54)
    N(U12, "GND", "GND", length=2.54)
    for i, net in enumerate(["GND",          # D0: was IRQ2 -- retired (NIC removed)
                             "IRQ3", "IRQ4", "IRQ5",
                             "GND",          # D4: was IRQ6 -- retired (fw event)
                             "IRQ7",
                             "GND"]):        # D6: was IRQ8 -- retired (fw RTC)
        N(U12, "D%d" % i, net)
    N(U12, "D7", "IRQ14")                           # storage strap (AT primary IDE)
    N(U12, "~{PL}", "IRQ_LOAD")                     # parallel load strobe
    N(U12, "CP", "IRQ_CLK")                         # shift clock
    N(U12, "~{CE}", "GND")                          # clock enable (active low)
    N(U12, "DS", "IRQ_CHAIN1")                      # <- U19.Q7 (EXT chain)
    N(U12, "Q7", "IRQ_SER")                         # serial out to MCU
    sch.no_connect(U12.pin_xy("~{Q7}"))

    def ext165(ref, at, ds_net, q7_net, dpins):
        u = sch.place("mini-xt:74HCT165", ref, "74HC165", at=at)
        N(u, "VCC", "+3V3", length=2.54)
        N(u, "GND", "GND", length=2.54)
        N(u, "~{PL}", "IRQ_LOAD")
        N(u, "CP", "IRQ_CLK")
        N(u, "~{CE}", "GND")
        N(u, "DS", ds_net)
        N(u, "Q7", q7_net)
        sch.no_connect(u.pin_xy("~{Q7}"))
        for i in range(8):
            N(u, "D%d" % i, dpins[i] if dpins[i] else "GND")  # unused inputs tied low
        return u
    # U19: expansion IRQs (EXT_IRQ2..EXT_IRQ7 on D0-D5; D6 = retired
    # EXT_IRQ8 lane and D7 both grounded -- bit map unchanged)
    ext165("U19", (60.96, 304.8), "IRQ_CHAIN2", "IRQ_CHAIN1",
           ["EXT_IRQ%d" % n for n in range(2, 8)] + [None, None])
    # U20: expansion DRQs (EXT_DRQ1-3 on D0-D2; D3-D7 grounded); DS=GND = chain end
    ext165("U20", (152.4, 304.8), "GND", "IRQ_CHAIN2",
           ["EXT_DRQ1", "EXT_DRQ2", "EXT_DRQ3", None, None, None, None, None])
    sch.text("§5.2 IRQ+EXT scan: 3x 74HC165 -> 3 MCU pins; order U12(IRQ)->U19(EXT_IRQ)->U20(EXT_DRQ)",
             (180.34, 210.82))
    decouple("C18", (35.56, 304.8), "+3V3")        # U19 (EXT '165)
    decouple("C19", (190.5, 304.8), "+3V3")        # U20 (EXT '165)

    # ---- bus-line idle pulls: wire-OR / releasable lines need defined levels.
    # 2026-07-14 consolidation: 4x10k isolated arrays (basic part) replace 31
    # discrete pulls -- elements are isolated, so packs mix rails freely.
    # Semantics unchanged per net:
    #  * IRQ3-5/7/14, DRQ1-3, TC idle LOW (released/active-high lines; no
    #    floating '165 inputs; DRQ2/3 + DACK2/3 declared-undriven, GPIO budget)
    #  * IOCHRDY/~{IOCHCK} wire-OR/open-collector: idle HIGH
    #  * MCU-Hi-Z parking (BOOTSEL/reset window): AEN low (cards see I/O
    #    decode deasserted), HLDA low ('244s off), ~{CPURESET} low (V20 held
    #    in reset until firmware runs), ~{DACK1}/~{REFRESH} to 3V3_BUS
    #    (deasserted; nets sit on RP2350B pins)
    #  * EXT_* idle low so the EXT '165s (U19/U20) never float
    mxbus.r_pack4(sch, "RN1", "10kx4", (86.36, 25.4),
                  [("IRQ3", "GND"), ("IRQ4", "GND"), ("IRQ5", "GND")])
    mxbus.r_pack4(sch, "RN2", "10kx4", (109.22, 25.4),
                  [("IRQ7", "GND"), ("IRQ14", "GND"),
                   ("DRQ1", "GND"), ("DRQ2", "GND")])
    mxbus.r_pack4(sch, "RN3", "10kx4", (132.08, 25.4),
                  [("DRQ3", "GND"), ("TC", "GND"),
                   ("AEN", "GND"), ("HLDA", "GND")])
    mxbus.r_pack4(sch, "RN4", "10kx4", (154.94, 25.4),
                  [("~{CPURESET}", "GND"), ("EXT_DRQ1", "GND"),
                   ("EXT_DRQ2", "GND"), ("EXT_DRQ3", "GND")])
    mxbus.r_pack4(sch, "RN5", "10kx4", (177.8, 25.4),
                  [("EXT_IRQ2", "GND"), ("EXT_IRQ3", "GND"),
                   ("EXT_IRQ4", "GND"), ("EXT_IRQ5", "GND")])
    mxbus.r_pack4(sch, "RN6", "10kx4", (200.66, 25.4),
                  [("EXT_IRQ6", "GND"), ("EXT_IRQ7", "GND"),
                   ("IOCHRDY", "+3V3"), ("~{IOCHCK}", "+3V3")])
    mxbus.r_pack4(sch, "RN7", "10kx4", (223.52, 25.4),
                  [("~{DACK2}", "+3V3"), ("~{DACK3}", "+3V3"),
                   ("~{DACK1}", "3V3_BUS"), ("~{REFRESH}", "3V3_BUS")])
    sch.text("DMA ch2/3 + raw ~WR/IO-M are NOT wired to the MCU (48-GPIO budget, "
             "S5.2): DACK2/3 parked high, DRQ2/3 low. First candidates for a "
             "second '165/'595 if sidecar DMA is ever needed.", (86.36, 15.24))

    sch.text("3.3V bus: data/addr/strobe/BALE/AEN/TC wired GPIO<->bus directly (no '245s);",
             (200.66, 116.84))
    sch.text("master/slave role = firmware tri-state.  RN3/RN4 idle AEN/TC/HLDA during MCU Hi-Z.",
             (200.66, 119.38))

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
    # (C6/C7/C8 removed with the data/addr/AEN '245s they decoupled.)
    decouple("C9", (50.8, 220.98), "3V3_BUS")      # counters (3.3 V domain)
    decouple("C10", (190.5, 198.12), "+3V3")       # U12 '165
    decouple("C12", (281.94, 213.36), "+3V3")      # U14 '244
    decouple("C13", (327.66, 213.36), "+3V3")      # U15 '244
    decouple("C14", (373.38, 213.36), "+3V3")      # U16 '244
    decouple("C16", (35.56, 220.98), "3V3_BUS")    # counter bank
    decouple("C17", (20.32, 220.98), "3V3_BUS")    # 3V3_BUS bulk

"""Real-time clock -- DS12C887 @ 0x70/0x71  (design doc S11.3, I/O map S14).

AT-style battery-backed RTC + CMOS RAM. The DS12C887 has an integral crystal
and lithium cell, so no external coin cell or crystal is needed.

The chip uses a MULTIPLEXED address/data bus (AD0-7) with an address strobe
(AS/ALE), but the buffered XT/ISA backplane is DE-multiplexed (separate A and D)
and the RTC is addressed as two I/O ports: 0x70 (index) and 0x71 (data). This
sheet adds the small glue to bridge the two:

  * MOT strapped to GND -> Intel bus mode (DS = ~{RD}, R/~{W} = ~{WR}, AS = ALE).
  * AD0-7 wired straight to the data bus D0-7 (the chip is the only driver on
    its AD pins).
  * 74HCT138 + 74HCT02/74HCT08 decode ~{CS} for exactly 0x70/0x71 from A1-A9 + AEN.
  * Strobes synthesised from the I/O cycle using A0 to pick index vs data:
      AS     = (~{IOW} low) AND (A0=0) AND selected   -- latches index on 0x70 write
      DS     = ~{IOR} OR ~A0                           -- read enable, 0x71 only
      R/~{W} = ~{IOW} OR ~A0                           -- write enable, 0x71 only
  * ~{IRQ} (active-low, open-drain) -> pull-up + invert -> active-high IRQ8.
  * ~{RESET} driven from bus RESET_DRV (inverted).

Soft card: ISA signals + power only.  See hardware/notes/questions-rtc.md.
"""
import mxbus
from mxbus import pin

NAME = "rtc"
TITLE = "Real-time clock -- DS12C887 @ 0x70/0x71"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR[:10]] +          # A0..A9 (decode)
    [pin(s) for s in mxbus.DATA] +                        # D0..D7 (mux'd AD bus)
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "AEN", "RESET_DRV"]] +
    [pin("IRQ8", "output")]
)


def build(sch, lib, expose=True):
    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # ---------------- DS12C887 RTC ----------------
    U1 = sch.place("mini-xt:DS12C887", "U1", at=(228.6, 116.84))
    L(U1, "VCC", "+5V", dx=0, dy=-2.54)
    L(U1, "GND", "GND", dx=0, dy=2.54)
    # multiplexed AD0-7 straight onto the data bus
    for i in range(8):
        L(U1, "AD%d" % i, "D%d" % i, dx=2.54)
    # synthesised Intel-mode strobes / chip select
    L(U1, "AS", "RTC_AS", dx=-2.54)
    L(U1, "DS", "RTC_DS", dx=-2.54)
    L(U1, "R/~{W}", "RTC_RW", dx=-2.54)
    L(U1, "~{CS}", "~{RTC_SEL}", dx=-2.54)
    L(U1, "~{RESET}", "RTC_RST_L", dx=-2.54)
    L(U1, "MOT", "GND", dx=-2.54)            # Intel bus mode
    L(U1, "~{IRQ}", "RTC_IRQ_L", dx=2.54)    # open-drain, active low
    sch.no_connect(U1.pin_xy("SQW"))         # square-wave output unused

    # IRQ8: pull-up on the open-drain ~{IRQ}, then invert to active-high IRQ8
    R1 = sch.place("Device:R", "R1", "10k", at=(254, 88.9))
    sch.net(R1, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(R1, "2", "RTC_IRQ_L", kind="label", dx=0, dy=2.54)

    # ---------------- address decode: 74HCT138 (0x70/0x71) ----------------
    # A6:A4 -> Y7 (=111); enabled only when A1=A2=A3=A7=A8=A9=0 and AEN=0.
    U2 = sch.place("mini-xt:74HCT138", "U2", at=(88.9, 81.28))
    L(U2, "VCC", "+5V", dx=0, dy=-2.54)
    L(U2, "GND", "GND", dx=0, dy=2.54)
    L(U2, "A0", "A4", dx=-2.54)
    L(U2, "A1", "A5", dx=-2.54)
    L(U2, "A2", "A6", dx=-2.54)
    L(U2, "~{E0}", "AEN", dx=-2.54)          # enable when AEN low
    L(U2, "~{E1}", "GND", dx=-2.54)          # tied active
    L(U2, "E2", "ADDR_ZERO", dx=-2.54)       # high when upper bits all zero
    L(U2, "~{Y7}", "~{RTC_SEL}", dx=2.54)    # 0x70/0x71 select (active low)

    # ---------------- "upper address all zero" detector ----------------
    # need A1=A2=A3=A7=A8=A9=0.  NOR pairs -> high when both 0; AND them.
    # 74HC grade (no HCT02 at JLC): safe here because every input is a bus
    # address line, which is always 5 V-driven (the '573 latches or the
    # Bus MCU's '244 counter buffers) -- never a 3.3 V level.
    U3 = sch.place("mini-xt:74HCT02", "U3", "74HC02", at=(88.9, 215.9))   # NOR x4
    L(U3, "VCC", "+5V", dx=0, dy=-2.54)
    L(U3, "GND", "GND", dx=0, dy=2.54)
    L(U3, "P2", "A1", dx=-2.54); L(U3, "P3", "A2", dx=-2.54)
    L(U3, "P1", "ZN1", dx=2.54)                                # NOR(A1,A2)
    L(U3, "P5", "A3", dx=-2.54); L(U3, "P6", "A7", dx=-2.54)
    L(U3, "P4", "ZN2", dx=2.54)                                # NOR(A3,A7)
    L(U3, "P8", "A8", dx=-2.54); L(U3, "P9", "A9", dx=-2.54)
    L(U3, "P10", "ZN3", dx=2.54)                               # NOR(A8,A9)

    # ---------------- AND glue: 74HCT08 ----------------
    # gate A,B: AND the three NOR outputs -> ADDR_ZERO
    # gate C,D: AS = nIOW AND nA0 AND selected
    U4 = sch.place("mini-xt:74HCT08", "U4", at=(152.4, 215.9))  # AND x4
    L(U4, "VCC", "+5V", dx=0, dy=-2.54)
    L(U4, "GND", "GND", dx=0, dy=2.54)
    L(U4, "P1", "ZN1", dx=-2.54); L(U4, "P2", "ZN2", dx=-2.54)
    L(U4, "P3", "ZN12", dx=2.54)                               # ZN1 & ZN2
    L(U4, "P4", "ZN12", dx=-2.54); L(U4, "P5", "ZN3", dx=-2.54)
    L(U4, "P6", "ADDR_ZERO", dx=2.54)                          # & ZN3 -> all zero
    L(U4, "P9", "NIOW", dx=-2.54); L(U4, "P10", "NA0", dx=-2.54)
    L(U4, "P8", "AS0", dx=2.54)                                # nIOW & nA0
    L(U4, "P12", "AS0", dx=-2.54); L(U4, "P13", "NRTCSEL", dx=-2.54)
    L(U4, "P11", "RTC_AS", dx=2.54)                            # & selected -> AS
    # TIMING (bench-verify): AS falls ~3 gate delays (inverter + two ANDs)
    # AFTER ~IOW rises, so the index byte must persist on D0-D7 through that
    # skew plus the DS12C887's address-hold time. Tightest margin on this
    # sheet; classic technique, expected fine at 7.16 MHz -- measure it.
    sch.text("AS hold path: ~IOW -> inv -> 2x AND -> AS. Verify index-byte hold "
             "vs DS12C887 tAHL on the bench.", (139.7, 236.22))

    # ---------------- OR glue: 74HCT32 (port-0x71 data strobes) ----------------
    U5 = sch.place("mini-xt:74HCT32", "U5", at=(152.4, 160.02))  # OR x4
    L(U5, "VCC", "+5V", dx=0, dy=-2.54)
    L(U5, "GND", "GND", dx=0, dy=2.54)
    L(U5, "P1", "~{IOR}", dx=-2.54); L(U5, "P2", "NA0", dx=-2.54)
    L(U5, "P3", "RTC_DS", dx=2.54)                             # ~{IOR} | nA0 (A0=1)
    L(U5, "P4", "~{IOW}", dx=-2.54); L(U5, "P5", "NA0", dx=-2.54)
    L(U5, "P6", "RTC_RW", dx=2.54)                             # ~{IOW} | nA0 (A0=1)

    # ---------------- inverters: 74HCT04 ----------------
    # NA0 = ~A0 ; NIOW = ~(~{IOW}) ; NRTCSEL = ~(~{RTC_SEL}) ;
    # RTC_RST_L = ~RESET_DRV ; IRQ8 = ~(~{IRQ})
    U6 = sch.place("mini-xt:74HCT04", "U6", at=(88.9, 160.02))  # inverter x6
    L(U6, "VCC", "+5V", dx=0, dy=-2.54)
    L(U6, "GND", "GND", dx=0, dy=2.54)
    L(U6, "P1", "A0", dx=-2.54);          L(U6, "P2", "NA0", dx=2.54)
    L(U6, "P3", "~{IOW}", dx=-2.54);      L(U6, "P4", "NIOW", dx=2.54)
    L(U6, "P5", "~{RTC_SEL}", dx=-2.54);  L(U6, "P6", "NRTCSEL", dx=2.54)
    L(U6, "P9", "RESET_DRV", dx=-2.54);   L(U6, "P8", "RTC_RST_L", dx=2.54)
    L(U6, "P11", "RTC_IRQ_L", dx=-2.54);  L(U6, "P10", "IRQ8", dx=2.54)
    sch.no_connect(U6.pin_xy("P13"))      # spare inverter
    sch.no_connect(U6.pin_xy("P12"))

    # spare NOR gate (U3 gate D) unused
    sch.no_connect(U3.pin_xy("P13"))

    # ---------------- decoupling ----------------
    decouple("C1", (228.6, 175.26))
    decouple("C2", (152.4, 96.52))

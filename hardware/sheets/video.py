"""video -- Video card MCU (RP2350B): soft CGA/MDA/Hercules, VGA + HDMI out.

Design doc S8 (and the video parts of S4.1/S7). A soft card: it talks the
standard ISA backplane + power plus ONE central level, DIS_VID (mxbus.PRIV_DIS
-- a standalone card's wrapper would put the strap back locally). It owns its
own video RAM and SELF-DECODES the 0xA0000-0xBFFFF window and the CRTC/mode
ports from the latched A17-A19 / A0-A9 it snoops (no Y5, no MCU link, no host
memory). DIS_VID (GPIO42, addr_decode JP6 -- 2026-07-14: replaced the on-sheet
VID_EN/JP1 strap, POLARITY INVERTED: high = disabled, enabled by default) and
VID_BASE (GPIO43, JP1 here) are boot-read straps: firmware honors DIS_VID
before enabling any bus-facing OE, and VID_BASE selects the default window
(CGA or MDA), letting an on-board video coexist with a card_video on the
sidecar chain.

Structure:
  * Core2350B module (M1, RP2350B) -- self-powers 3V3 from +5V (onboard LDO);
    D1 (SS34 Schottky) is the VBUS diode-OR so module-USB flashing never
    back-powers the +5V rail.
  * 3.3V bus redesign (2026-07-14): the ISA bus itself is now 3.3V-native, so
    the 74LVC245A block that used to bridge 3.3V MCU <-> 5V bus split into two
    fates (see questions-video.md #10):
      KEPT -- U2 data transceiver D0-D7 (bidirectional, DIR=DDIR, OE=DOE),
      U3/U4/U5 address snoop A0-A7/A8-A15/A16-A19 (B->A, OE=AOE_LO/MID/HI).
      These four time-share one 8-bit MCU "snoop bus" SB0-SB7 (GPIO0-7) via
      PIO-controlled output-enables -- a GPIO-BUDGET multiplexer (questions-
      video.md #2), not a voltage bridge: direct-wiring A0-19+D0-7 would need
      28 dedicated GPIO instead of 8, and this part is already at 47/48 GPIO.
      Kept as-is, still 3.3V-3.3V on 3V3_VID.
      DELETED -- U6 control snoop MEMR/MEMW/IOR/IOW/BALE/AEN/CLK/RESET_DRV
      (B->A, always enabled, fixed direction: no mux to preserve) and U7
      IOCHRDY driver (one channel, A->B, OE=RDY_OE: the RP2350B GPIO
      tri-states natively, so the dedicated OE-controlled buffer added
      nothing once the bus stopped needing a voltage bridge). Both
      direct-connected 1:1 instead.
    R32-R36 still park U2-U5's control nets while the MCU is Hi-Z (BOOTSEL
    flashing / reset-to-init); R37 (the old RDY_OE park) is gone with U7 --
    IOCHRDY floating during Hi-Z is caught by the shared bus pull-up on the
    Bus MCU sheet (R2, idle-high), same as every other soft card.
  * HDMI (J1): RP2350 HSTX drives the 3 TMDS data pairs + clock pair straight out
    of GPIO12-19 through 270R series resistors -- no transmitter chip.
  * VGA  (J2): resistor-ladder DAC, 3R-3G-2B, from GPIO to an HD15 connector,
    plus HSYNC/VSYNC.
  * VGA-aperture PSRAM is the module's onboard QSPI PSRAM (CS=GPIO47).

HDMI/VGA are LOCAL outputs to connectors -- not hierarchical interface pins.
"""
import mxbus
from mxbus import pin

NAME = "video"
TITLE = "Video card MCU (RP2350B) -- soft CGA/MDA/Herc, VGA + HDMI out"

PINS = (
    [pin(s, "input") for s in mxbus.ADDR] +                  # A0..A19 snooped
    [pin(s) for s in mxbus.DATA] +                           # D0..D7 bidir
    [pin(s, "input") for s in ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}",
                               "BALE", "AEN", "CLK", "RESET_DRV"]] +
    [pin("IOCHRDY", "output"),                               # card wait-states reads
     pin("DIS_VID", "input")]   # addr_decode JP6 level: high = card disabled (fw-read)
)


def build(sch, lib, expose=True):
    if expose:        # standalone dev-card PCBs tie to on-card headers, not a parent
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, net="3V3_VID"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", net, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # ================= Core2350B module (RP2350B) =================
    # Order the PSRAM variant (2/8MB): the module's onboard QSPI PSRAM IS the VGA
    # aperture (CS=GPIO47, internal to the module) -- no external PSRAM chip needed.
    M1 = sch.place("mini-xt:Core2350B", "M1", "Core2350B (8MB PSRAM)", at=(165.1, 139.7))
    # self-powered: +5V -> D1 -> VBUS; onboard LDO makes 3V3_VID (local rail) for the
    # shifters. 3V3_VID is sheet-local -- not tied to +3V3 or the Bus MCU's 3V3.
    # D1 (SS34 Schottky) is the VBUS diode-OR: modules have no internal VBUS protection,
    # so D1 prevents module-USB flashing from back-powering the +5V rail.
    L(M1, "VBUS", "VBUS_VID", dx=0, dy=-2.54)
    L(M1, "3V3", "3V3_VID", dx=0, dy=-2.54)
    L(M1, "59", "GND", dx=0, dy=2.54); L(M1, "60", "GND", dx=0, dy=2.54)
    for nm in ("3V3_EN", "RUN", "ADC_VREF", "USB_DP", "USB_DM", "BOOTSEL",
               "SWCLK", "SWDIO"):
        sch.no_connect(M1.pin_xy(nm))

    # ---- snoop bus + bus interface GPIO ----
    for i in range(8):
        L(M1, "GPIO%d" % i, "SB%d" % i, dx=-2.54)            # GPIO0-7 snoop bus
    L(M1, "GPIO8", "~{MEMR}", dx=-2.54); L(M1, "GPIO9", "~{MEMW}", dx=-2.54)
    L(M1, "GPIO10", "~{IOR}", dx=-2.54); L(M1, "GPIO11", "~{IOW}", dx=-2.54)
    # HDMI HSTX TMDS pairs on GPIO12-19 (RP2350 HSTX block)
    for g, net in [(12, "TMDS_D0M"), (13, "TMDS_D0P"), (14, "TMDS_CKM"),
                   (15, "TMDS_CKP"), (16, "TMDS_D1M"), (17, "TMDS_D1P"),
                   (18, "TMDS_D2M"), (19, "TMDS_D2P")]:
        L(M1, "GPIO%d" % g, net, dx=2.54)
    L(M1, "GPIO20", "BALE", dx=-2.54); L(M1, "GPIO21", "AEN", dx=-2.54)
    L(M1, "GPIO22", "AOE_LO", dx=-2.54); L(M1, "GPIO23", "AOE_MID", dx=-2.54)
    L(M1, "GPIO24", "AOE_HI", dx=-2.54); L(M1, "GPIO25", "DOE", dx=-2.54)
    L(M1, "GPIO26", "DDIR", dx=-2.54)
    L(M1, "GPIO27", "IOCHRDY", dx=-2.54)  # direct (was IOCHRDY_DRV via U7); GPIO tri-states natively when not waiting
    # VGA DAC drive on GPIO28-37
    for g, net in [(28, "VR0"), (29, "VR1"), (30, "VR2"),
                   (31, "VG0"), (32, "VG1"), (33, "VG2"),
                   (34, "VB0"), (35, "VB1"), (36, "HSYNC"), (37, "VSYNC")]:
        L(M1, "GPIO%d" % g, net, dx=2.54)
    L(M1, "GPIO38", "CLK", dx=2.54)
    L(M1, "GPIO39", "RESET_DRV", dx=2.54)            # module user LED on GPIO39 (still usable)
    sch.no_connect(M1.pin_xy("GPIO40"))              # freed: U7 deleted (was RDY_OE); IOCHRDY (GPIO27) tri-states natively
    L(M1, "GPIO41", "HDMI_HPD", dx=2.54)      # 5V-level from sink; RP2350 IO is 5V-tolerant
    L(M1, "GPIO42", "DIS_VID", dx=2.54)       # central boot strap: HIGH = disabled
    L(M1, "GPIO43", "VID_BASE", dx=2.54)      # boot strap: low = CGA, high = MDA
    # GPIO44-46 unused; GPIO47 = module's onboard PSRAM chip-select (internal).
    for g in (44, 45, 46, 47):
        sch.no_connect(M1.pin_xy("GPIO%d" % g))

    # VBUS diode-OR: the Core2350B has NO on-module diode between its USB
    # connector and the VBUS pin (vendor schematic) -- D1 feeds the module
    # Pico-style so a PC plugged in for flashing powers the module but never
    # back-powers the +5V rail, and a powered board never back-drives the PC.
    d1 = sch.place("Device:D_Schottky", "D1", "SS34", at=(152.4, 40.64))
    sch.net(d1, "2", "+5V", kind="label", dx=0, dy=-2.54)       # 2 = anode
    sch.net(d1, "1", "VBUS_VID", kind="label", dx=0, dy=2.54)   # 1 = cathode
    # ERC power markers: VBUS_VID is diode-fed, HDMI_5V polyfuse-fed
    for i, net in ((1, "VBUS_VID"), (2, "HDMI_5V")):
        pf = sch.place("power:PWR_FLAG", "#FLG%d" % i, at=(12.7 + (i - 1) * 15.24, 12.7))
        sch.net(pf, "1", net, kind="label", dx=0, dy=-2.54)

    # local 3V3_VID decoupling for the shifters (module itself is self-decoupled)
    decouple("C1", (44.45, 274.32), net="3V3_VID")
    decouple("C2", (69.85, 274.32), net="3V3_VID")
    bulk = sch.place("Device:C", "C3", "10uF", at=(95.25, 274.32))
    sch.net(bulk, "1", "3V3_VID", kind="label", dx=0, dy=-2.54)
    sch.net(bulk, "2", "GND", kind="label", dx=0, dy=2.54)
    # More 3V3_VID decoupling for the 6 video output shifters
    decouple("C4", (127.0, 274.32))
    decouple("C5", (152.4, 274.32))
    decouple("C6", (177.8, 274.32))
    decouple("C7", (203.2, 274.32))

    # MCU-Hi-Z parking (BOOTSEL flashing / reset-to-init window): every
    # bus-facing '245 enable defaults OFF and the data direction defaults to
    # bus->MCU sense, so an unconfigured MCU never drives the 3.3V bus. (R37,
    # the old RDY_OE park, is gone with U7 -- IOCHRDY floating during Hi-Z is
    # caught by the Bus MCU sheet's shared idle-high pull-up, R2.)
    for ref, net, rail, x in [("R32", "DDIR", "GND", 33.02),
                             ("R33", "DOE", "3V3_VID", 48.26),
                             ("R34", "AOE_LO", "3V3_VID", 63.5),
                             ("R35", "AOE_MID", "3V3_VID", 78.74),
                             ("R36", "AOE_HI", "3V3_VID", 93.98)]:
        r = sch.place("Device:R", ref, "10k", at=(x, 287.02))
        sch.net(r, "1", rail, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", net, kind="label", dx=0, dy=2.54)

    # Boot straps (firmware-read; decode is firmware in this snoop design):
    # DIS_VID comes from addr_decode JP6 (2026-07-14, was the on-sheet
    # VID_EN/JP1 -- polarity inverted): low/default -> card enabled; jumper
    # fitted -> high -> firmware keeps every bus-facing OE off (all drivers
    # are MCU-gated tri-states) = card disabled.
    # JP1 installed -> VID_BASE low -> CGA windows (0x3D4-3DF / 0xB8000);
    # open -> MDA/Hercules (0x3B4-3BF / 0xB0000) -- the snoop-firmware
    # equivalent of a base-address jumper.
    JP1 = sch.place("Connector_Generic:Conn_01x02", "JP1", "VID_BASE", at=(137.16, 40.64))
    L(JP1, "Pin_1", "VID_BASE", dx=2.54)
    L(JP1, "Pin_2", "GND", dx=2.54)
    r = sch.place("Device:R", "R31", "10k", at=(137.16, 60.96))
    sch.net(r, "1", "3V3_VID", kind="label", dx=0, dy=-2.54)
    sch.net(r, "2", "VID_BASE", kind="label", dx=0, dy=2.54)

    # ============= kept 74LVC245A: GPIO-budget snoop-bus mux =============
    # (U6 control-snoop and U7 IOCHRDY-driver deleted below -- direct-connected.)
    def shifter(ref, at):
        u = sch.place("mini-xt:74LVC245A", ref, "74LVC245A", at=at)
        L(u, "VCC", "3V3_VID", dx=0, dy=-2.54)
        L(u, "GND", "GND", dx=0, dy=2.54)
        return u

    # U2: data transceiver (bidirectional)  A=snoop bus, B=ISA D0-D7
    U2 = shifter("U2", (63.5, 50.8))
    L(U2, "A->B", "DDIR"); L(U2, "CE", "DOE")
    for i in range(8):
        L(U2, "A%d" % i, "SB%d" % i, dx=-2.54)
        L(U2, "B%d" % i, "D%d" % i)

    # U3/U4/U5: address snoop (DIR low = B->A, bus -> MCU)
    U3 = shifter("U3", (63.5, 99.06))
    L(U3, "A->B", "GND"); L(U3, "CE", "AOE_LO")
    for i in range(8):
        L(U3, "A%d" % i, "SB%d" % i, dx=-2.54)
        L(U3, "B%d" % i, "A%d" % i)
    U4 = shifter("U4", (63.5, 147.32))
    L(U4, "A->B", "GND"); L(U4, "CE", "AOE_MID")
    for i in range(8):
        L(U4, "A%d" % i, "SB%d" % i, dx=-2.54)
        L(U4, "B%d" % i, "A%d" % (8 + i))
    U5 = shifter("U5", (63.5, 195.58))
    L(U5, "A->B", "GND"); L(U5, "CE", "AOE_HI")
    for i in range(4):
        L(U5, "A%d" % i, "SB%d" % i, dx=-2.54)
        L(U5, "B%d" % i, "A%d" % (16 + i))
    for i in range(4, 8):                                    # unused channels
        sch.no_connect(U5.pin_xy("A%d" % i))
        sch.no_connect(U5.pin_xy("B%d" % i))

    # U6 (control snoop) and U7 (IOCHRDY driver) DELETED: both were pure
    # buffers (fixed direction, no muxing) with nothing left to do once the
    # bus is 3.3V-native -- GPIO8-11/20/21/38/39/27 now sit on
    # ~{MEMR}/~{MEMW}/~{IOR}/~{IOW}/BALE/AEN/CLK/RESET_DRV/IOCHRDY directly
    # (see the GPIO block above and questions-video.md #10).

    # ================= VGA aperture PSRAM =================
    # On the Core2350B module (8MB QSPI PSRAM, CS=GPIO47) -- no external part.

    # ================= HDMI out (HSTX direct TMDS) =================
    # +5V fused to protect against shorted HDMI cable
    F1 = sch.place("Device:Polyfuse", "F1", "500mA", at=(297.18, 170.18))
    L(F1, "1", "+5V", dx=0, dy=-2.54)
    L(F1, "2", "HDMI_5V", dx=0, dy=2.54)

    J1 = sch.place("Connector:HDMI_A", "J1", at=(322.58, 88.9))
    hdmi = [("TMDS_D2P", "HDMI_D2P", "D2+"), ("TMDS_D2M", "HDMI_D2M", "D2-"),
            ("TMDS_D1P", "HDMI_D1P", "D1+"), ("TMDS_D1M", "HDMI_D1M", "D1-"),
            ("TMDS_D0P", "HDMI_D0P", "D0+"), ("TMDS_D0M", "HDMI_D0M", "D0-"),
            ("TMDS_CKP", "HDMI_CKP", "CK+"), ("TMDS_CKM", "HDMI_CKM", "CK-")]
    for i, (src, conn, cpin) in enumerate(hdmi):
        r = sch.place("Device:R", "R%d" % (10 + i), "270", at=(289.56, 45.72 + i * 15.24))
        sch.net(r, "1", src, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", conn, kind="label", dx=0, dy=2.54)
        L(J1, cpin, conn, dx=2.54)
    for cpin in ("D2S", "D1S", "D0S", "CKS", "GND", "SH"):
        L(J1, cpin, "GND", dx=2.54)
    L(J1, "+5V", "HDMI_5V", dx=2.54)
    L(J1, "HPD", "HDMI_HPD", dx=2.54)      # 5V-level from sink; RP2350 IO is 5V-tolerant
    for cpin in ("CEC", "UTILITY", "SCL", "SDA"):
        sch.no_connect(J1.pin_xy(cpin))

    # ================= VGA out (resistor-ladder DAC) =================
    # 3-bit R, 3-bit G, 2-bit B weighted ladders summing per colour.
    # Blue is 820/470 (not 1k/510): matches the R/G full-scale into 75R --
    # 470||820 = 299R vs 2k||1k||510 = 289R (~0.66V vs ~0.68V FS); the old
    # 1k/510 pair was ~12% blue-deficient.  Ratio 1.74 vs ideal 2 is fine
    # for 2 bits (monotonic; both values are JLC basic parts).
    vga_dac = [("VR0", "VGA_R", "2k"), ("VR1", "VGA_R", "1k"), ("VR2", "VGA_R", "510"),
               ("VG0", "VGA_G", "2k"), ("VG1", "VGA_G", "1k"), ("VG2", "VGA_G", "510"),
               ("VB0", "VGA_B", "820"), ("VB1", "VGA_B", "470")]
    for i, (src, out, val) in enumerate(vga_dac):
        r = sch.place("Device:R", "R%d" % (20 + i), val, at=(266.7, 165.1 + i * 15.24))
        sch.net(r, "1", src, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", out, kind="label", dx=0, dy=2.54)

    # VGA sync series resistors (protect RP2350 from monitor-side faults)
    r = sch.place("Device:R", "R28", "100", at=(266.7, 287.02))
    sch.net(r, "1", "HSYNC", kind="label", dx=0, dy=-2.54)
    sch.net(r, "2", "HSYNC_J", kind="label", dx=0, dy=2.54)
    r = sch.place("Device:R", "R29", "100", at=(281.94, 287.02))
    sch.net(r, "1", "VSYNC", kind="label", dx=0, dy=-2.54)
    sch.net(r, "2", "VSYNC_J", kind="label", dx=0, dy=2.54)

    J2 = sch.place("Connector_Generic:Conn_01x15", "J2", "VGA HD15", at=(322.58, 215.9))
    L(J2, "Pin_1", "VGA_R", dx=2.54)
    L(J2, "Pin_2", "VGA_G", dx=2.54)
    L(J2, "Pin_3", "VGA_B", dx=2.54)
    L(J2, "Pin_13", "HSYNC_J", dx=2.54)
    L(J2, "Pin_14", "VSYNC_J", dx=2.54)
    for p in ("Pin_5", "Pin_6", "Pin_7", "Pin_8", "Pin_10"):
        L(J2, p, "GND", dx=2.54)
    for p in ("Pin_4", "Pin_9", "Pin_11", "Pin_12", "Pin_15"):
        sch.no_connect(J2.pin_xy(p))

    sch.text("SOFT CARD: ISA bus + power ONLY. Self-decodes 0xA0000-0xBFFFF and "
             "3B4/3B5/3B8/3BA/3BF + 3D4/3D5/3D8/3D9/3DA from snooped A17-A19/A0-A9. "
             "No Y5, no link, no host RAM (design S8). "
             "Disable: addr_decode JP6 (DIS_VID high, firmware keeps all OEs off; enabled by default). JP1 = CGA (closed) / MDA (open) window set.", (38.1, 20.32))
    sch.text("HDMI: +5V fused (F1); HPD sensed on GPIO41. Add TMDS ESD array (TPD4E05U06-class, <=0.15pF) at layout -- no KiCad symbol yet.", (266.7, 33.02))

"""video -- Video card MCU (RP2350B): soft CGA/MDA/Hercules, VGA + HDMI out.

Design doc S8 (and the video parts of S4.1/S7). A SOFT CARD: it talks ONLY the
standard ISA backplane + power, exactly like a period ISA video card, so it stays
liftable to a standalone ISA board unchanged. It owns its own video RAM and
SELF-DECODES the 0xA0000-0xBFFFF window and the CRTC/mode ports from the latched
A17-A19 / A0-A9 it snoops -- it uses NO private motherboard signal (no Y5, no
MCU link, no host memory).

Structure:
  * RP2350B (U1) at 3.3 V, on-chip buck core rail (VREG_LX -> L1 -> VCORE).
  * Local 74LVC245A level shifters between the 3.3 V MCU and the 5 V bus:
      U2  data transceiver  D0-D7  (bidirectional, DIR=DDIR, OE=DOE)
      U3  address snoop     A0-A7  (B->A, OE=AOE_LO)
      U4  address snoop     A8-A15 (B->A, OE=AOE_MID)
      U5  address snoop     A16-A19(B->A, OE=AOE_HI)
      U6  control snoop     MEMR/MEMW/IOR/IOW/BALE/AEN/CLK/RESET_DRV (B->A)
      U7  IOCHRDY driver    one channel, A->B, OE=RDY_OE (tri-state when idle)
    The address+data shifters share one 8-bit MCU "snoop bus" SB0-SB7; the PIO
    enables one '245 at a time (see questions-video.md #2) -- this is what fits
    the wide bus + two video stages onto 48 GPIO.
  * HDMI (J1): RP2350 HSTX drives the 3 TMDS data pairs + clock pair straight out
    of GPIO12-19 through 270R series resistors -- no transmitter chip.
  * VGA  (J2): resistor-ladder DAC, 3R-3G-2B, from GPIO to an HD15 connector,
    plus HSYNC/VSYNC.
  * Optional QSPI PSRAM (U8) for the 256 KB VGA aperture, CS on GPIO47.

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
    [pin("IOCHRDY", "output")]                               # card wait-states reads
)


def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    def decouple(ref, at, net="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", net, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    # ================= RP2350B =================
    U1 = sch.place("MCU_RaspberryPi:RP2350B", "U1", at=(165.1, 139.7))

    # ---- power rails ----
    for n in (5, 15, 24, 29, 41, 50, 60, 76):        # IOVDD
        L(U1, n, "+3V3", dx=0, dy=-2.54)
    for n in (61, 59, 64, 68, 69):                    # VREG_AVDD, ADC_AVDD, VREG_VIN, USB_OTP_VDD, QSPI_IOVDD
        L(U1, n, "+3V3", dx=0, dy=-2.54)
    for n in (62, 81):                                 # VREG_PGND, GND
        L(U1, n, "GND", dx=0, dy=2.54)
    for n in (10, 32, 51):                             # DVDD core rail
        L(U1, n, "VCORE", dx=0, dy=-2.54)
    L(U1, 63, "VREG_LX", dx=0, dy=-2.54)               # buck switch node
    L(U1, 65, "VCORE", dx=0, dy=-2.54)                 # VREG_FB sensed at core
    L1 = sch.place("Device:L", "L1", "3.3uH", at=(139.7, 96.52))
    sch.net(L1, "1", "VREG_LX", kind="label", dx=0, dy=-2.54)
    sch.net(L1, "2", "VCORE", kind="label", dx=0, dy=2.54)

    # ---- housekeeping pins ----
    L(U1, "RUN", "+3V3", dx=-2.54)                    # run whenever powered
    L(U1, "XIN", "XIN", dx=-2.54)                     # off-sheet 12 MHz crystal
    L(U1, "XOUT", "XOUT", dx=-2.54)
    L(U1, "SWCLK", "SWCLK", dx=-2.54)
    L(U1, "SWDIO", "SWDIO", dx=-2.54)
    sch.no_connect(U1.pin_xy("USB_DM"))
    sch.no_connect(U1.pin_xy("USB_DP"))

    # ---- snoop bus + bus interface GPIO ----
    for i in range(8):
        L(U1, "GPIO%d" % i, "SB%d" % i, dx=-2.54)            # GPIO0-7  snoop bus
    L(U1, "GPIO8", "MEMR_M", dx=-2.54)                       # command strobes (watched)
    L(U1, "GPIO9", "MEMW_M", dx=-2.54)
    L(U1, "GPIO10", "IOR_M", dx=-2.54)
    L(U1, "GPIO11", "IOW_M", dx=-2.54)
    # HDMI HSTX TMDS pairs on GPIO12-19
    for g, net in [(12, "TMDS_D0M"), (13, "TMDS_D0P"), (14, "TMDS_CKM"),
                   (15, "TMDS_CKP"), (16, "TMDS_D1M"), (17, "TMDS_D1P"),
                   (18, "TMDS_D2M"), (19, "TMDS_D2P")]:
        L(U1, "GPIO%d" % g, net, dx=2.54)
    L(U1, "GPIO20", "BALE_M", dx=-2.54)
    L(U1, "GPIO21", "AEN_M", dx=-2.54)
    L(U1, "GPIO22", "AOE_LO", dx=-2.54)                      # '245 output-enables
    L(U1, "GPIO23", "AOE_MID", dx=-2.54)
    L(U1, "GPIO24", "AOE_HI", dx=-2.54)
    L(U1, "GPIO25", "DOE", dx=-2.54)
    L(U1, "GPIO26", "DDIR", dx=-2.54)
    L(U1, "GPIO27", "IOCHRDY_DRV", dx=-2.54)
    # VGA DAC drive on GPIO28-37
    for g, net in [(28, "VR0"), (29, "VR1"), (30, "VR2"),
                   (31, "VG0"), (32, "VG1"), (33, "VG2"),
                   (34, "VB0"), (35, "VB1"), (36, "HSYNC"), (37, "VSYNC")]:
        L(U1, "GPIO%d" % g, net, dx=2.54)
    L(U1, "GPIO38", "CLK_M", dx=2.54)
    L(U1, "GPIO39", "RST_M", dx=2.54)
    L(U1, "GPIO40/ADC0", "RDY_OE", dx=2.54)
    L(U1, "GPIO47/ADC7", "PSRAM_CS", dx=2.54)

    # ---- QSPI to PSRAM ----
    L(U1, "QSPI_SCLK", "QSPI_SCLK", dx=2.54)
    L(U1, "QSPI_SD0", "QSPI_SD0", dx=2.54)
    L(U1, "QSPI_SD1", "QSPI_SD1", dx=2.54)
    L(U1, "QSPI_SD2", "QSPI_SD2", dx=2.54)
    L(U1, "QSPI_SD3", "QSPI_SD3", dx=2.54)
    sch.no_connect(U1.pin_xy("~{QSPI_SS}"))               # boot flash off-sheet

    # decoupling
    decouple("C1", (44.45, 274.32)); decouple("C2", (69.85, 274.32))
    decouple("C3", (95.25, 274.32)); decouple("C4", (120.65, 274.32))
    decouple("C5", (146.05, 274.32)); decouple("C6", (171.45, 274.32), net="VCORE")

    # ================= level shifters (74LVC245A) =================
    def shifter(ref, at):
        u = sch.place("mini-xt:74LVC245A", ref, "74LVC245A", at=at)
        L(u, "VCC", "+3V3", dx=0, dy=-2.54)
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

    # U6: control snoop (B->A)
    U6 = shifter("U6", (63.5, 243.84))
    L(U6, "A->B", "GND"); L(U6, "CE", "GND")                # always enabled
    ctrl = [("~{MEMR}", "MEMR_M"), ("~{MEMW}", "MEMW_M"), ("~{IOR}", "IOR_M"),
            ("~{IOW}", "IOW_M"), ("BALE", "BALE_M"), ("AEN", "AEN_M"),
            ("CLK", "CLK_M"), ("RESET_DRV", "RST_M")]
    for i, (busnet, mcunet) in enumerate(ctrl):
        L(U6, "B%d" % i, busnet)
        L(U6, "A%d" % i, mcunet, dx=-2.54)

    # U7: IOCHRDY driver (A->B), tri-stated unless the card is waiting
    U7 = shifter("U7", (109.22, 243.84))
    L(U7, "A->B", "+3V3"); L(U7, "CE", "RDY_OE")
    L(U7, "A0", "IOCHRDY_DRV", dx=-2.54)
    L(U7, "B0", "IOCHRDY")
    for i in range(1, 8):
        sch.no_connect(U7.pin_xy("A%d" % i))
        sch.no_connect(U7.pin_xy("B%d" % i))

    # ================= QSPI PSRAM (VGA aperture) =================
    U8 = sch.place("Memory_RAM:APS6404L-3SQRx-SN", "U8", "APS6404L", at=(241.3, 76.2))
    L(U8, "VDD", "+3V3", dx=0, dy=-2.54)
    L(U8, "VSS", "GND", dx=0, dy=2.54)
    L(U8, "~{CE}", "PSRAM_CS", dx=-2.54)
    L(U8, "SCLK", "QSPI_SCLK", dx=-2.54)
    L(U8, "SI/SIO0", "QSPI_SD0", dx=-2.54)
    L(U8, "SO/SIO1", "QSPI_SD1", dx=-2.54)
    L(U8, "SIO2", "QSPI_SD2")
    L(U8, "SIO3", "QSPI_SD3")

    # ================= HDMI out (HSTX direct TMDS) =================
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
    L(J1, "+5V", "+5V", dx=2.54)
    for cpin in ("CEC", "UTILITY", "SCL", "SDA", "HPD"):
        sch.no_connect(J1.pin_xy(cpin))

    # ================= VGA out (resistor-ladder DAC) =================
    # 3-bit R, 3-bit G, 2-bit B weighted ladders summing per colour.
    vga_dac = [("VR0", "VGA_R", "2k"), ("VR1", "VGA_R", "1k"), ("VR2", "VGA_R", "510"),
               ("VG0", "VGA_G", "2k"), ("VG1", "VGA_G", "1k"), ("VG2", "VGA_G", "510"),
               ("VB0", "VGA_B", "1k"), ("VB1", "VGA_B", "510")]
    for i, (src, out, val) in enumerate(vga_dac):
        r = sch.place("Device:R", "R%d" % (20 + i), val, at=(266.7, 165.1 + i * 15.24))
        sch.net(r, "1", src, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", out, kind="label", dx=0, dy=2.54)

    J2 = sch.place("Connector_Generic:Conn_01x15", "J2", "VGA HD15", at=(322.58, 215.9))
    L(J2, "Pin_1", "VGA_R", dx=2.54)
    L(J2, "Pin_2", "VGA_G", dx=2.54)
    L(J2, "Pin_3", "VGA_B", dx=2.54)
    L(J2, "Pin_13", "HSYNC", dx=2.54)
    L(J2, "Pin_14", "VSYNC", dx=2.54)
    for p in ("Pin_5", "Pin_6", "Pin_7", "Pin_8", "Pin_10"):
        L(J2, p, "GND", dx=2.54)
    for p in ("Pin_4", "Pin_9", "Pin_11", "Pin_12", "Pin_15"):
        sch.no_connect(J2.pin_xy(p))

    sch.text("SOFT CARD: ISA bus + power ONLY. Self-decodes 0xA0000-0xBFFFF and "
             "3B4/3B5/3B8/3BA/3BF + 3D4/3D5/3D8/3D9/3DA from snooped A17-A19/A0-A9. "
             "No Y5, no link, no host RAM (design S8).", (38.1, 20.32))

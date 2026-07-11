"""power -- USB-C 5 V input -> on-board 3.3 V buck (design doc S13).

Single 5 V input rail from a USB-C receptacle; the board needs only 5 V (a Type-C
sink may draw up to 3 A at 5 V with nothing but the mandatory 5.1 k Rd pulldowns
on CC1/CC2). A fixed-function PD sink controller (CH224K) is included as the
optional upgrade that *guarantees* a 5 V/3 A contract from PD-only supplies that
won't hand out 3 A on Rp alone -- see notes/questions-power.md (with the CH224K
populated the discrete 5.1 k Rd may be DNP; both are drawn so either build works).

VBUS enters through a 3A-hold 1812 polyfuse (F1) with an SMBJ5.0A TVS clamp on
the +5V rail for input protection. The CH224K local decoupling (C6) and power-good
(PG, open-drain pulled to +3V3) is routed to the Supervisor as PD_PG.

A TPS563200 synchronous buck (3 A, 0.768 V ref) steps 5 V down to +3V3 for the
four MCUs + USB logic, with its inductor, bootstrap cap, input/output caps and
feedback divider (33k/10k -> 3.30 V). PWR_FLAG markers tell ERC that +5V and +3V3
are driven sources; a GND reference symbol anchors ground.

Interface (global power nets, declared for documentation): +5V, +3V3, GND, PD_PG.
"""
import mxbus
from mxbus import pin

NAME = "power"
TITLE = "Power supply -- USB-C 5V in (CC/CH224K) -> 3.3V buck"

PINS = [pin("+5V", "output"), pin("+3V3", "output"), pin("GND", "power_in"), pin("PD_PG", "output")]


def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    def L(c, p, net, dx=2.54, dy=0.0):
        sch.net(c, p, net, kind="label", dx=dx, dy=dy)

    def flag(ref, net, at):
        f = sch.place("power:PWR_FLAG", ref, at=at)
        sch.net(f, "1", net, kind="label", dx=0, dy=-2.54)

    # ---------------- USB-C receptacle ----------------
    J1 = sch.place("Connector:USB_C_Receptacle", "J1", at=(50.8, 165.1))
    L(J1, "A4", "VBUS_IN")        # VBUS -> fuse -> +5V
    L(J1, "A1", "GND", dx=0, dy=2.54)   # GND (A1/A12/B1/B12 stacked)
    L(J1, "S1", "GND", dx=0, dy=2.54)   # shield -> GND
    L(J1, "A5", "CC1")           # CC1 -> Rd / CH224K
    L(J1, "B5", "CC2")           # CC2 -> Rd / CH224K
    L(J1, "A7", "USB_DM"); L(J1, "B7", "USB_DM")   # D- (both pads tied)
    L(J1, "A6", "USB_DP"); L(J1, "B6", "USB_DP")   # D+ (both pads tied)
    # USB 2.0 only: SuperSpeed pairs and SBU unused
    for nc in ["RX1-", "RX1+", "TX1-", "TX1+", "RX2-", "RX2+",
               "TX2-", "TX2+", "SBU1", "SBU2"]:
        sch.no_connect(J1.pin_xy(nc))

    # ---------------- mandatory 5.1 k Rd pulldowns on CC1/CC2 ----------------
    R1 = sch.place("Device:R", "R1", "5.1k", at=(88.9, 195.58))
    L(R1, "1", "CC1", dx=0, dy=-2.54); L(R1, "2", "GND", dx=0, dy=2.54)
    R2 = sch.place("Device:R", "R2", "5.1k", at=(101.6, 195.58))
    L(R2, "1", "CC2", dx=0, dy=-2.54); L(R2, "2", "GND", dx=0, dy=2.54)

    # ---------------- input protection: polyfuse + TVS clamp ----------------
    # Polyfuse limits a board fault; the SMBJ5.0A clamps the rail (~9.2 V) if a
    # confused PD source or CH224K fault ever puts >5 V on VBUS (V20/HCT/SRAM
    # abs max is ~7 V) -- the clamp current then trips the fuse.
    F1 = sch.place("Device:Polyfuse", "F1", "3A", at=(76.2, 127.0))
    L(F1, "1", "VBUS_IN", dx=0, dy=-2.54); L(F1, "2", "+5V", dx=0, dy=2.54)
    D3 = sch.place("Device:D_Zener", "D3", "SMBJ5.0A", at=(91.44, 127.0))
    L(D3, "K", "+5V", dx=0, dy=-2.54); L(D3, "A", "GND", dx=0, dy=2.54)

    # ---------------- optional PD sink controller (CH224K, ~5V/3A) ----------------
    U1 = sch.place("Interface_USB:CH224K", "U1", at=(139.7, 165.1))
    L(U1, "VBUS", "+5V", dx=0, dy=-2.54)
    L(U1, "VDD", "+5V", dx=0, dy=-2.54)
    L(U1, "GND", "GND", dx=0, dy=2.54)
    L(U1, "CC1", "CC1", dx=-2.54)
    L(U1, "CC2", "CC2", dx=-2.54)
    L(U1, "DM", "USB_DM", dx=-2.54)
    L(U1, "DP", "USB_DP", dx=-2.54)
    L(U1, "PG", "PD_PG")          # power-good (open-drain) -> Supervisor
    # CFG1 voltage select: MUST be left OPEN (internal pull-up = 5 V request).
    # Any resistor to GND here selects the 9/12/15/20 V rows -- >= 9 V on the
    # +5V rail would destroy the V20/SRAM/HCT logic. Do NOT add a strap.
    sch.no_connect(U1.pin_xy("CFG1"))
    sch.no_connect(U1.pin_xy("CFG2"))
    sch.no_connect(U1.pin_xy("CFG3"))
    sch.text("CH224K CFG1 OPEN = 5V. Never strap CFG1 low (that selects 9-20V!).",
             (129.54, 185.42))
    # PG pull-up to logic rail
    R4 = sch.place("Device:R", "R4", "10k", at=(177.8, 139.7))
    L(R4, "1", "+3V3", dx=0, dy=-2.54); L(R4, "2", "PD_PG", dx=0, dy=2.54)

    # CH224K local decoupling
    C6 = sch.place("Device:C", "C6", "1uF", at=(165.1, 190.5))
    L(C6, "1", "+5V", dx=0, dy=-2.54); L(C6, "2", "GND", dx=0, dy=2.54)   # U1 VDD decouple

    # ---------------- bulk input capacitors on +5V ----------------
    C1 = sch.place("Device:C_Polarized", "C1", "22uF", at=(203.2, 177.8))
    L(C1, "1", "+5V", dx=0, dy=-2.54); L(C1, "2", "GND", dx=0, dy=2.54)
    C2 = sch.place("Device:C", "C2", "100nF", at=(215.9, 177.8))
    L(C2, "1", "+5V", dx=0, dy=-2.54); L(C2, "2", "GND", dx=0, dy=2.54)

    # ---------------- 5V -> 3.3V buck (TPS563200, 3 A) ----------------
    U2 = sch.place("Regulator_Switching:TPS563200", "U2", at=(228.6, 152.4))
    L(U2, "VIN", "+5V", dx=-2.54)
    L(U2, "EN", "+5V", dx=-2.54)        # enable tied high (always on)
    L(U2, "GND", "GND", dx=0, dy=2.54)
    L(U2, "SW", "SW")
    L(U2, "VBST", "BOOT")
    L(U2, "VFB", "FB")
    # bootstrap cap SW -> VBST
    C5 = sch.place("Device:C", "C5", "100nF", at=(254.0, 165.1))
    L(C5, "1", "BOOT", dx=0, dy=-2.54); L(C5, "2", "SW", dx=0, dy=2.54)
    # power inductor SW -> +3V3
    L1 = sch.place("Device:L", "L1", "2.2uH", at=(266.7, 142.24))
    L(L1, "1", "SW", dx=0, dy=-2.54); L(L1, "2", "+3V3", dx=0, dy=2.54)
    # feedback divider 33k/10k -> 0.768V*(1+33/10) = 3.30 V
    R5 = sch.place("Device:R", "R5", "33k", at=(279.4, 177.8))
    L(R5, "1", "+3V3", dx=0, dy=-2.54); L(R5, "2", "FB", dx=0, dy=2.54)
    R6 = sch.place("Device:R", "R6", "10k", at=(279.4, 198.12))
    L(R6, "1", "FB", dx=0, dy=-2.54); L(R6, "2", "GND", dx=0, dy=2.54)
    # output capacitors on +3V3
    C3 = sch.place("Device:C_Polarized", "C3", "22uF", at=(292.1, 165.1))
    L(C3, "1", "+3V3", dx=0, dy=-2.54); L(C3, "2", "GND", dx=0, dy=2.54)
    C4 = sch.place("Device:C", "C4", "100nF", at=(304.8, 165.1))
    L(C4, "1", "+3V3", dx=0, dy=-2.54); L(C4, "2", "GND", dx=0, dy=2.54)

    # Buck capacitors (per TPS563200 datasheet)
    C7 = sch.place("Device:C_Polarized", "C7", "22uF", at=(317.5, 165.1))   # 2nd output cap (datasheet 2x22uF)
    L(C7, "1", "+3V3", dx=0, dy=-2.54); L(C7, "2", "GND", dx=0, dy=2.54)
    C8 = sch.place("Device:C", "C8", "10uF", at=(215.9, 127.0))             # VIN local cap
    L(C8, "1", "+5V", dx=0, dy=-2.54); L(C8, "2", "GND", dx=0, dy=2.54)
    C9 = sch.place("Device:C_Polarized", "C9", "22uF", at=(190.5, 177.8))   # extra +5V bulk
    L(C9, "1", "+5V", dx=0, dy=-2.54); L(C9, "2", "GND", dx=0, dy=2.54)

    # ---------------- rail indicator LEDs ----------------
    R7 = sch.place("Device:R", "R7", "1k", at=(101.6, 215.9))
    L(R7, "1", "+5V", dx=0, dy=-2.54); L(R7, "2", "LED5", dx=0, dy=2.54)
    D1 = sch.place("Device:LED", "D1", "5V", at=(101.6, 228.6))
    L(D1, "A", "LED5", dx=2.54); L(D1, "K", "GND", dx=-2.54)
    R8 = sch.place("Device:R", "R8", "1k", at=(304.8, 215.9))
    L(R8, "1", "+3V3", dx=0, dy=-2.54); L(R8, "2", "LED33", dx=0, dy=2.54)
    D2 = sch.place("Device:LED", "D2", "3V3", at=(304.8, 228.6))
    L(D2, "A", "LED33", dx=2.54); L(D2, "K", "GND", dx=-2.54)

    # ---------------- ERC power markers ----------------
    flag("#FLG1", "+5V", (190.5, 114.3))
    flag("#FLG2", "+3V3", (304.8, 127.0))
    flag("#FLG3", "GND", (50.8, 241.3))
    flag("#FLG4", "VBUS_IN", (76.2, 114.3))
    g = sch.power("power:GND", "#PWR01", at=(38.1, 228.6))
    sch.net(g, "1", "GND", kind="label", dx=0, dy=2.54)

    sch.text("Baseline: 5.1k Rd on CC1/CC2 (R1/R2) = 5V up to 3A from a Type-C "
             "source.", (38.1, 96.52))
    sch.text("Optional: CH224K (U1) guarantees a 5V/3A PD contract; with it "
             "populated R1/R2 may be DNP.", (38.1, 101.6))

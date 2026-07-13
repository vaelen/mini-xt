# Open questions / decisions -- video sheet

Soft CGA/MDA/Hercules card on an RP2350B. Isolation rule (design S8): ISA bus
signals + power ONLY. Self-decodes 0xA0000-0xBFFFF and the CRTC/mode ports from
latched A17-A19 / A0-A9 -- no private motherboard signal (no Y5, no link).

## 1. VGA connector symbol -- no HD15 / D-Sub-15 in the available libs
`pins.py -s DSUB / D-Sub / HD15` returned nothing; `Connector:` has only DE9/DB25.
The guide's fallback is `Connector_Generic:Conn_01x15`.
- **Decision:** use `Connector_Generic:Conn_01x15` as J2, pins mapped to the
  standard HD15 VGA pinout (1=R, 2=G, 3=B, 5/6/7/8/10=GND, 13=HSYNC, 14=VSYNC,
  others NC). A real build swaps in a proper 3-row HD15 footprint.

## 2. GPIO pin pressure -- full demuxed bus + two video outputs > 48 GPIO
Dedicating one GPIO each to A0-A19 (20) + D0-D7 (8) + 6 control + IOCHRDY would
leave too few pins for VGA (~10) + HDMI HSTX (8) on a 48-GPIO part (design S8
calls out exactly this pressure as the reason for the 48-pin RP2350B).
- **Decision (PicoGUS-style PIO snoop):** the address + data level shifters share
  a single 8-bit MCU "snoop bus" SB0-SB7 (GPIO0-7); the PIO enables one '245 at a
  time (AOE_LO/AOE_MID/AOE_HI for A0-7/A8-15/A16-19, DOE+DDIR for the data
  transceiver) and captures address vs. data in different cycle phases. The four
  command strobes + BALE/AEN/CLK/RESET_DRV stay on dedicated GPIO (they trigger
  the cycle and must be watched continuously). This collapses the bus interface to
  ~20 GPIO, freeing GPIO12-19 for the HSTX TMDS pairs and GPIO28-37 for VGA.
  Firmware detail (exact PIO timing) is out of scope for the schematic.

## 3. IOCHRDY drive -- must be tri-state (open) on ISA, not push-pull
IOCHRDY is wire-OR'd on the backplane; a card drives it only while inserting a
wait, otherwise it must release (high-Z).
- **Decision:** route IOCHRDY through its own '245 channel (U7) with DIR fixed
  A->B and the output-enable (CE) under MCU control (RDY_OE). The card enables the
  driver only to wait-state a read, then releases -- the standard behaviour.

## 4. QSPI PSRAM for the VGA aperture (design S8 "optional QSPI PSRAM")
A QSPI PSRAM exists in the libs (`Memory_RAM:APS6404L-3SQRx-SN`, the part used on
the Pi Pico 2).
- **Decision:** populate it as U8 on the RP2350 QSPI bus (SCLK/SD0-3 shared with
  the boot flash) with its chip-select on GPIO47 (the Pico-2 PSRAM-CS convention),
  giving the 256 KB linear/planar VGA aperture room.

## 5. HDMI series-resistor value + spare connector pins
Design S8: "HSTX serializing TMDS out of GPIO with series resistors (no
transmitter chip)".
- **Decision:** 270 ohm series on each of the 8 TMDS lines (3 data pairs + clock).
  Data-shield pins (D2S/D1S/D0S/CKS) and the connector shield tie to GND, +5V from
  the bus feeds the HDMI +5V pin, and CEC/UTILITY/SCL/SDA/HPD are left
  unconnected (DDC/CEC/hot-plug not used in v1).

## 6. RP2350 core regulator / crystal -- shown representatively
- VREG_LX -> L1 -> VCORE (DVDD core rail), VREG_FB sensed at VCORE; VREG_VIN and
  all IOVDD/analog rails on +3V3.
- XIN/XOUT left as labelled stubs (off-sheet 12 MHz crystal); RUN tied to +3V3
  (card runs whenever powered; could instead be gated by RESET_DRV). USB and SWD
  brought out as labels only.

## 7. Connector hardening (design review 2026-07-11)
HDMI +5V now goes through a 500mA polyfuse (F1) and HPD is sensed on GPIO41
(5V-tolerant IO, no divider). HSYNC/VSYNC get 100R series resistors (R28/R29)
before the HD15. Deferred to layout: a TMDS-rated ESD array (TPD4E05U06-class,
<=0.15pF/line) on the HDMI pairs -- no KiCad symbol available in the installed
libs, and the 270R+CML trick needs the array footprint picked with the
connector placement. VGA DAC note: 510/1k/2k weights assume the monitor's 75R
termination (~0.7V full scale).

## 8. Enable + base straps (2026-07-11)
VID_EN (GPIO42, JP1) and VID_BASE (GPIO43, JP2) are boot-read straps with 10k
pull-ups to 3V3_VID: this card self-decodes in firmware, so a hardware
chip-select gate doesn't exist to jumper -- instead firmware honors VID_EN
before enabling ANY bus-facing OE (all drivers are already MCU-gated
tri-states, so a disabled card is electrically silent), and VID_BASE picks
the default window set (closed = CGA 0x3D4/0xB8000, open = MDA 0x3B4/0xB0000)
like a period card's MDA/CGA switch. Lets an on-board video coexist with a
card_video on the sidecar chain (one CGA, one MDA, or one disabled).

## 9. Module-USB flashing made safe (2026-07-11)
Same fix as the Bus MCU: the Core2350B has no on-module VBUS diode, so D1
(SS34) now feeds the module from +5V Pico-style -- flashing over the module's
USB can't back-power the board and a running board can't back-drive the PC
port. R32-R37 park the shifter controls while the MCU is Hi-Z (BOOTSEL /
pre-init): DOE/AOE_LO/AOE_MID/AOE_HI/RDY_OE pulled to 3V3_VID (OEs are
active-low -> buffers disabled), DDIR pulled low (bus->MCU sense). Before
this, those enables floated whenever the MCU wasn't driving them.

## 10. 3.3V bus redesign (2026-07-14) -- keep/delete per shifter, not en masse
**Question:** Task 6 brief says delete "the 3x LVC245A loop (~line 165)" and
direct-connect the RP2350B GPIOs, mirroring bus_mcu's Task 5 deletion of its
six 74LVC245A. Does that apply uniformly to all six shifters on this sheet
(U2-U7)?
**Why:** U2/U3/U4/U5 (data + 3x address snoop) don't just level-shift -- they
share ONE 8-bit MCU "snoop bus" SB0-SB7 (GPIO0-7), with the PIO enabling only
one '245 at a time via AOE_LO/AOE_MID/AOE_HI/DOE (decision #2, above). That
is a GPIO-BUDGET time-division mux, driven by the RP2350B having only 48
GPIO for A0-19(20)+D0-7(8)+6 ctrl+IOCHRDY+VGA(10)+HDMI(8)+straps, not by the
5V/3.3V voltage split. Direct-wiring A0-19+D0-7 would need 28 dedicated GPIO
instead of the current 8 (SB0-7) + 5 (AOE_LO/MID/HI, DOE, DDIR) = 13; after
freeing GPIO40 (RDY_OE, see below) this part sits at 47/48 GPIO with zero
slack for a 15-pin increase. Deleting U2-U5 is not possible without a
redesign outside this task's scope.
U6 (control snoop, 8 channels, always enabled CE=GND, fixed direction
A->B=GND) and U7 (IOCHRDY driver, 1 channel, fixed direction, OE=RDY_OE) have
NO muxing role -- U6's 8 channels are all always-on 1:1 passthroughs, and
U7's tri-state-on-demand behavior is exactly what an RP2350B GPIO does
natively (as established by bus_mcu's HOLD/HLDA/strobe direct-connect,
commit 63580f1). Both add nothing once both sides of the bus are 3.3V.
**Pick:** KEEP U2/U3/U4/U5 (still 74LVC245A on 3V3_VID, now serving purely as
the GPIO-budget mux, not a level shifter -- functionally unchanged).
DELETE U6 and U7: GPIO8/9/10/11/20/21/38/39 now label directly onto
~{MEMR}/~{MEMW}/~{IOR}/~{IOW}/BALE/AEN/CLK/RESET_DRV; GPIO27 labels directly
onto IOCHRDY (GPIO tri-states it natively when not asserting a wait state).
GPIO40 (ex-RDY_OE) is freed -> no_connect. R37 (RDY_OE park) removed; IOCHRDY
floating during MCU Hi-Z is caught by the Bus MCU sheet's shared idle-high
pull-up (R2), same reliance every other soft card already has on that net.
This matches bus_mcu's own precedent of keeping U14-U16 (its '244s) because
they were the address counter's only tri-state, not level shifters.
</content>
</invoke>

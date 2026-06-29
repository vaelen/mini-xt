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
</content>
</invoke>

# Open questions -- supervisor sheet

## 1. No QSPI-flash symbol in the available libraries
**Question:** The RP2040 boots from external QSPI flash, and design doc S5.0/S7 puts
the BIOS + option-ROM images in the Supervisor's QSPI flash. Which flash part / symbol?

**Why it matters:** Without a boot flash the RP2040 cannot run, and there is nowhere to
store the BIOS images the Bus MCU shadow-loads. The guide named `Memory_Flash` / `W25Q`,
but `pins.py -s Flash`, `-s W25`, `-s 25Q`, `-s SST39`, `-s AT25` all return nothing --
no flash library is installed, only `Memory_RAM` (SRAM/PSRAM/SDRAM) and EEPROM-less.

**Options:**
- (a) Use a generic SPI/QSPI part from `Memory_RAM` (wrong device class -- it's RAM).
- (b) Place a `Connector_Generic` header standing in for the 8-pin SOIC flash footprint.
- (c) Add a custom `mini-xt:W25Q128` symbol (out of scope -- task says edit only this sheet).

**Pick: (b)** -- `Connector_Generic:Conn_01x08` as `J1`, pinned CS / SCLK / SD0..SD3 /
+3V3 / GND, matching a standard 8-pin SPI-flash (W25Qxx-class, e.g. W25Q128, ~16 MB:
firmware + ~128 KB BIOS/option-ROM images with room to spare). Swap for a real flash
symbol when a `Memory_Flash` library is available.

## 2. No 7-segment display symbol
**Question:** The 2-digit hex POST display -- two 7-seg digits or a header?

**Why it matters:** `pins.py -s 7Seg` / `-s Segment` find nothing; no 7-seg symbol exists.

**Pick:** A `Connector_Generic:Conn_01x10` header (`J3`) carrying the 8 segment lines
(POST_A..POST_G, POST_DP) and 2 digit-select lines (POST_DIG0/1), multiplexed common
display driven directly from GPIO. Per-segment current-limit resistors are assumed on the
display module / omitted at this fidelity. Replace with two 7-seg symbols if added to libs.

## 3. RP2040 supply topology
**Decision (not a blocker):** Wired IOVDD/USB_VDD/ADC_AVDD/VREG_VIN to +3V3, the internal
core LDO output VREG_VOUT to a local `VCORE` (1.1 V) net feeding DVDD, per the RP2040
hardware-design reference. DVDD is NOT tied to +3V3.

## 4. USB series resistors / ESD
**Decision:** D+/D- run straight from the RP2040 native USB PHY to the USB-A jack (the
RP2040 integrates the USB series/pull resistors). No external 27 R / ESD parts placed at
this fidelity; add ESD diodes on a real layout.

## 5. VBUS / 5 V
**Decision:** USB VBUS is sourced from the global `+5V` net (design S13: 5 V must source
downstream USB). `+5V` arrives as a global power net, so it is NOT exposed as a hier pin;
only LINK_B2S / LINK_S2B / SPEED_SEL cross the sheet boundary -- keeping the two-MCU
interface minimal as the design intends.

## 6. USB host port hardening (design review 2026-07-11)
**Decision:** Added the RP2040-required 27R series resistors on USB D+/D- (R2/R3), a
USBLC6-2SC6 ESD array at the jack, and 100uF bulk on VBUS_KBD (USB hosts must supply
>=120uF-class bulk for downstream inrush; the polyfuse alone would brown-out on keyboard
hot-plug). GPIO16 now reads PD_PG from the power sheet (CH224K power-good) so setup can
warn when only default-USB current is available.

## 7. PicoGUS-derived improvements + shared programming port (2026-07-11)
**Decision:** Crystal caps corrected 15pF -> 30pF (CL=20pF part) with 1k series on XOUT
(R4), per the RP2040 minimal design / PicoGUS chip-down. BOOTSEL button added
(SW1 + R5 on QSPI_CS) since the chip is now USB-flashable. J6 (USB-C) + SW2
(DPDT slide) form ONE programming port for both bare RP2040s: A = Supervisor
(shares the PHY with the USB-A host jack -- unplug the keyboard to flash),
B = PicoGUS via PGUS_USB_DP/DM. J6's VBUS is deliberately unconnected: the
board must be powered to flash, eliminating back-power paths entirely.

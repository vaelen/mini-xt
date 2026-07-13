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
**STALE (2026-07-12):** the sheet now places a real W25Q128JVS (U2) on the
QSPI pins; the placeholder header J1 is gone.

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

## Programming-port ESD (2026-07-12)
U3 (USBLC6) sits on the jack-side USB_DP_J/DM_J nets, which only cover SW2
position A -- in position B (PicoGUS flashing) J6's pins had no ESD path.
Added U4 (second USBLC6) on PROG_DP/DM at J6 so both positions are protected;
clamp rail is +3V3 (J6 VBUS is unconnected and signaling is 3.3 V USB).

## 8. I2C RTC (PCF8563) + CR2032 replaces the DS12C887 sheet (2026-07-14, Task 8)

**Context:** `hardware/sheets/rtc.py` (DS12C887 + ISA glue) is deleted. The Bus
MCU now emulates ports 0x70/71 in firmware (see bus_mcu.py's docstring); the
real timekeeping hardware -- a PCF8563 I2C RTC + CR2032 backup cell -- moves
here, off-bus, synced over the existing UART link at boot. `RTC_SDA`/
`RTC_SCL` are supervisor-internal nets, not in `PINS` -- the two-MCU
interface stays exactly as small as before.

**GPIO pins (U5 I2C):** GPIO2/GPIO3, the RP2040's *default* I2C1 SDA/SCL
function-select pair. Picked from the pool of GPIO2/3 + GPIO17-29 that were
all sitting in the sheet's spare/no-connect list -- GPIO2/3 need no PIO/mux
workaround (any GPIO can be muxed to any I2C block on the RP2040, but the
default assignment reads better in a schematic and needs zero firmware-side
function-select justification). GPIO17-29 remain NC/spare.

**Pull-ups:** 4.7k SDA/SCL pull-ups (R8/R9) go to `+3V3`, not to the
battery-only `VDD_RTC` rail. The Supervisor is the only I2C master on this
bus and it only runs on board power, so the bus is only ever driven while
+3V3 is up; pulling from +3V3 avoids leaking current into `VDD_RTC` through
the PCF8563's internal ESD diodes while the board is off, for no benefit
(the bus is dead anyway with the board unpowered).

**VDD_RTC battery-OR:** Two SS34 Schottkys (D1 from `+3V3`, D2 from
`VBAT_RTC`/CR2032) diode-OR onto `VDD_RTC`, the PCF8563's actual VDD pin --
the standard low-power-RTC backup arrangement (also used for VBUS OR-ing in
bus_mcu.py/video.py/card_isatest.py, so no new part class). With the board
powered, `+3V3` (minus D1's forward drop) sits above the ~3.0 V CR2032 and
wins; with the board off, the CR2032 alone carries `VDD_RTC` through D2.
100 nF (C8) decouples `VDD_RTC`; BT1 (CR2032, parts.py's existing
`Device:Battery_Cell`/`CR2032` entry, LCSC C22363833) grounds its `-` pin.

**Crystal + load caps (datasheet: NXP PCF8563 Rev 10, 3 Apr 2012, `C_OSCO`/
quartz-parameter tables, fetched via a Seiko-mirrored PDF after nxp.com
404'd, same as Task 2's gensym.py pin-verification note):** the PCF8563 has
ONE **integrated** oscillator capacitor on OSCO (`C_OSCO`: 15-35 pF, typ
25 pF) -- OSCO gets NO external cap. Only OSCI needs an external trim cap
(`Ctrim`: 5-25 pF external), and the datasheet gives
`CL = Ctrim * C_OSCO / (Ctrim + C_OSCO)` where `CL` is the crystal's rated
load capacitance (quartz-parameter table: 7-12.5 pF, Rs <= 100 kOhm).
Crystal picked: **C32346** (Epson Q13FC13500004, SMD3215-2P, CL=12.5pF,
ESR<=70kOhm) -- JLC's deepest-stock (437k) basic-library 32.768kHz part, and
CL=12.5pF is the datasheet's own quartz-CL ceiling. Solving for Ctrim at
C_OSCO=25pF typ gives ~25pF; rather than add a new capacitor SKU, C7 reuses
parts.py's existing **22pF** (`Device:C`/`22pF`, already sourced for the NIC
20MHz crystal) -- a couple pF off nominal, which shifts the effective load a
sub-pF-equivalent amount, dwarfed by the crystal's own +-20ppm tolerance at
this fidelity. Added `("Device:Crystal", "32.768kHz")` to parts.py.

**~{INT} / CLKOUT:** both NC. The Supervisor polls time over I2C rather than
servicing an RTC interrupt, and CLKOUT (32.768kHz/1.024kHz/32Hz/1Hz test
clock out) has no consumer on this board.

**IRQ8 side effect (flagged, not fixed here):** `rtc.py` used to drive the
motherboard-only `IRQ8` net (Bus MCU's '165 IRQ collector) via a push-pull
'04 output -- IRQ8 never reached the 60-pin ISA header (pin 15 is GND per
the 2026-07-12 review). With `rtc.py` gone, IRQ8 is now genuinely undriven;
noted in bus_mcu.py near its PINS-list IRQ comment and left as a dangling
label (ignorable at this fidelity per CLAUDE.md) for a follow-up to either
repurpose or formally retire the line -- out of scope for this task (RTC
sheet deletion + Supervisor I2C RTC only).

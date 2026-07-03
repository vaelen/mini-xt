# JLCPCB sourcing — 2026-07-03

Every component in the design was checked against the JLCPCB parts database.
The authoritative machine-readable result is `tools/parts.py` (the (lib_id,
value) → LCSC map that build.py applies as `LCSC Part Num` properties); this
file records the decisions and the things a human must re-check at order time.

## Custom-symbol pin verification (open-questions Q5 — RESOLVED)

Verified against JLCPCB/EasyEDA symbol data and the Maxim datasheets:

- **MAX3241** (MAX3241EEAI+T, LCSC C406859, SSOP-28): the original
  best-effort symbol was wrong on essentially EVERY pin (only C2+ matched),
  and used MAX3243-style pin names. The real part has `SHDN#` (22, tie high
  to run), `EN#` (23, tie LOW to enable receiver outputs), and two
  always-active receiver outputs `R1OUTB`/`R2OUTB` (21/20, NC here).
  Symbol regenerated; com_port.py rewired (~FORCEON→~EN is a polarity fix:
  it must be GROUNDED, where the old ~FORCEON was tied high).
- **DS12C887** (DS12C887+, LCSC C9869, EDIP-24): four pins were wrong —
  DS is 17 (was 16), RESET# 18 (was 17), IRQ# 19 (was 18), SQW 23 (was 21).
  Symbol regenerated; rtc.py wiring is by pin NAME so it followed along.

## Stock-forced substitutions (all same-pinout, netlist-verified)

| Wanted        | Not stocked → used     | LCSC     | Why it is safe |
|---------------|------------------------|----------|----------------|
| 74HCT374      | 74HCT574               | C6001    | same function, flow-through pinout; parallel.py rewired (Q→ outputs) |
| 74HCT163      | 74HC161                | C5610    | same pinout; async ~MR tied inactive; see voltage-domain note below |
| 74HCT157      | 74HC157                | C5609    | 3.3 V selects/PIO clock now pass through spare HCT04 gates (inverting → mux I0/I1 swapped) |
| 74HCT02       | 74HC02                 | C5588    | RTC decode inputs are always-5 V address lines |
| TCM809        | MCP809T-450I/TT        | C511285  | same SOT-23 pinout, 4.375 V threshold |
| 2N3904        | MMBT3904               | C20526   | SMD version of the same die |
| TL072→MCP6002 | (already swapped, H6)  | C7377    | RRIO, pin-identical |
| 1.8432 MHz XO | crystal on 16C550 XIN/XOUT | C47345430 | canned XOs at this frequency are 3.3 V-only and soft cards have no 3.3 V rail |

**HC-at-5V voltage-domain rule:** plain 74HC at 5 V cannot read a 3.3 V high
(Vih ≈ 3.5 V). Wherever an HC substitute would have seen a 3.3 V input:
- **bus_mcu address counters (5× HC161 + the HC08 CNT_RUN gate) moved into
  the 3.3 V domain** (VCC = 3V3_BUS): all their control inputs are MCU
  GPIOs, and the load data now comes from the MCU-side MD0–7 nets. Their
  3.3 V outputs feed the 5 V 74HCT244 bus buffers, whose TTL Vih (2.0 V)
  reads 3.3 V cleanly. No level shifters needed at all.
- **clock muxes (HC157 at 5 V)**: SPEED_SEL / CLK_SRC / PIO_CLK are squared
  up through spare 74HCT04 gates (HCT reads 3.3 V, drives 5 V). The gates
  invert, so each mux's I0/I1 inputs are swapped to keep firmware polarity.
- **14.31818 MHz oscillators are 3.3 V-only parts**: powered from +3V3 and
  buffered to the 5 V OSC net by a spare HCT04 gate (cpu_core U13,
  card_isatest U19). Clock phase inversion is irrelevant.

## Socket policy (fab installs the socket, chip goes in by hand)

| Component            | Socket (= its LCSC Part Num) | Chip source        |
|----------------------|------------------------------|--------------------|
| V20 (µPD70108)       | DIP-40 socket C2332          | user stock (vintage) |
| AS6C4008-55 SRAM ×2  | DIP-32 socket C72122         | user stock (no 5 V 512K×8 SRAM at JLC at all) |
| DS12C887 RTC         | DIP-24 600 mil socket C72120 | LCSC C9869 ($14, extended) or user stock |
| Core2350B module ×2  | 2.54 mm female headers C2897411 | Waveshare        |
| Pico module          | 2.54 mm female headers C2897411 | Raspberry Pi     |

## Not available at JLCPCB (source elsewhere / consign)

- **8-bit ISA card-edge slot** (card_isatest J1) — 3.96 mm edge connector;
  consign or CONNFLY/EDAC from another distributor.
- **VGA HD15 (DE15) connector** (video card) — THT part from another
  distributor, or build the video card HDMI-only initially.

## Thin stock — re-verify with jlc_stock_check before ordering

- TL16C550DPTR (C544406): ~18 pcs, $4.9. Also note the LQFP-48 pin numbers
  do NOT match the DIP-40-style KiCad symbol — remap at footprint time.
- DB25 male (C5400534): ~10 pcs — likely needs a substitute.
- MAX3241EEAI+T (C406859): ~175. DS12C887+ (C9869): ~573.
- TPS563200DDCR (C97253): ~256.

## Other design changes made during sourcing

- **Supervisor QSPI flash is now a real W25Q128JVSIQ (C97521, basic)** —
  the placeholder 8-pin header could never boot the RP2040.
- 12 MHz crystal C9002 (CL = 20 pF): the 15 pF load caps (C1644) should be
  revisited against the crystal's CL at layout (≈2×(CL−Cstray) suggests
  more like 27–33 pF).
- 22 µF bulk caps: MLCC (C12891) replaces the polarized symbol's implied
  electrolytic.
- LEDs: KT-0603R (C2286) for both rail indicators.
- All jumpers/headers are cut-to-length 2.54 mm breakaway strips
  (C2337 1×40, C2333 2×40); the CF socket is a real SMD CompactFlash
  connector (C2962036) whose footprint replaces the generic 2×25 header at
  layout.

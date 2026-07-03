# card_isatest -- decisions & open questions

Board: standalone Pico-based ISA host/bus-master card tester.
Spec: docs/superpowers/specs/2026-07-01-isa-test-card-design.md

## Decisions made during generation

- **Data bus direct, address shift-registered.** D0-7 on Pico GPIO (MD0-7);
  A0-19 on a split 74HC595 OUT chain (address latch RCLK_ADDR, control latch
  RCLK_CTRL). Fits 24/26 GPIO. (spec D2-D4)
- **Real ISA slot uses Connector:Bus_ISA_8bit** (stock true-pinout symbol) with a
  name remap to our mxbus nets; no custom isa_slot symbol was needed. The
  DACK0/REFRESH# pin maps to ~{REFRESH}; -5V/-12V/+12V/UNUSED left NC.
- **74HC595 (standard 74xx lib) for the OUT chain; mini-xt:74HCT165 reused for the
  IN chain.** Both run at +3V3; at 3.3V the HCT vs HC threshold distinction is
  moot. Confirm HC595 part choice at layout (74LVC595 also acceptable).
- **Config selects (SPEED_SEL / CLK_SRC / DUT_PWR_EN)** ride the address-latch
  spare 595 outputs (U11 QE/QF/QG), keeping GP27/GP28 as true spares.
- **Clock tree mirrors cpu_core** (14.318 can osc, /2 74HCT74, /3 74HCT163
  preset-to-3, 74HCT157 mux, 74HCT04 buffer), plus a second 74HCT157 for the
  PIO_CLK override selected by CLK_SRC.

## Open questions (review before layout)

- **/3 preset-to-3 (U16):** DIV3_TC/DIV3_LD wiring is copied from cpu_core and
  carries the same review flag -- verify the terminal-count-to-load path (polarity
  / one-shot) on the bench. (These two nets show as label_dangling in isolation,
  as in cpu_core -- expected.)
- **P-FET gate drive (Q1):** G is driven from DUT_PWR_EN (3V3 logic) with a pull
  to keep it off by default. A high-side P-FET switching a 5V rail needs its gate
  pulled to the source rail when off and pulled low (possibly via an NPN/level
  shift) to turn on -- the current single-resistor idle is a placeholder; finalize
  the gate-drive network at layout.
- **ISA slot analog pins:** -5V/-12V/+12V left NC. Decide whether to add labeled
  test points/jumpers for the rare 8-bit card that needs them.
- **Pico module symbol pin numbers:** GPIO NAMES are authoritative; the 40-pin
  physical numbers are best-effort -- confirm against the Pico datasheet at layout.
- **Bus-mastering DUT:** address is output-only; testing a card that drives the
  address bus is out of scope (would need address-readback buffering).

---
**Corrections (2026-07-03, design review H7/H8):**
- DUT power P-FET: the 3.3 V gate-drive placeholder could neither turn the FET
  fully off nor default safe. Gate now pulls to V5RAW (R5, off by default) and
  is driven low through Q2 (2N3904 open-collector, base R4 from DUT_PWR_EN,
  which now pulls DOWN via R3). DUT_PWR_EN=1 -> DUT powered.
- The /3 divider's TC->~PE reload was two dangling nets ('163 free-ran /16, so
  "4.77 MHz" was 0.895 MHz). TC now inverts through a spare U19 gate into ~PE,
  same as cpu_core.

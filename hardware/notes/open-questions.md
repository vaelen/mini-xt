# Open questions & autonomous decisions — mini-xt KiCad schematics

Decisions I made without you (per your instruction to keep working and log
questions for later review). Each: the question, why it came up, the options, and
the choice I made. Per-sheet questions from the sub-agents are in the
`questions-<sheet>.md` files alongside this one.

---

## Project-wide decisions (made during the foundation)

### Q1. How to generate electrically-valid KiCad files at this scale?
**Why:** Hand-authoring S-expressions for ~12 hierarchical sheets is extremely
error-prone (UUIDs, instance paths, pin coordinates, embedded symbols).
**Options:** (a) hand-write .kicad_sch; (b) use a Python library (kiutils — not
installed); (c) write a small purpose-built generator.
**Chosen:** (c) — `hardware/tools/mxsch.py`, a ~500-line generator validated
end-to-end with `kicad-cli` (netlist export proves connectivity). It reads pin
geometry from the real KiCad symbol libraries, embeds symbols correctly
(including resolving `extends` inheritance), and snaps everything to the 1.27 mm
grid. This is the single most important decision; everything else builds on it.

### Q2. Schematic fidelity.
**Chosen (you approved):** interface-focused — real symbols, all hierarchical
interface pins, key supporting parts and decoupling, every inter-sheet signal
wired; not guaranteed pin-perfect-complete for every passive. Goal is clarity of
module boundaries / isolation, not a manufacturable BOM.

### Q3. Bus representation.
**You approved "KiCad buses".** Implementation nuance: for reliability across
independently-authored sheets, each sheet connects signals by **named member
labels** (D0, A5, IRQ4, …) via hierarchical pins, and the **root** ties
identically-named pins together. This yields a correct netlist regardless of
sheet author. The wide groups are declared as bus aliases A[0..19]/D[0..7]/
IRQ[2..15] in the contract. If you want literal drawn bus-with-bus-entry graphics
on every sheet (purely visual), that's a follow-up beautification pass — the
electrical result is identical.

### Q4. V20 symbol.
**Why:** No µPD70108/V20 symbol in KiCad libs.
**Options:** (a) reuse stock `8088_Min_Mode`; (b) author a custom V20.
**Chosen:** custom `mini-xt:V20`, copied from the stock base `8088` symbol (whose
pinout *is* the min-mode pinout: ALE, ~WR, IO/~M, ~RD, HOLD, HLDA, ~SS0, MN/~MX,
…) and relabelled. Pin-accurate and pin-compatible with the V20.

### Q5. MAX3241 and DS12C887 symbols.
**Why:** Neither exists in the KiCad libs.
**Chosen:** authored both as flat single-body symbols in `mini-xt.kicad_sym`.
**REVIEW NEEDED:** the **pin numbers** for MAX3241 (28-pin) and DS12C887 (24-pin)
are best-effort from the datasheets — please verify against the real datasheets
before any layout. Functional pin *names* and the interface are correct; only the
package pin-number assignment is the risk.

### Q6. 74xx glue as flat symbols.
**Why:** KiCad's 74xx symbols are multi-unit (e.g. a quad NAND = 4 gate units +
a power unit); my generator is single-unit.
**Chosen:** auto-generate flat single-body versions of the glue chips
(573/245/138/00/02/04/08/32/74/125/157/163/165/244/374/4017) into
`mini-xt.kicad_sym`. Clearer for an architecture schematic (whole chip on one
body) and avoids multi-unit complexity. Some are sourced from 74LS variants of
the same pinout (e.g. 74LS573 for the 74HC573) — pinout identical, value label
says the HC part. A few families (LVC245A) reuse the 74HC245 body with a value
override.

### Q7. Power nets.
**Chosen:** +5V / +3V3 / GND are treated as **global power nets** (via power
symbols), not hierarchical interface pins — standard practice; every chip needs
power, so they're not part of the "isolation interface" the exercise is probing.
The `power` sheet drives them (with PWR_FLAGs). Functional signal interfaces are
what's exposed as hierarchical pins.

### Q8. Extra sheets beyond your list of 8.
**Why:** the design doc implies more of the board.
**Chosen:** added `storage` (XT-IDE + CF, §10), `audio` (PC-speaker + op-amp
summer + PicoGUS line-in stub, §9), and `sidecar` (2×32 ISA header, §4.3). Drop
any you don't want — they're self-contained sheets. PicoGUS itself is excluded
per your instruction (only a line-in header stub remains on the audio sheet).

### Q9. Footprints.
**You approved skipping footprints** — schematic capture only. Footprints can be
assigned later when moving to layout.

### Q10. ERC expectations.
At this fidelity, ERC will report many `pin_not_connected` / `pin_not_driven` /
`label_dangling` warnings — these are inherent to interface-focused schematics
(unused chip pins, signals that legitimately go to one place). The build harness
keeps the structural errors (off-grid, unconnected wires, duplicate net names,
load failures) at zero. `lib_symbol_issues` from the CLI is just "library not in
the running app's config" and is harmless.

---

---

## Integration results (final)

- **12 sheet instances** (cpu_core, bus_mcu, supervisor, video, COM1, COM2,
  parallel, rtc, power, storage, audio, sidecar), **217 components, 217 unique
  references** (no collisions — per-sheet reference banks + per-instance suffix).
- **Netlist exports cleanly** and cross-sheet connectivity is verified:
  D0 spans 8 sheet-banks, A0 8 banks; HOLD ties V20↔Bus-MCU; LINK_B2S ties
  Bus-MCU↔Supervisor; SPEED_SEL ties clock-mux↔Supervisor; IRQ4←COM1 and
  IRQ3←COM2 both land on the Bus-MCU '165 collector. Power is global:
  +5V 152 nodes, +3V3 77, GND 289.
- **Isolation holds:** soft cards (video, com, lpt, rtc, storage, sidecar, audio)
  connect only via ISA signals + power; private signals (HOLD/HLDA, the UART
  link, SPEED_SEL, counter strobes, Y5) appear only between the motherboard
  nodes. The hierarchical pin lists make this auditable per sheet.
- A 13-page PDF renders (`mini-xt.pdf`).

### Fix applied during integration
- Power rails were initially sheet-local (sub-agents used local labels); the
  generator now auto-promotes +5V/+3V3/GND to **global** labels so they form one
  project-wide net each. (mxsch `Schematic.POWER_GLOBAL`.)
- Added a flat `mini-xt:TL072` so the audio op-amp's second half + power pins are
  placeable (KiCad's stock TL072 is multi-unit, which the generator doesn't split).

### Remaining ERC (all expected at interface-focused fidelity; netlist is correct)
- `label_dangling` — interface hierarchical labels declared via `emit_interface`
  connect cross-sheet by NAME but aren't on a wire, so ERC flags them. Harmless.
- `pin_not_connected` — unused MCU GPIO, spare gate inputs, unused chip pins.
- `pin_to_pin` — multiple drivers on the shared bus (e.g. the address counter and
  the level-shift transceivers both source A0-A19; several cards can drive D0-D7).
  Inherent to drawing a shared bus without modeling tri-state enables. By design.
- `pin_not_driven` / 2× `power_pin_not_driven` / 1× `lib_symbol_mismatch` (the
  CLI's GND-symbol-copy note) — benign.

To drive these to zero you'd add no-connect flags on every unused pin and model
bus tri-state enables — out of scope for an interface/isolation study.

## To review together
- MAX3241 / DS12C887 pin-number assignment (Q5).
- Whether you want drawn bus graphics vs the name-based bus connectivity (Q3).
- Whether storage / audio / sidecar should stay in scope (Q8).
- The per-sheet `questions-*.md` files for component/decode choices.

---

## Post-review change: standardize 5 V glue on 74HCT (your call)

Replaced the mixed HC/HCT glue with **74HCT across all 5 V logic** (TTL input
thresholds reliably read the 3.3 V level-shifter outputs; HC's CMOS Vih ~3.5 V
was marginal). This also fixed the earlier bug where the bus address latches and
data transceiver were 74HC instead of the doc's 74HCT.

- Bus-facing latch/transceiver/decoder/gates/counters/FF/mux/inverter → **74HCT**.
- The ÷3 changed from **74HC4017 → 74HCT163 preset-to-3** (no HCT 4017 exists;
  S3.2 already lists the '163 preset as the equivalent substitute). A spare
  74HCT04 gate inverts the counter's TC into ~PE for the reload.
- Per-card 3.3 V↔5 V level shifters stay **74LVC245A** (dedicated symbol).
- Net result: 11× 74LVC245A, and HCT for everything else; pinouts unchanged so
  this was purely a part-number/value change. Verified: cpu_core U2-U4 = 74HCT573,
  U5 = 74HCT245; zero structural ERC errors; netlist intact.

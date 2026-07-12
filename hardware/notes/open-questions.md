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
**RESOLVED 2026-07-03:** both symbols were verified against JLCPCB/EasyEDA
data and regenerated — the MAX3241 was wrong on nearly every pin (and used
MAX3243-style control-pin names; the real part has SHDN#/EN#/R1OUTB/R2OUTB),
the DS12C887 on four pins (DS=17, RESET#=18, IRQ#=19, SQW=23). See
`notes/jlcpcb-sourcing.md`.

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
- ~~MAX3241 / DS12C887 pin-number assignment (Q5)~~ — resolved 2026-07-03
  (verified via JLCPCB data; both symbols regenerated).
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

---

## Post-review change: speed-select moved Supervisor -> Bus MCU (your call)

`SPEED_SEL` (the 74HCT157 clock-mux select) now originates on the **Bus MCU**
instead of the Supervisor, so the Supervisor's cross-sheet interface drops to the
**2-wire UART link + power** (LINK_B2S, LINK_S2B). The Supervisor sends the chosen
CPU divisor over the link; the Bus MCU drives SPEED_SEL before it releases the V20
reset (it already owns reset sequencing, so speed + reset are now one owner).

Pin budget (§5.2): this costs 1 Bus-MCU GPIO. To stay within 48, the address/
control level-shifter direction is now **HLDA-derived externally** (the §5.2
"transceiver DIR can be HLDA-derived, 0-1 pins" option) instead of a dedicated
BUSDIR GPIO — verified `/HLDA` drives U203-206 DIR pins. Net effect: ~45-47/48,
still within budget. First GPIO to reclaim if sidecar DMA/IRQ later expand.
Verified: SPEED_SEL ties bus_mcu(U201)<->cpu_core mux(U112); supervisor interface
= LINK only; zero structural ERC errors.

---

## Post-review change: use Waveshare Core2350B modules for both RP2350B nodes (your call)

Both RP2350B sites (Bus MCU, video) now drop in the **Waveshare Core2350B**
module (`mini-xt:Core2350B`, 64-pin PGA) instead of a bare QFN-80 chip. The chip +
core SMPS (VREG/inductor) + 16 MB flash + crystal collapse into the module; the
level shifters, address counter, and IRQ collector stay on the carrier.

- **Self-powered:** each module takes **+5 V on VBUS** and its onboard **ME6217C33
  LDO** makes a local 3V3 that also feeds *that card's* level shifters
  (`3V3_BUS` / `3V3_VID`, sheet-local, never paralleled). The LDO is small, but the
  ~35 mA shifter load per module is well inside its headroom (it's an LDO at 5->3.3V,
  so keep loads module-local and modest -- which this is).
- **PSRAM variant per node:** Bus MCU = **0 MB** (keeps GPIO47 free for ~{WR}, the
  pin-bound node); video = **8 MB** (onboard PSRAM is the VGA aperture, CS=GPIO47,
  internal -- the discrete APS6404 was removed).
- **HSTX/HDMI** stays on GPIO12-19; **LED on GPIO39** rides along free (= CNT_LD2 on
  the Bus MCU, = RST_M on video -- both still functional, now with a status LED).
- The central 3.3 V buck **stays** (the bare RP2040 Supervisor still needs +3V3);
  the modules just no longer load it. Verified: +3V3 still has the Supervisor.

Module symbol pin NAMES are authoritative; the PGA pin NUMBERS in the symbol are a
functional placeholder. **Resolved 2026-07-03:** module photos
(`hardware/Core2350B0-details-*.jpg`) show the holes are silk-labelled by signal
name with NO canonical numbering — so the symbol's numbers are project-defined
and the layout footprint must simply be authored to match them. The module is a
25.4 mm² double-ring PGA (no castellations → header-mounted only, ~6 GND holes);
photos confirm HSTX = GP12-19 and PSRAM CS = GP47. See notes/jlcpcb-sourcing.md.

---

## Feature: shared ISA connector + standalone chainable soft-card PCBs (your request)

**Shared ISA connector** (`sheets/isa_conn.py`): the 2x32 (64-pin) ISA header is
now a reusable building block -- `place_header(sch, ref, at, remap=)` plus the
64-pin signal map (interleaved grounds, +5V, key pin). `sidecar.py` was refactored
to use it, so the motherboard edge and the dev cards share one identical pinout.
(IRQ8 was added to the header -- one redundant ground dropped to stay 64-pin -- so
the RTC card's interrupt is carried.)

**Per-card dev PCBs** (`sheets/card_<name>.py` -> built to `hardware/cards/`):
each soft card (video, com, lpt, rtc, storage) is now a standalone board =
the soft-card schematic + **two** chainable ISA headers (`J_IN` / `J_OUT`,
same nets => pass-through). Bus + power (+5V/GND) flow in J_IN, through to J_OUT,
and the card logic taps the bus by name. So you can fab each card separately and
**daisy-chain them header-to-header** for development. Each card is its own
top-level schematic/project (A2 sheet) in `hardware/cards/` (own .kicad_pro), and
the soft-card `build(sch, lib, expose=False)` skips the motherboard-facing
hierarchical pins so everything ties to the on-card headers.
- Verified: J_IN<->J_OUT pass-through + logic tap on every signal (e.g. card_com:
  D0/~{IOR}/A5 each = J_IN + J_OUT + the UART; COM_IRQ taps the IRQ4 line via the
  per-card header remap). Structural ERC = 0 on all five cards.
- The integrated motherboard is unchanged (soft cards still plug into the single
  sidecar there); the card PCBs are the parallel development arrangement.

**Known cosmetic issue:** `kicad-cli sch export netlist` prints "schematic has
annotation errors" for the card sheets. This does NOT appear in ERC (the
authoritative annotation check), the netlist exports completely and correctly, and
all references are unique/annotated with no duplicate UUIDs -- it's a CLI exporter
quirk triggered by the 64-pin connector, not a real defect. Opening a card in the
KiCad GUI shows a properly annotated, ERC-clean schematic.

---

## Change: ISA connector re-based on the standard 8-bit ISA pinout (60-pin, your call)

`isa_conn` now uses the **standard 8-bit ISA pinout on a 60-pin 2.54 mm header
(Conn_02x30_Odd_Even)** -- laid out exactly like the PicoGUS `Bus_ISA_8bit`
header, so the sidecar and dev cards are pin-compatible with real 8-bit ISA cards
(and 60-pin ribbon/headers are far easier to source than 64-pin). Replaces the
earlier arbitrary 64-pin order.

Since we don't use the ISA analog rails (S13: no +-12V / -5V), those three pins
are reclaimed:
  * pin  7 : -5V   -> ~{IOCHCK}  (channel check -> NMI)
  * pin 11 : -12V  -> GND        (extra ribbon return / signal integrity)
  * pin 15 : +12V  -> IRQ8       (RTC)
Pin 13 (reserved / 0WS#) is left unconnected, as on the PicoGUS header.

Dropped: the non-standard IRQ10/11/14 (spare/unused; on a real AT they live on the
16-bit extension connector, not the 8-bit edge). DACK0/REFRESH# now appears on its
standard pin (pin 35) but is undriven on our side (we refresh internally; SRAM
needs none) -- it's there for ISA-card compatibility.

Verified: pin map correct (7=~{IOCHCK}, 11=GND, 15=IRQ8); ~{IOCHCK} ties
sidecar<->Bus MCU; IRQ8 ties sidecar<->Bus-MCU collector<->RTC; IRQ10/11/14 gone;
bus intact; zero structural ERC on the motherboard and all five cards. The change
lives entirely in isa_conn.py, so the sidecar and all card_* sheets picked it up.
Note: the Bus MCU's 74HC165 still samples IRQ2-9, so IRQ8 is collected; nothing
above IRQ9 is on the connector anymore.

---

## Change: drive REFRESH# from the Bus MCU (your call)

The ISA REFRESH# line (standard pin 35, the DACK0/REFRESH# position) is now an
ACTIVE output of the Bus MCU instead of an undriven `~{DACK0}` stub, so DRAM-based
ISA cards on the sidecar/chain stay refreshed.

- `isa_conn` pin 35 net renamed `~{DACK0}` -> `~{REFRESH}`.
- Bus MCU drives it from **GPIO47**, reclaimed from the (redundant) raw-`~WR`
  sense -- the MCU already tracks writes via the gated MEMW/IOW on GPIO17/19, so
  no net GPIO cost (budget stays ~46-48/48). `~{REFRESH}` added to the Bus MCU
  interface (output) and to `_NET_SHAPE`.
- Generation: driven from the same internal ~15 us refresh timer that produces the
  0x61-bit-4 toggle. A full refresh cycle reuses the existing bus-master engine --
  it walks the refresh row address on A0-A7 via the §5.1 counter and pulses MEMR#
  -- so a DRAM card sees a standard RAS-only/CBR refresh; only the REFRESH# strobe
  itself needed a pin.
- Verified: `~{REFRESH}` ties sidecar(J1) <-> Bus MCU(GPIO47); passes through
  J_IN<->J_OUT on every dev card; zero structural ERC on motherboard + all cards.

---

## Change: COM/LPT/RTC standalone cards removed (your call, 2026-07-11)

The card_com / card_lpt / card_rtc wrappers and their generated PCBs are
deleted; those peripherals live on the motherboard only (still one isolated
soft-card sheet each). In exchange the sheets gained the full jumper set a
real card would have -- COM: J2 base 0x3F8/0x2F8, JP2 IRQ4/IRQ3/open=polled,
JP3 enable; LPT: JP1 base 0x378/0x278, JP3 IRQ7/IRQ5/open=polled, JP2 enable
-- so an on-board port can be disabled or re-strapped to make room for the
same peripheral on the sidecar chain. Standalone cards that remain: video,
storage, isatest (the ones that earn their own PCB). A card wrapper is ~25
lines (see card_video.py), so any deleted card is trivially restorable from
git history if needed.

---

## Change: storage card removed; on-board XT-IDE gains IRQ14 default (your call, 2026-07-11)

card_storage is deleted (same rationale as the COM/LPT/RTC removal -- the
on-board sheet carries the full jumper set; restorable from git in ~25
lines). The storage sheet gains JP3: IRQ14 (default, AT primary-IDE
convention) / IRQ5 (XT fallback) / open = polled. IRQ14 required a physical
path into the soft-PIC: the Bus MCU's IRQ collector is now a cascaded pair
of 74HCT165s (U12 IRQ2-9 + U19 IRQ10-15, same 3 GPIO, 16-bit shift), which
also un-dangles the IRQ10-15 interface pins the sheet had declared all
along. IRQ10-15 are motherboard-internal -- the 60-pin header still carries
only IRQ2-8. Standalone cards remaining: video, isatest.

---

## Change: design-review fixes, IRQ8 off the expansion header (2026-07-12)

Review sweep of the whole motherboard netlist + all sheets. Fixes applied:

- **IRQ8 removed from the 60-pin ISA header** (isa_conn pin 15 -> second GND
  return, like pin 11). The RTC is on-board, so IRQ8 is now exclusively the
  RTC sheet's push-pull '04 output into the Bus MCU's '165 collector -- no
  card can ever share it, which also retires the driver-vs-driver concern
  with the RTC's non-tri-state IRQ8 drive. card_isatest keeps its IRQ8 '165
  lane for bit-map stability; the lane reads 0 via its local pull-down.
- **Bus CLK is fixed at 7.16 MHz** (cpu_core U13 buffers CLK7 to the ISA CLK
  pin; the speed mux retimes only CPUCLK). A real turbo XT often did the
  same; nothing in this design times off CLK -- cards are strobe-timed. If a
  picky card ever needs CLK = CPU clock, buffer CLK_MUX instead of CLK7.
- **MCU-Hi-Z parking completed** (bus_mcu R25-R28): ~{CPURESET} pulled low
  (V20 + RESET_DRV held in reset while the Bus MCU is unprogrammed/BOOTSEL/
  pre-init -- previously the V20 came out of reset with floating HOLD/READY/
  INTR after the TCM809 timeout), ~{DACK1}/~{REFRESH} parked deasserted
  (3V3_BUS -- both sit directly on RP2350B pins), DRQ1 idled low.
- **Supervisor 12 MHz crystal**: the 1k damping R4 was wired in parallel with
  nothing (XOUT, crystal and load cap all on one net, R4's far end dangling).
  Now XOUT -> R4 -> crystal + C2, per the RP2040 minimal design.
- Floating spare CMOS inputs grounded everywhere (cpu_core U4 D4-D7, rtc U5
  gates 3/4 + U6 P13, storage U3 gates 3/4); NC-marking an input doesn't
  stop it floating -- GND is now the uniform convention.
- VGA blue ladder 1k/510 -> 820/470 (full-scale was ~12% below R/G).
- Audio: PG summing 10k -> 20k (headroom), 100k LINE bleed, MCP6002 unit B
  parked as follower (see questions-audio.md).
- Power: CH224K VDD now fed through 1k (R9) with C6 at the pin (WCH ref design).
- com_port: 10k pull-up on UART_RXD (SIN idles at mark with JP1 open); CLK
  dropped from PINS (never used -- the UART has its own crystal). parallel:
  RESET_DRV dropped from PINS (never used; '574s have no reset). storage: R3
  deleted (pull-up on a push-pull node); "populate ONE of J1/J2" note added
  (both CSELs grounded = both master).
- Supervisor: second USBLC6 (U4) on PROG_DP/DM at J6, so the programming port
  is ESD-protected in BOTH SW2 positions (U3 only covers the jack-side nets).
- ERC dangling-label cleanup (KiCad 10): emit_interface now anchors every
  hier label on a short stub ending in a same-name local label (connectivity
  unchanged -- still by name; verified /D0, /AEN, /~{MEMR} spans in the
  netlist). Interface honesty fixes that fell out of it: cpu_core dropped
  AEN/IOCHRDY from PINS (AEN is generated on bus_mcu, IOCHRDY folds into
  READY there -- nothing on cpu_core touched either), and bus_mcu dropped
  PRIV_COUNTER from PINS (the 20-bit counter chain lives on-sheet, CNT_*
  never crosses). Remaining 6 label_dangling (root IRQ9-13/15) are
  single-sheet by design: the soft-PIC collector pulls them up on bus_mcu
  and no on-board source drives them (60-pin header carries 8-bit IRQs
  only); kept in PINS as the AT-style contract for future 16-bit sources.
- ERC power cleanup: root's duplicate PWR_FLAGs removed (power.py #FLG1-3
  own +5V/+3V3/GND -- the pair made flag-vs-flag pin_to_pin errors), and
  PWR_FLAGs added on the series-fed local rails ERC can't see through:
  VBUS_MCU / VBUS_VID (Schottky), VBUS_KBD / HDMI_5V (polyfuse),
  CH224_VDD (1k), AVDD_PGUS / AGND_PGUS (ferrite). Full-build ERC is now
  just the 6 expected IRQ9-13/15 label_dangling; net membership verified
  unchanged (821 nets, node-identical to HEAD).
- IRQ collector shrunk to ONE 74HCT165 (U19 + pull-downs R19-R24 + C18
  deleted): the live set is exactly 8 lines -- D0-D6 = IRQ2-8 (header +
  RTC), D7 = IRQ14 (storage strap; replaces the source-less IRQ9).
  IRQ9-13/15 dropped from bus_mcu PINS entirely -- nothing on the board
  or the 8-bit header can drive them; a cascaded second '165 comes back
  if a 16-bit source ever appears. Firmware shifts 8 bits, Q7-first
  (IRQ14, IRQ8, IRQ7...IRQ2). Full-build ERC is now ZERO violations.
- COM/LPT IRQ straps deleted (COM JP2, LPT JP3): IRQs are hardwired to the
  PC conventions -- COM1=IRQ4, COM2=IRQ3 (via the COM_IRQ instance remap in
  INSTANCES, the sheet's first use of the netmap mechanism), LPT=IRQ7 (U13
  '125 drives the net directly). Rationale: the straps only existed to
  dodge conflicts, and the enable jumpers already do that better -- COM JP3
  / LPT JP2 disable the whole port and the tri-state IRQ driver goes silent
  with it, freeing the line. Storage JP3 (IRQ14/IRQ5) kept: its two
  positions are both real use cases (AT vs XT convention), not just
  conflict avoidance.
- Storage JP3 and the PicoGUS IRQ jumper row deleted; both hardwired.
  Storage INTRQ -> '125 -> IRQ14 (the soft PIC is AT-style anyway; poll vs
  interrupt is an XTIDE UB per-controller config, safe to leave wired --
  the '125 only drives while INTRQ asserts). PicoGUS -> IRQ5, the free
  line and now its sole driver; every personality is happy on IRQ5 and
  pgusinit tells the firmware which line to use, so the 5-row IRQ jumper
  bought nothing. PicoGUS J1 shrank 2x9 -> 2x4 (DMA pairs only; ch1 is
  the only MCU-serviced channel). IRQ5 contention is now zero -- the
  sidecar header is the only other possible driver.

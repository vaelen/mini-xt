# 3.3V Single-Board Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the mini-xt from a multi-board 5V-bus system to one PCB with a 3.3V internal bus, per `docs/superpowers/specs/2026-07-14-3v3-single-board-design.md`.

**Architecture:** The V20's demux stage (3× latch + 1× transceiver) becomes 74LVC parts at 3.3V and is the single 5V↔3.3V boundary. All per-section level shifters are deleted; MCU GPIOs sit directly on the 3.3V bus. One 512K×16 SRAM wired as 1M×8 replaces both AS6C4008s. The sidecar sheet becomes a buffered 5V-compatible ISA expansion port. RTC is emulated (I2C RTC + coin cell on the Supervisor).

**Tech Stack:** Python sheet builders (`hardware/sheets/*.py`) + `mxsch` generator; KiCad 9/10 CLI for ERC/netlist; pcbparts MCP tools (`jlc_search`, `jlc_get_part`, `jlc_get_pinout`) for parts research.

## Global Constraints

- Read `hardware/tools/SHEET_AUTHORING_GUIDE.md` before editing any sheet. `hardware/sheets/cpu_core.py` is the worked reference example.
- Edit ONLY Python sources + docs. All `.kicad_sch`, `.net`, `.kicad_pro`, `erc.rpt` files are build outputs.
- Connectivity is by net name via `sch.net(comp, pin, "NAME", kind="label", dx=..., dy=...)`. Use exact canonical names from `hardware/tools/mxbus.py`. Active-low = `~{NAME}`.
- Stay generic in sheets; concrete purchasable parts bind ONLY in `hardware/tools/parts.py` keyed on `(lib_id, value)`. A deviating value override (e.g. `"74LVC573A"` on a `mini-xt:74HCT573` body) needs a sheet comment saying why.
- Verify custom-symbol pin numbers against JLCPCB/EasyEDA data (`mcp__pcbparts__jlc_get_pinout`) before trusting them.
- Validation gate for every sheet task: `python3 hardware/tools/validate_sheet.py <name>` reports **zero** `endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`, "Failed to load". Ignore `pin_not_connected`, `pin_not_driven`, `label_dangling`, `pin_to_pin`, `lib_symbol_issues` — do not chase them, do not report them.
- Use `python3 hardware/tools/pins.py <Lib:Name>` to get exact pin names/numbers before wiring a symbol. Never guess.
- Place on the 2.54mm grid, ~40–60mm part spacing.
- When something is under-specified: make a best-guess decision, log it in `hardware/notes/questions-<sheet>.md` (question/why/options/pick), and proceed. Do not stop.
- Every task ends with a commit. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Voltage rules (new): 5V→3.3V only via 5V-tolerant LVC inputs or RP2350B GPIOs; 3.3V→V20 logic inputs direct (Vih 2.2V); V20 CLK (and RESET if Task 1 flags it) via the 5V-powered HCT04 (cpu_core U13); 3.3V LVC output legally drives TTL-input 5V ISA cards.

---

### Task 1: Verification research → `hardware/notes/3v3-verification.md`

**Files:**
- Create: `hardware/notes/3v3-verification.md`

**Interfaces:**
- Produces: a notes file with a numbered VERDICT (PASS/FAIL + evidence) for each check below, and a **Parts picks** table `| role | MPN | LCSC | package | price | stock |` consumed by Task 2.

This task is research only — no sheet edits. Use WebSearch/WebFetch for datasheets and `mcp__pcbparts__jlc_search` / `jlc_get_part` for stock.

- [ ] **Step 1: Run the seven datasheet checks** (spec §"Plan-stage verification checklist"):

1. µPD70108 (NEC V20) DC characteristics: Vih of logic inputs (expect 2.2V); exact Vih of CLK and RESET. Decide: does RESET need the 5V HCT04 path or is 3.3V direct OK?
2. IS62WV51216BLL-55TLI: confirm /LB//UB gate the outputs on reads (byte-lane trick validity) and that 55ns + one 74HC00 gate delay in the /UB and /CE paths closes 0-wait at 7.16MHz (bus cycle ≈ 4 × 140ns with ~200ns address-to-data budget — show the arithmetic against the old 2×AS6C4008 budget in `docs/xt-mcu-sbc-design.md` §4.1).
3. TL16C550C: confirm 3.3V operation is in spec; confirm the LQFP-48 (PT suffix) pinout; find it at JLC (`jlc_search "TL16C550"`). If JLC has no stock, put it on the sourced-elsewhere list (like the V20) and say so in the notes.
4. RP2350B GPIO 5V-tolerance conditions (IOVDD powered) — the pins that see raw V20 5V outputs directly (RD̄, HLDA, ALE etc. on bus_mcu).
5. 3.3V buck budget: sum 4 MCUs + SRAM (30mA) + 2× TL16C550 + MAX3241s + all HC/LVC glue; compare against the buck part on `hardware/sheets/power.py` (read its value + datasheet). Verdict: fits / needs upsize (if upsize: pick a JLC part, add to picks table).
6. PicoGUS GPIO map: read `hardware/sheets/picogus.py`; list the RP2040-GPIO→ISA-signal map implied by its LVC245 wiring, so Task 6 can preserve it exactly when wiring GPIOs direct.
7. 74HC74 ÷2 and 74HC4017 ÷3 at 3.3V, 14.318MHz input: check fmax at 3V from datasheets. HC4017 is marginal at 3V — if fmax < 20MHz, the fallback is a 74LVC161-based ÷3 (preset load); record which to use.

- [ ] **Step 2: Build the Parts picks table** — find LCSC numbers (in stock, prefer basic/preferred, else extended) for every new part:

| Role | Candidate to verify |
|---|---|
| SRAM 512K×16 | IS62WV51216BLL-55TLI = **C11315** (confirm stock) |
| Octal latch, 3.3V, 5V-tol inputs | 74LVC573A (TSSOP-20) |
| Octal buffer, 3.3V, 5V-tol | 74LVC244A (TSSOP-20) |
| Octal D-FF for parallel.py | 74LVC574A (TSSOP-20) |
| Quad tri-state | 74LVC125A |
| Open-drain dual buffer (port IOCHRDY/IOCHCK̄) | 74LVC2G07 |
| 3.3V-supply re-buys of existing bodies | 74HC00/04/08/32/125/138/157/161/165/244/245/573/574 — same physical parts work 2–6V; keep existing LCSC codes where the part is HC-grade already, find HC replacements for each HCT-grade code in parts.py |
| UART | TL16C550CPT (LQFP-48) |
| I2C RTC | PCF8563 or RX8025T class, whichever is cheapest in stock |
| CR2032 holder | SMD, e.g. C70377-class (verify) |
| ÷3 fallback (only if check 7 fails) | 74LVC161 |

- [ ] **Step 3: Write `hardware/notes/3v3-verification.md`** with the seven verdicts + picks table. Any FAIL verdict that breaks the design (e.g. V20 logic Vih > 3.3V-drivable) → STOP, report to the orchestrator instead of proceeding.

- [ ] **Step 4: Commit**

```bash
git add hardware/notes/3v3-verification.md
git commit -m "Notes: 3.3V redesign datasheet verification + JLC part picks"
```

---

### Task 2: New symbols + parts.py rebind

**Files:**
- Modify: `hardware/mini-xt.kicad_sym` (via `hardware/tools/gensym.py`)
- Modify: `hardware/tools/parts.py`

**Interfaces:**
- Consumes: Task 1's picks table (LCSC codes) and pinout data.
- Produces: symbols `mini-xt:IS62WV51216`, `mini-xt:TL16C550PT`, `mini-xt:<RTC part>` (flat, single-body, like the existing mini-xt glue symbols); parts.py entries so that `(lib_id, value)` resolves for every new value used in Tasks 4–9: `("mini-xt:74HCT573","74LVC573A")`, `("mini-xt:74HCT245","74LVC245A")` (if not placing `mini-xt:74LVC245A` directly), `("mini-xt:74HCT574","74LVC574A")`, `("mini-xt:74HCT125","74LVC125A")`, `("mini-xt:74HCT244","74LVC244A")`, HC-value variants (`"74HC00"`, `"74HC04"`, `"74HC08"`, `"74HC32"`, `"74HC138"`, `"74HC165"`) on the mini-xt HCT bodies, `("mini-xt:IS62WV51216","IS62WV51216BLL")`, `("mini-xt:TL16C550PT","TL16C550C")`, RTC, CR2032 holder, `("mini-xt:74LVC2G07","74LVC2G07")`.

- [ ] **Step 1: Generate the three new symbols with `gensym.py`** (read its header for usage; follow the existing flat-symbol style). Pin lists MUST come from `mcp__pcbparts__jlc_get_pinout` for the exact LCSC part, cross-checked against the datasheet. IS62WV51216: A0–A18, IO0–IO15, ~{CE}, ~{OE}, ~{WE}, ~{LB}, ~{UB}, VDD, GND (TSOP-44). TL16C550PT: full LQFP-48 pinout — note LQFP-48 pin numbers differ from the PLCC-44 symbol; do not copy the old 16550 symbol's numbers.

- [ ] **Step 2: Verify each new symbol**: `python3 hardware/tools/pins.py "mini-xt:IS62WV51216"` (and the other two) — output must list every pin with the datasheet's number. Fix mismatches now.

- [ ] **Step 3: Update parts.py.** Add the new entries with LCSC codes from Task 1. Delete now-dead entries: AS6C4008 + DIP-32 socket, PLCC-44 socket, DS12C887 + DIP-24 socket, and any HCT-value entry no sheet will reference after Tasks 4–9 (grep sheets at the END of the plan instead if unsure — a stale extra entry is harmless, a missing one fails `check_parts.py`).

- [ ] **Step 4: Sanity build** — `python3 hardware/tools/build.py` must still pass (sheets untouched; this catches parts.py syntax errors). Expected: `wrote project: root + 13 sheets`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add hardware/mini-xt.kicad_sym hardware/tools/parts.py
git commit -m "Symbols+parts: IS62WV51216, TL16C550CPT, I2C RTC; 3.3V LVC/HC rebinds"
```

---

### Task 3: mxbus.py — new private nets + rule reframe

**Files:**
- Modify: `hardware/tools/mxbus.py`

**Interfaces:**
- Produces: `PRIV_EXP = ["EXP_DDIR", "EXT_DRQ1", "EXT_DRQ2", "EXT_DRQ3"] + ["EXT_IRQ%d" % i for i in range(2, 9)]` — consumed by bus_mcu (Task 5) and sidecar (Task 9). Exact names: `EXP_DDIR`, `EXT_IRQ2`…`EXT_IRQ8`, `EXT_DRQ1`…`EXT_DRQ3`.

- [ ] **Step 1: Add after `PRIV_LINK`:**

```python
# Expansion-port isolation bank (sidecar <-> Bus MCU). The port's inward
# lines land on DEDICATED nets, never the internal IRQ/DRQ nets: a floating
# external line must not fight an internal driver. The soft-PIC/soft-8237
# merge EXT_* with the internal lines in firmware. EXP_DDIR: Bus MCU drives
# the port data transceiver direction (inward only for reads it knows are
# externally decoded; default outward).
PRIV_EXP = ["EXP_DDIR", "EXT_DRQ1", "EXT_DRQ2", "EXT_DRQ3"] + \
           ["EXT_IRQ%d" % i for i in range(2, 9)]
```

- [ ] **Step 2: Reframe the module docstring**: the "any soft card may use ONLY these" paragraph becomes: ISA names remain the canonical bus contract and the *firmware-portability guideline* for card sections, but it is no longer a hard schematic rule — the system is one board (spec 2026-07-14); PRIV_* groups mark motherboard side-channels for visibility, not enforcement.

- [ ] **Step 3: Validate + commit** — `python3 hardware/tools/build.py` exit 0.

```bash
git add hardware/tools/mxbus.py
git commit -m "mxbus: PRIV_EXP port nets; isolation rule -> guideline"
```

---

### Task 4: cpu_core.py — LVC boundary, single SRAM, 3.3V glue

**Files:**
- Modify: `hardware/sheets/cpu_core.py`
- Create/append: `hardware/notes/questions-cpu_core.md`

**Interfaces:**
- Consumes: `mini-xt:IS62WV51216` symbol (Task 2); Task 1 verdicts #1 (RESET path), #7 (÷3 divider choice).
- Produces: unchanged sheet PINS (the ISA contract nets); net `Y5_INT` stays sheet-internal.

Read the whole sheet first; it is the reference example and the most intricate. Changes:

- [ ] **Step 1: Boundary part swaps.** The three `mini-xt:74HCT573` (U2–U4) get value `"74LVC573A"`; the `mini-xt:74HCT245` (U5) becomes value `"74LVC245A"` (keep the HCT bodies — pinouts are identical; add the required deviation comment: `# 74LVC573A on the HCT573 body: 3.3V-powered, 5V-tolerant inputs = the V20 5V<->3.3V boundary (spec 2026-07-14)`). Their VCC power symbols change `+5V` → `+3V3`.

- [ ] **Step 2: Glue to 3.3V.** U11 (HCT125) → value `"74LVC125A"`; U6 (HCT138) → value `"74HC138"`; U7 (HCT00) → value `"74HC00"`; U12 mux keeps value `"74HC157"`. All their power symbols → `+3V3`. U13 (HCT04) is the ONE package that stays on `+5V` — it buffers V20 CLK (and RESET, per Task 1 verdict #1; if RESET is 3.3V-safe, wire `~{CPURESET}`-derived reset to the V20 directly and leave the spare gates NC). Clock dividers (HC74/HC4017 or the Task-1 fallback LVC161) → `+3V3`.

- [ ] **Step 3: Single SRAM.** Delete RAM1, RAM2, their DIP sockets' assumptions, and the SRAM#2 NAND select. Place the new chip and wire the byte-lane trick (adjust coordinates to fit the vacated area; pin names from `pins.py mini-xt:IS62WV51216`):

```python
# One 512K x16 as 1M x8 (byte-lane trick, spec 2026-07-14): word address is
# A1..A19; A0 picks the byte lane; both IO bytes tie to D0-D7 -- exactly one
# lane is ever enabled, the other tri-states.
RAM = sch.place("mini-xt:IS62WV51216", "RAM1", "IS62WV51216BLL", at=(x, y))
for i in range(19):                      # chip A0..A18 <- system A1..A19
    sch.net(RAM, "A%d" % i, "A%d" % (i + 1), kind="label", dx=-2.54)
for i in range(8):                       # both byte lanes on D0..D7
    sch.net(RAM, "IO%d" % i, "D%d" % i, kind="label", dx=2.54)
    sch.net(RAM, "IO%d" % (i + 8), "D%d" % i, kind="label", dx=2.54)
sch.net(RAM, "~{OE}", "~{MEMR}", kind="label", dx=-2.54)
sch.net(RAM, "~{WE}", "~{MEMW}", kind="label", dx=-2.54)
sch.net(RAM, "~{LB}", "A0", kind="label", dx=-2.54)      # A0=0 -> low byte
sch.net(RAM, "~{UB}", "A0_INV", kind="label", dx=-2.54)  # A0=1 -> high byte
sch.net(RAM, "~{CE}", "RAM_CE", kind="label", dx=-2.54)  # = NOT(Y5_INT)
```

Two 74HC00 gates of U7 (freed by deleting the SRAM#2 NAND) become the inverters, NAND-as-inverter (both inputs tied):

```python
# U7b: A0_INV = NAND(A0, A0); U7c: RAM_CE = NAND(Y5_INT, Y5_INT) --
# SRAM answers the full 1MB except the 0xA0000-0xBFFFF video window.
```

(wire with the existing U7 gate pins — read the current sheet for the gate-pin naming convention on the flat symbol).

- [ ] **Step 4: Decouple/socket cleanup.** Remove the second SRAM's decoupling; V20 DIP-40 socket unchanged.

- [ ] **Step 5: Validate**

Run: `python3 hardware/tools/validate_sheet.py cpu_core`
Expected: zero structural categories, "Failed to load" absent.

- [ ] **Step 6: Log decisions** (RESET path chosen, divider choice, SRAM placement) in `hardware/notes/questions-cpu_core.md`, then commit:

```bash
git add hardware/sheets/cpu_core.py hardware/notes/questions-cpu_core.md
git commit -m "cpu_core: LVC573A/245A 3.3V boundary; single 512Kx16 SRAM as 1Mx8"
```

---

### Task 5: bus_mcu.py — shed transceivers, add EXT scan

**Files:**
- Modify: `hardware/sheets/bus_mcu.py`
- Create/append: `hardware/notes/questions-bus_mcu.md`

**Interfaces:**
- Consumes: `PRIV_EXP` names from Task 3.
- Produces: sheet PINS grows by `EXP_DDIR` (output), `EXT_IRQ2..8`, `EXT_DRQ1..3` (inputs).

- [ ] **Step 1: Delete the 3× `mini-xt:74LVC245A` (loop at ~line 182) and their DIR/role logic.** Identify the DIR nets (the HCT08 U18 gates and/or dedicated MCU GPIO driving the 245s' DIR pins) — delete the gates if that's their only job. Rewire every MCU GPIO that fed a 245 B-side pin directly to the bus net the A-side carried. The MCU pin ↔ bus net mapping must be preserved 1:1 (the GPIO assignments don't change, only the transceivers vanish).

- [ ] **Step 2: 3.3V value swaps.** HCT163 counters (already value `"74HC161"`) → power `+3V3` (they latch the now-3.3V A-bus); HCT165 (U12) → value `"74HC165"`, `+3V3`; HCT244s (~line 311): these buffered 3.3V MCU outputs onto the 5V bus — delete them and wire the MCU GPIOs direct (same 1:1 rule as Step 1); HCT08/HCT04 leftovers: keep only gates with a real remaining function, at `+3V3` with HC values.

- [ ] **Step 3: EXT scan chain.** Add 2× `mini-xt:74HCT165` (values `"74HC165"`, `+3V3`) chained onto the existing IRQ shift-register chain (same clock/load nets as U12, serial-out → U12's serial-in, or chain-extend per the current arrangement — read how U12 is wired first). Inputs: `EXT_IRQ2`…`EXT_IRQ8`, `EXT_DRQ1`…`EXT_DRQ3` (10 lines across the two chips; ground unused inputs). Add one MCU GPIO → `EXP_DDIR` (pick a free GPIO; the 245 deletions freed none — they were 1:1 — so use a spare; `pins.py mini-xt:Core2350B` to see what's unassigned, and log the pick).

- [ ] **Step 4: PINS list**: add `mxbus.pin("EXP_DDIR", "output")`, and `mxbus.pin(n, "input")` for the ten EXT_* nets.

- [ ] **Step 5: Validate + commit**

Run: `python3 hardware/tools/validate_sheet.py bus_mcu` — zero structural.

```bash
git add hardware/sheets/bus_mcu.py hardware/notes/questions-bus_mcu.md
git commit -m "bus_mcu: direct 3.3V bus GPIOs (LVC245s+DIR logic deleted); EXT IRQ/DRQ scan"
```

---

### Task 6: video.py, picogus.py, audio.py — delete shifters

**Files:**
- Modify: `hardware/sheets/video.py`, `hardware/sheets/picogus.py`, `hardware/sheets/audio.py`
- Create/append: `hardware/notes/questions-<sheet>.md` per touched sheet

- [ ] **Step 1: video.py** — delete the 3× LVC245A (loop ~line 165), wire the RP2350B GPIOs direct to the bus nets 1:1 (as Task 5 Step 1). Power symbol sweep → `+3V3` for anything that was 5V-only-for-the-bus.

- [ ] **Step 2: picogus.py** — delete its LVC245s the same way, preserving the RP2040-GPIO→signal map from Task 1 verdict #6 EXACTLY (stock firmware depends on it — add a comment table of the mapping). U7 (74AHC14) / U8, U9 (74LVC00) / U10 (LVC2G06): keep any gate with a non-level-shift function (schmitt conditioning, strobe gating), now at `+3V3`; delete pure 3.3V→5V buffer gates. The RP2040 is NOT 5V-tolerant — confirm every net it now touches is 3.3V-only (they all are, post-Task 4).

- [ ] **Step 3: audio.py** — find its single LVC/shifter (grep `LVC` in the sheet); same treatment. The op-amp summing stage keeps whatever analog rail it uses today (do not rework analog).

- [ ] **Step 4: Validate each + commit**

Run: `python3 hardware/tools/validate_sheet.py video` (then `picogus`, `audio`) — zero structural each.

```bash
git add hardware/sheets/video.py hardware/sheets/picogus.py hardware/sheets/audio.py hardware/notes/questions-*.md
git commit -m "video/picogus/audio: MCUs direct on 3.3V bus, shifters deleted"
```

---

### Task 7: com_port.py, network.py, storage.py, parallel.py — 3.3V rebinds

**Files:**
- Modify: `hardware/sheets/com_port.py`, `hardware/sheets/network.py`, `hardware/sheets/storage.py`, `hardware/sheets/parallel.py`
- Create/append: per-sheet questions files

- [ ] **Step 1: com_port.py** — replace the PLCC-44 16550 (and its socket binding) with `mini-xt:TL16C550PT`, value `"TL16C550C"`, at `+3V3`, soldered (spec decision 3). Rewire pin-for-signal from the new symbol's pin names (`pins.py mini-xt:TL16C550PT`) — LQFP-48 numbering differs from PLCC-44. U6 (HCT125) → value `"74LVC125A"`, `+3V3`. MAX3241 untouched. Both COM1/COM2 INSTANCES stay.

- [ ] **Step 2: network.py** — U3 (HCT125) → `"74LVC125A"`, `+3V3`; power sweep → `+3V3` for bus-facing logic.

- [ ] **Step 3: storage.py** — value swaps, all at `+3V3`: U1 HCT04→`"74HC04"`, U2/U3 HCT08→`"74HC08"`, U4 HCT32→`"74HC32"`, U5 HCT125→`"74LVC125A"`, U6/U7/U11 HCT138→`"74HC138"`, U8 HCT245→`"74LVC245A"`, U9/U10 HCT573→`"74LVC573A"`. (LVC on the IDE-connector-facing parts: a CF adapter or drive may drive 5V back — 5V-tolerance at the external connector, same rule as the port.)

- [ ] **Step 4: parallel.py** — the DB25 is an external boundary; connector-facing parts go LVC (5V-tolerant), decode glue goes HC: U1/U2 HCT574→`"74LVC574A"`, U3 HCT244→`"74LVC244A"`, U4 HCT245→`"74LVC245A"`, U13 HCT125→`"74LVC125A"`, U10/U11 HCT32→`"74HC32"`, U12 HCT00→`"74HC00"`. All `+3V3`.

- [ ] **Step 5: Validate each + commit**

Run: `python3 hardware/tools/validate_sheet.py com_port` (then `network`, `storage`, `parallel`) — zero structural each.

```bash
git add hardware/sheets/com_port.py hardware/sheets/network.py hardware/sheets/storage.py hardware/sheets/parallel.py hardware/notes/questions-*.md
git commit -m "com/network/storage/parallel: 3.3V; TL16C550CPT soldered; LVC at external connectors"
```

---

### Task 8: RTC — delete sheet, add I2C RTC to supervisor

**Files:**
- Delete: `hardware/sheets/rtc.py`
- Modify: `hardware/sheets/supervisor.py`, `hardware/tools/build.py:53-55`
- Create/append: `hardware/notes/questions-supervisor.md`

- [ ] **Step 1:** `git rm hardware/sheets/rtc.py`; remove `"rtc"` from `SHEETS` in `build.py`. Delete the generated `hardware/sheets/rtc.kicad_sch` if present.

- [ ] **Step 2: supervisor.py** — add the I2C RTC (Task 1's pick, symbol from Task 2) on two spare RP2040 GPIOs (check current usage with `pins.py mini-xt:Pico` + the sheet; log the pins chosen):

```python
# Battery-backed timekeeping for the Bus MCU's port-0x70/71 RTC emulation
# (spec 2026-07-14): Supervisor reads it over I2C, syncs time over the UART
# link at boot; CMOS config bytes live in Supervisor flash.
RTC = sch.place("mini-xt:<RTCPART>", "U8", "<RTCPART>", at=(x, y))
sch.net(RTC, "SDA", "RTC_SDA", kind="label", dx=2.54)   # + 4.7k pull-ups to +3V3
sch.net(RTC, "SCL", "RTC_SCL", kind="label", dx=2.54)
# CR2032 holder on VBAT; 100nF on VDD; crystal per datasheet if the pick
# needs an external 32.768kHz (prefer a pick with integrated crystal).
```

`RTC_SDA`/`RTC_SCL` are supervisor-internal nets (not in PINS).

- [ ] **Step 3: Full build** (sheet list changed): `python3 hardware/tools/build.py` — expected `wrote project: root + 12 sheets`, exit 0. Then `python3 hardware/tools/validate_sheet.py supervisor` — zero structural.

- [ ] **Step 4: Commit**

```bash
git add -A hardware/sheets/ hardware/tools/build.py hardware/notes/questions-supervisor.md
git commit -m "RTC: DS12C887 sheet deleted; I2C RTC + coin cell on Supervisor"
```

---

### Task 9: sidecar.py — buffered expansion port

**Files:**
- Modify: `hardware/sheets/sidecar.py`
- Create: `hardware/notes/questions-sidecar.md`

**Interfaces:**
- Consumes: `PRIV_EXP` net names (Task 3): `EXP_DDIR`, `EXT_IRQ2..8`, `EXT_DRQ1..3`.
- Produces: sheet PINS = existing ISA set MINUS inward lines it no longer passes through (IRQ2–8, DRQ1–3 leave the ISA pin list) PLUS the PRIV_EXP pins. IOCHRDY/`~{IOCHCK}` stay in PINS (driven onto the internal nets by open-drain buffers).

The header keeps the standard pinout via `isa_conn.place_header` — but its bus-side nets become port-local nets (prefix `X_`, e.g. `X_A0`, `X_D3`, `X_IRQ5`) via the `remap=` argument, with the buffer bank between `X_*` and the internal nets:

- [ ] **Step 1: Remap the header.** Extend the existing `remap={"+5V": "+5V_ISA"}` so every signal pin maps to its `X_`-prefixed name (build the dict from `isa_conn.ISA_PINS` programmatically).

- [ ] **Step 2: Outbound bank.** 3× `mini-xt:74LVC245A` (A0–A19 + BALE, AEN, CLK, OSC) with DIR strapped outward, plus 2× `mini-xt:74HCT244` value `"74LVC244A"` (MEMR̄/MEMW̄/IOR̄/IOW̄, RESET_DRV, TC, DACK̄1–3, REFRESH̄ = 10 lines). All `+3V3`. Each line: internal net in, `X_*` net out.

- [ ] **Step 3: Data transceiver.** 1× `mini-xt:74LVC245A`, A-side D0–D7, B-side X_D0–X_D7, DIR = `EXP_DDIR` (default outward — add a 10k pull-down/up matching the DIR polarity for drive-outward so the port is safe before Bus MCU boot; check the 245 DIR pin sense and say which in a comment).

- [ ] **Step 4: Inward lines.** `X_IRQ2..8` → `EXT_IRQ2..8` and `X_DRQ1..3` → `EXT_DRQ1..3` through 2× `mini-xt:74HCT244` value `"74LVC244A"` at `+3V3` (5V-tolerant inputs), with 100k pull-DOWNs on every `X_` input so unplugged lines read 0. IOCHRDY and `~{IOCHCK}`: one `mini-xt:74LVC2G07` (open-drain) per line driving the INTERNAL net from the `X_` line, pull-ups on the X_ side — wired-AND semantics, no contention:

```python
# X_IOCHRDY low (card wants wait) -> pull internal IOCHRDY low; hi-Z otherwise.
# X_~{IOCHCK} low -> pull internal ~{IOCHCK} low. LVC2G07 = open drain, 5V-tol.
```

- [ ] **Step 5: PINS update** per the Interfaces block above. Keep fuse/TVS/bulk caps unchanged. Update the sheet docstring + `sch.text` notes: this is now the board's ONLY 5V-compatible real-ISA attachment point; external bus-master cards unsupported (fixed-direction control buffers).

- [ ] **Step 6: Validate + full build + commit**

Run: `python3 hardware/tools/validate_sheet.py sidecar` — zero structural. Then `python3 hardware/tools/build.py` — exit 0 (EXT_* nets must resolve against bus_mcu's pins).

```bash
git add hardware/sheets/sidecar.py hardware/notes/questions-sidecar.md
git commit -m "sidecar: isolation/buffer bank -- 5V-compatible ISA expansion port"
```

---

### Task 10: Docs, netlist verification, final build

**Files:**
- Modify: `docs/xt-mcu-sbc-design.md`, `CLAUDE.md`, `hardware/notes/jlcpcb-sourcing.md`, `hardware/notes/open-questions.md`, `hardware/sheets/card_video.py` + `hardware/sheets/card_isatest.py` (docstrings only)
- Verify: `hardware/mini-xt.net`

- [ ] **Step 1: Netlist ground-truth checks** (after `python3 hardware/tools/build.py`):

```bash
# single SRAM, byte-lane: D0 must include RAM IO0 AND IO8
grep -A30 '(net .*"D0"' hardware/mini-xt.net
# boundary: A8 net spans cpu_core latch + bus_mcu MCU pin + sidecar buffer, no LVC245 in video/picogus
grep -A40 '(net .*"A8"' hardware/mini-xt.net
# EXT nets span sidecar + bus_mcu
grep -A10 '(net .*"EXT_IRQ5"' hardware/mini-xt.net
# no DS12C887, no AS6C4008 anywhere
grep -c 'DS12C887\|AS6C4008' hardware/mini-xt.net   # expect 0
```

- [ ] **Step 2: Parts coverage**: `python3 hardware/tools/check_parts.py` — every component resolves to an LCSC part (or is on the documented sourced-elsewhere list).

- [ ] **Step 3: Component-count sanity**: count comps in the netlist (same method as the spec's estimate); record the real number in the spec's "Component-count estimate" section (replace `~350` with the actual).

- [ ] **Step 4: Cards rebuild**: `python3 -c 'import sys;sys.path.insert(0,"hardware/tools");import build;build.build_cards()'` — both cards still build clean; update the two card docstrings to say they target the buffered expansion port (genuine 5V ISA cards, keep their own shifters).

- [ ] **Step 5: Doc updates**:
  - `docs/xt-mcu-sbc-design.md`: §1 table (RTC row, RAM row, MCU/COM rows), §2 portability contract → guideline, block diagram (one SRAM, port bank, no per-card shifters), §4.1 (single-chip decode), §4.2 rewritten (boundary-at-V20 + port bank), §4.3 (buffered port, EXT_* merge, bus-master limitation), §7/power (3.3V budget).
  - `CLAUDE.md`: isolation rule → guideline; socket policy (V20 only); 100×100 constraint → one large board; sub-boards-standalone rule → dev cards target the expansion port; SRAM/COM/RTC part notes.
  - `hardware/notes/jlcpcb-sourcing.md`: delete dead HCT substitution rows; add the new picks table from Task 1; keep sourced-elsewhere list updated.
  - `hardware/notes/open-questions.md`: log the redesign decisions (one entry pointing at the spec).

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "Docs: 3.3V single-board redesign — design doc, CLAUDE.md, sourcing notes"
```

---

## Self-Review Notes

- Spec coverage: decisions 1–8 map to Tasks 4 (boundary, SRAM), 5–7 (shifter deletion, 3.3V, TL16C550CPT), 8 (RTC), 9 (port, dev cards unchanged + Task 10 docstrings), 3+10 (rule downgrade, docs). Verification checklist → Task 1.
- Net-name consistency: `EXP_DDIR`, `EXT_IRQ2..8`, `EXT_DRQ1..3` defined once (Task 3), consumed Tasks 5 and 9 with identical spelling. `RAM_CE`, `A0_INV`, `Y5_INT` are cpu_core-internal.
- Known drift from spec: port bank is ~9 packages (3+2 out, 1 data, 2 in, 2×LVC2G07... the 2G07s may be one dual package) not "~6" — contention-safe IRQ/DRQ/wired-AND handling costs the extra; spec's count estimate updated in Task 10 Step 3.

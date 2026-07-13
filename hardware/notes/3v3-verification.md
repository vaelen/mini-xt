# 3.3V single-board redesign — plan-stage verification

Research for `docs/superpowers/specs/2026-07-14-3v3-single-board-design.md` §"Plan-stage
verification checklist". Pure research, no sheet edits. Consumed by Task 2 onward.

All seven checks: **7/7 PASS** in the sense that none blocks the redesign — but checks 1
and 7 turn up two concrete part/wiring corrections downstream tasks must apply (below).

---

## Check 1 — µPD70108 (V20) DC characteristics: Vih, CLK, RESET

**VERDICT: PASS**, with a correction to the design doc's assumption.

Source: NEC `IC-3552A` data sheet for the µPD70108H/70116H (V20HL/V30HL — CMOS
re-spin of the plain V20; NEC's own "Differences" table confirms only *operating
frequency/voltage* differ between the H and non-H parts, not pin electrical
structure, so its DC table is the best primary source available online for the
V20's input thresholds; the plain non-H datasheet's electrical tables were only
available as non-OCR-able scans). §9.1 "WHEN VDD = 5V ± 10%", DC CHARACTERISTICS
table (p.82):

| Symbol | Conditions | Min | Max |
|---|---|---|---|
| Vih | Other than (1) READY, (2) HLDRQ | **2.2 V** | Vdd+0.5 |
| Vih | (1) READY | 0.6·Vdd (=3.0V) | Vdd+0.5 |
| Vih | (2) HLDRQ (DIP only) | 0.6·Vdd (=3.0V) | Vdd+0.5 |
| Vil | all | −0.5 | 0.8 V |
| **Vkh** (CLK input high) | — | **0.8·Vdd = 4.0 V** | Vdd+1.0 |
| Vkl (CLK input low) | — | −0.5 | 0.15·Vdd |

**RESET is not listed as an exception** — it uses the general-input Vih = 2.2V min,
*not* the clock-input class (Vkh). A 3.3V LVC output (Vout high comfortably ≥2.4–3.0V
even loaded) clears 2.2V with margin, so **RESET can be driven directly from 3.3V
logic — it does NOT need the 5V HCT04 buffer**, contradicting the design doc's
hedge ("RESET if flagged"). Only **CLK** needs the buffer: Vkh min = 0.8×5V = 4.0V,
unreachable from a 3.3V rail (max 3.3V < 4.0V). This confirms the design's one
5V HCT04 package is sized correctly (CLK only) and identifies a small simplification
(RESET can lose its buffer gate) for whichever task wires reset distribution.

Datasheet: NEC IC-3552A (µPD70108H/70116H), fetched via
`https://docs.rs-online.com/8dd4/0900766b8002a664.pdf`-equivalent mirror
(`datasheets.chipdb.org/NEC/V20-V30/IC-3552A.PDF`), §9.1 p.82, §1 differences table p.10.

---

## Check 2 — IS62WV51216BLL-55TLI: byte-lane trick + 0-wait timing at 7.16 MHz

**VERDICT: PASS.**

**LB̄/UB̄ gate the output drivers (byte-lane trick is valid).** ISSI datasheet
(`https://www.issi.com/WW/pdf/62WV51216ALL.pdf`, TRUTH TABLE p.3) Read rows:

| WE̅ | CS1̅ | CS2 | OE̅ | LB̅ | UB̅ | I/O0-7 | I/O8-15 |
|---|---|---|---|---|---|---|---|
| H | L | H | L | L | H | D_OUT | High-Z |
| H | L | H | L | H | L | High-Z | D_OUT |
| H | L | H | L | L | L | D_OUT | D_OUT |

Deasserting LB̅ (high) forces I/O0-7 high-Z regardless of CS/OE state; same for UB̅
on I/O8-15. This is exactly the mini-xt scheme: **A0 → LB̅ direct, A0 → inverter →
UB̅**, both byte groups wired to the same D0-7 — only one group ever drives.
Supply range confirmed 2.5–3.6V (datasheet p.2, "BLL" row) — 3.3V is mid-range, not
an edge case.

**Timing closes with wide margin.** V20 AC characteristics (same NEC datasheet,
§9.1, -10 grade, Vdd=5V, p.83): at the actual 7.16 MHz operating clock (tCYK ≈ 140 ns,
vs. the -10 grade's 100 ns *minimum* rated tCYK — i.e. comfortably under-clocked):
- tRR (RD̅ low-level width) = 2·tCYK − 40 = **240 ns min**
- tSDK (data setup before sampling CLK↓) = 10 ns min
- ⇒ usable "OE asserted → data must be valid" budget = 240 − 10 = **230 ns**
  (close to the brief's ~200 ns estimate, slightly more generous)

SRAM's own critical-path term is **tDOE (OE access time) = 25 ns max** at the -55
grade (ISSI datasheet, READ CYCLE SWITCHING CHARACTERISTICS, p.6) — since
/OE = MEMR̄ is wired direct (no gate), this is the whole critical path: 25 ns
consumed of a 230 ns budget, **~205 ns of slack**.

The new design's two added gates — `/CE = INV(Y5)` and `/UB = INV(A0)` via one
74HC00 package — are **not on this critical path**: both CE and UB settle from
address-latch time (~T1, start of the 560 ns/4-T-state bus cycle), while OE
(MEMR̄) doesn't assert until mid-cycle. Even a pessimistic 74HC00 gate delay at
3.3V (Nexperia `74HC_HCT00.pdf` Table 7: tpd max = 23 ns@4.5V / 115 ns@2.0V,
no 3.3V row published; conservatively bounding ~40 ns at 3.3V) lands well inside
the address-setup slack, not the OE-to-data slack. This matches the **old
2×AS6C4008 design's already-accepted budget**: `docs/xt-mcu-sbc-design.md` §4.1
already routes SRAM#2's /CE through "one 74HC00 gate" (a NAND) at the same
7.16 MHz/55 ns-SRAM operating point and calls it 0-wait — the new design adds
one *comparable* gate (an inverter) to a *different, non-critical* signal (/UB),
so it is no worse.

Sources: ISSI `62WV51216ALL.pdf` (truth table p.3, timing p.6); NEC IC-3552A
§9.1 AC characteristics p.83; Nexperia `74HC_HCT00.pdf` Table 7 (dynamic
characteristics); `docs/xt-mcu-sbc-design.md` §4.1 (old-design budget, quoted above).

---

## Check 3 — TL16C550C at 3.3V, LQFP-48 (PT) pinout, JLC stock

**VERDICT: PASS for electrical spec; sourced-elsewhere for stock** (per brief's own
fallback instruction).

TI datasheet `TL16C550C` (SLLS177I, rev. March 2021 — current, fetched directly
from `ti.com/lit/ds/symlink/tl16c550c.pdf`):
- §5.2 "Recommended Operating Conditions (Low Voltage - 3.3 nominal)": VCC
  3.0–3.6V (nom 3.3V), oscillator/clock speed max **14.9 MHz** — comfortably
  covers the design's 1.8432 MHz crystal.
- §5.5 "Electrical Characteristics (Low Voltage - 3.3V nominal)" is a fully
  populated table (VOH/VOL/leakage/Icc/capacitance) — 3.3V is an
  officially-supported, characterized operating point, not an edge case.
  Icc max = **8 mA** at Vcc=3.6V (used directly in check 5's budget).
- §4 "Pin Configuration and Functions", Table 4-1 gives the **NO.PT** column
  (LQFP-48) pin-by-pin alongside NO.N (DIP-40)/NO.FN(PLCC-44) — confirmed
  distinct from the DIP-40 numbering the existing `mini-xt:16550` custom symbol
  uses (matches the pre-existing parts.py note that a pin remap is needed at
  layout; this task doesn't remap it, just confirms the table exists and is
  authoritative for whoever does).

**JLC stock: both TL16C550CPTR (C181382) and TL16C550CPTRG4 (C2653207) show
0 units** in `jlc_stock_check` (live API), package LQFP-48(7×7), $3.30/$3.66
1-piece price when available. Per the brief's own instruction ("If JLC has no
stock, put it on the sourced-elsewhere list like the V20"): **TL16C550CPT is
sourced-elsewhere** (TI direct / Mouser / Digi-Key), alongside the V20 and the
two SRAM sockets, in `hardware/notes/jlcpcb-sourcing.md`'s "NOT available at
JLC" list. (The PLCC-44 `TL16C550CIFNR`, C2653193, does show 10 in stock at
JLC if a socketed fallback is ever wanted, but decision #3 in the spec is
soldered LQFP-48, not socketed.)

Sources: TI `tl16c550c.pdf` (SLLS177I) §4 Table 4-1, §5.2, §5.5;
`mcp__pcbparts__jlc_stock_check` query "TL16C550CPTR" (2026-07-14).

---

## Check 4 — RP2350B GPIO 5V-tolerance conditions

**VERDICT: PASS.**

Raspberry Pi RP2350 datasheet (`RP-008373-DS-2-rp2350-datasheet.pdf`, official
mirror), §14.8.2 pin-type legend, exact quote:

> "Fault Tolerant Digital. These pins are described as Fault Tolerant, which in
> this case means that very little current flows into the pin whilst it is
> below 3.63 V and IOVDD is 0 V. Additionally, they will tolerate voltages up
> to 5.5 V, provided IOVDD is powered to 3.3 V."

and the feature-list summary (p.1): "GPIOs are 5V-tolerant (powered) and
3.3V-failsafe (unpowered)". All **Bank 0 GPIOs (the User IO bank, GPIO0–47 on
the QFN-80/RP2350B package)** use this "Digital IO (FT)" pad type — this is the
bank that carries every bus-facing signal on `bus_mcu`/`video` (RD̄, HLDA, ALE,
MEMR̄/MEMW̄, IOR̄/IOW̄, D0-7, A0-19 sensed lines, etc.), so **every pin that sees
a raw V20 5V output directly is FT and safe, condition: IOVDD powered at 3.3V**
(true for the whole board once the buck is up — no sequencing hazard as long as
the RP2350B's own 3V3 rail comes up with/before the V20's 5V rail, which it
does since both derive from the single 5V input: +5V direct to V20, +5V→buck→
+3V3 to the RP2350Bs is a fraction of a ms slower, and FT pins additionally
tolerate ≤3.63V with *no* IOVDD present per the same quote — no damage risk
during power-up either way).

**Caveat, not applicable here:** the QSPI IO bank (flash/PSRAM pins) uses a
*different, non-FT* pad macro (datasheet explicitly: "This issue doesn't
affect the QSPI pads, which use a different pad macro without the faulty
circuitry" — a reference to an erratum, but confirms the QSPI bank is
electrically distinct). Nothing in mini-xt ties a 5V signal to QSPI pins, so
this doesn't affect the design, but it's worth remembering if a future GPIO
reassignment ever considers routing a bus signal through the flash pins.

Source: Raspberry Pi RP2350 datasheet §14.8.2.2 (pin type legend, p.1367 of the
fetched PDF) and feature list p.1.

---

## Check 5 — 3.3V buck re-budget

**VERDICT: PASS — fits with wide margin, no upsize needed.**

Buck: `hardware/sheets/power.py` U2 = **TPS563200** (TI datasheet confirms:
4.5–17V input / **3A synchronous buck**, SOT-23-6, 650 kHz), configured 5V→3.3V
via a 33k/10k feedback divider (0.768V×(1+33/10) = 3.30V, matches the sheet's
own comment). Sheet's inductor (parts.py: FHD4020S-2R2MT, rated **4.8A**) and
input/output caps are already sized to the datasheet's typical application.

**Estimated worst-case load** (engineering estimate — no per-part current
measurement exists yet; flagged so a bring-up measurement is still worthwhile):

| Item | Count | Each | Subtotal | Basis |
|---|---|---|---|---|
| RP2350B (Bus MCU, Video MCU) | 2 | ~80 mA | 160 mA | dual-core + PIO active, conservative padding over published Pico 2 current figures |
| RP2040 (Supervisor, PicoGUS) | 2 | ~60 mA | 120 mA | dual-core + USB/flash/PSRAM active, conservative padding over RP2040 datasheet typical run current |
| IS62WV51216BLL SRAM | 1 | 30 mA | 30 mA | ISSI datasheet active Icc (also the figure the brief itself cites) |
| TL16C550C UART | 2 | 8 mA | 16 mA | **TI datasheet §5.5, Icc max @ Vcc=3.6V** (check 3) |
| MAX3241 (COM1/COM2) | 2 | ~5 mA | 10 mA | conservative padding over typical RS-232 transceiver active current |
| All 74HC/74LVC glue board-wide (~40-50 pkgs: latches, buffers, mux, decode, dividers, CB3T3257/3245 FET switches) | ~45 | ~3 mA | ~150 mA | conservative average incl. CPD switching current at ~14 MHz, not just static Iq |
| **Total (worst case)** | | | **≈ 486 mA** | |

486 mA is **~16% of the TPS563200's 3A rating** — over 6× headroom. Even
doubling every estimate (e.g. MCUs under heavy DMA/PIO load, more glue than
counted) lands at ~1A, still only ~33% of budget. **Verdict: fits; do not
upsize.**

**Open question logged for the sheet-rewiring task (not resolved here):**
`hardware/sheets/picogus.py` currently regulates its own 3.3V rail (`3V3_PGUS`)
locally via an AMS1117-3.3 fed from `+5V` — a separate supply from the main
board's `+3V3`/TPS563200. The budget above conservatively assumes PicoGUS's
MCU joins the *main* 3.3V bus's load (worst case for this check); whoever
rewires `picogus.py` for the unified 3.3V bus should decide whether to keep
the local AMS1117-from-5V (simplest, no sheet change) or delete it and feed
`3V3_PGUS` from the shared `+3V3` rail directly (one fewer LDO, but then
its current genuinely lands on the main buck as budgeted above). Either way
the buck has room.

Sources: `hardware/sheets/power.py` (read directly); TI `TPS563200` product
page (3A, 4.5–17V input, confirmed via WebSearch of TI's own datasheet
summary); ISSI SRAM datasheet (check 2); TI TL16C550C datasheet (check 3).

---

## Check 6 — PicoGUS GPIO map (must be preserved exactly)

**VERDICT: N/A pass/fail — map documented below for Task 6.**

Read `hardware/sheets/picogus.py` in full. The RP2040's `gpio_map` list
(lines 83–93) plus the fixed pin assignments, translated through the two
signal-shifting stages (CB3T3257 address/data mux U4/U5, CB3T3245 U6, LVC2G06
U10) to their ultimate ISA-bus-facing meaning:

| GPIO | Sheet net | ISA-facing signal | Path / notes |
|---|---|---|---|
| 8,9,11-16 | AD0-AD7 | **A0-A7 / D0-D7** (time-shared) | through U4/U5 (CB3T3257 2:1 FET mux), select = `ADS` (GPIO39), gate = `~{BUSOE}` |
| 17 | RA8 | **A8** (address only, no mux — ISA only has 8 data bits) | through U6 (CB3T3245), 1A2→1Y2 |
| 18 | RA9 | **A9** | through U6, 1A3→1Y3 |
| 6 | ~{RIOW} | **~{IOW}**, qualified | via U7/U8 gates: masked during DMA (`AEN`) unless `DACK` (this channel) asserted |
| 7 | ~{RIOR} | **~{IOR}**, qualified | same masking as above |
| 30 | ~{RDACK} | **~{DACK1} or ~{DACK3}** (whichever is jumpered, J1) | senses the jumpered DMA ack line |
| 31 | RTC_LS | **TC** (ISA terminal count, input) | through U6, 1A0→1Y0 |
| 32 | RIRQ | **IRQ5** (output, hardwired — the free line) | through U6, drives 2A1→2Y1 |
| 34 | RDRQ | **DRQ1 or DRQ3** (output, jumpered, J1) | through U6, drives 2A0→2Y0 |
| 38 | RIOCHRDY | **IOCHRDY** (output, open-drain) | through U10 (74LVC2G06 open-drain buffer — stays regardless of voltage domain, needed for wired-AND semantics) |
| 39 | ADS | *(internal only — mux select/timing, not an ISA signal itself)* | drives U4/U5/U9 select/latch logic |
| 26 | RUN | *(internal — BUSOE-latch enable gating, see U9)* | not ISA-facing |
| 2,3,4,5 | SPI_RX/~{SPI_CS}/SPI_SCK/SPI_TX | *(not ISA — APS6404L sample RAM SPI)* | unaffected by bus voltage domain |
| 27,28,29 | DIN,BCK,LRCK | *(not ISA — PCM5102A I2S DAC)* | unaffected |
| 35 | LED_A | *(not ISA — status LED)* | unaffected |
| 36,37,40 | RV_DATA,RV_CLK,MIDI_TX | *(not ISA — documented dangling, wavetable/MIDI removed 2026-07-11)* | unaffected |
| 41 | — | tied **GND** | see discrepancy note below |
| SWCLK/SWDIO | PGUS_SWCLK/SWDIO | *(debug, not ISA)* | unaffected |

**Which chips are pure voltage-safety vs. functional and must stay regardless
of the 3.3V redesign:**
- **U4/U5 (CB3T3257) are a 2:1 time-division mux**, not primarily a level
  shifter — the RP2040 only has 8 GPIOs for AD0-7 and must time-share them
  between address and data roles (the `ADS`/`~{BUSOE}` scheme). This is a
  firmware/hardware contract independent of bus voltage and **must be
  preserved as-is** even at 3.3V (deleting it would require an 8-pin GPIO
  budget increase the RP2040 doesn't have).
- **U6 (CB3T3245) is pure buffering/level-shift** for 6 single-direction
  signals (A8/A9 in, TC in, IRQ5/DRQ out) with no muxing — this is the piece
  that becomes **removable** once the bus is 3.3V-native (direct GPIO-to-net
  wiring), matching the spec's "PicoGUS (−3 …)" component-count note.
- **U10 (74LVC2G06) stays** — it's an open-drain driver (needed for
  IOCHRDY's wired-AND semantics on a shared bus), not a level shifter, and
  is already 3.3V-native.

**Discrepancy found (flag for whoever next edits `picogus.py`, not fixed
here per "research only"):** the sheet's own module docstring says *"GPIO29
grounded = the chip-down board-detect strap"*, but the actual `gpio_map` code
ties **GPIO29 to `LRCK`** (I2S) and **GPIO41 to `GND`** instead. The code (not
the stale comment) is presumably correct per CLAUDE.md's "generated files are
build outputs, the code is truth" — but the docstring should be corrected in
the same commit that next touches this file, so nobody re-derives the wrong
strap pin from the comment.

---

## Check 7 — Clock divider fmax at 3.3V, 14.31818 MHz input

**VERDICT: FAIL for HC-grade at 3.3V on both dividers — use LVC-grade for both.**

**Correction to the check's own premise:** the design doc's summary/block-diagram
(§1, §5.1, table p.752 of `docs/xt-mcu-sbc-design.md`) and this task's brief both
describe the ÷3 stage as "74HC4017" — but `hardware/notes/open-questions.md`
("Post-review change: standardize 5V glue on 74HCT") already records that the
÷3 was changed from 74HC4017 to a **74HC161 preset-to-3 scheme** (no HCT-grade
4017 exists at JLC) *before* this 3.3V effort began, and the currently-generated
`hardware/sheets/cpu_core.py` (U9, line 217) implements exactly that: a
`mini-xt:74HCT163` symbol with value override `"74HC161"`, preset-loaded to 13
(1101) and reloading on terminal count. **The part actually needing verification
is 74HC161, not 74HC4017** — coincidentally already the same *style* of part
(binary counter preset-reload) as the brief's own suggested fallback, just still
at HC (not LVC) grade. U8 (line 204) is the ÷2, a genuine `mini-xt:74HCT74`
(HCT-grade today, since the whole clock tree currently lives on the 5V rail).

Both parts move to the 3.3V rail in this redesign, so the question is fmax at
3.3V for each. Neither Nexperia datasheet publishes a 3.3V row (only 2.0V/
4.5V/6.0V) — interpolating between the two guaranteed worst-case bracketing
points (-40 to +85°C column, the commercial/industrial range both datasheets
guarantee):

| Part | fmax min @ 2.0V | fmax min @ 4.5V | Linear interp. @ 3.3V | vs. 14.318 MHz |
|---|---|---|---|---|
| 74HC74 (÷2) | 4.8 MHz | 24 MHz | ≈ 14.8 MHz | **~3% margin — unsafe** |
| 74HC161 (÷3, the actual part) | 3.6 MHz | 18 MHz | ≈ 11.1 MHz | **below the clock — fails** |

(Nexperia `74HC_HCT74.pdf` Table 8 and `74HC161.pdf` "fmax, CP" row, both
-40 to +85°C Min columns.) The manufacturer does not guarantee either number
at 3.3V; the true curve is likely concave (most of the Vcc→fmax gain happens
between 2–4.5V, diminishing above), so real silicon may do somewhat better than
the naive linear interpolation — but that's not a number a datasheet backs, and
74HC161's own bracketing points are unambiguously worse than 74HC74's, putting
even the optimistic case in doubt. Per the brief's own <20 MHz safety bar,
**both fail** — this is not a "close enough" case.

**Fix: move both dividers to LVC-grade**, already confirmed in stock at JLC:
- **74LVC74A** (÷2): C6100, TSSOP-14, Nexperia, 7807 in stock, $0.296. Datasheet
  clock frequency spec 250 MHz — no margin question at 14.318 MHz.
- **74LVC161** (÷3, same preset-to-3 topology, direct drop-in): C548136,
  TSSOP-16, Nexperia, spec'd 150 MHz / 1.2–3.6V — comfortable margin. **Stock is
  thin (100 units at time of writing) — re-verify before ordering.**

This is a genuine part change for whichever task rewires `cpu_core.py`'s clock
tree (U8/U9), not a blocker for the overall redesign — logged here so that
task doesn't accidentally leave U8/U9 on HC-grade bodies once they move to
the 3.3V rail.

Sources: Nexperia `74HC_HCT74.pdf` Table 8 (dynamic characteristics, fmax
row); Nexperia `74HC161.pdf` (dynamic characteristics, fmax row);
`hardware/sheets/cpu_core.py` lines 195–264 (current implementation, read
directly); `hardware/notes/open-questions.md` "Post-review change: standardize
5V glue on 74HCT" (÷3 history); `docs/xt-mcu-sbc-design.md` (stale 4017
references); `mcp__pcbparts__jlc_get_part` for both LCSC codes.

---

## Parts picks table

All LCSC codes confirmed via `jlc_search`/`jlc_get_part`/`jlc_stock_check`
(2026-07-14). "Stock" is the live count at query time; **thin** flags anything
worth re-checking before an order.

| Role | MPN | LCSC | Package | Price (1pc) | Stock |
|---|---|---|---|---|---|
| SRAM 512K×16 | IS62WV51216BLL-55TLI | C11315 | TSOP-II-44 | — | deep (existing pick, re-confirmed 2.5–3.6V, 55ns, byte-lane valid — check 2) |
| Octal latch, 3.3V, 5V-tol inputs | 74LVC573APW,118 | C6096 | TSSOP-20 | $0.28 | 18,681 |
| Octal buffer, 3.3V, 5V-tol | 74LVC244APW,118 | C6079 | TSSOP-20 | $0.29 | 23,742 |
| Octal D-FF for parallel.py | 74LVC574AT20-13 | C842658 | TSSOP-20 | $0.34 | 88 **thin** |
| Quad tri-state | 74LVC125AD,118 | C6057 | SOIC-14 | $0.19 | 17,935 |
| Open-drain dual buffer (IOCHRDY/IOCHCK̄) | 74LVC2G07GW,125 | C24478 | SOT-363-6 | $0.24 | 6,631 |
| 74HC00 (NAND, 3.3V re-buy) | 74HC00D | C699445 | SOIC-14 | $0.27 | 1,108 |
| 74HC04 (inverter, 3.3V re-buy) | 74HC04D | C86613 | SOIC-14 | $0.08 | 28,720 |
| 74HC32 (OR, 3.3V re-buy) | 74HC32D | C52140395 | SOP-14L (verify SOIC-14 footprint match) | $0.15 | 3,904 |
| 74HC125 (tri-state buf, 3.3V re-buy) | 74HC125D | C52140399 | SOP-14L | $0.15 | 11,602 |
| 74HC138 (3:8 decoder, 3.3V re-buy) | 74HC138D,653 | C5602 | SOIC-16 | $0.20 | 42,420 |
| 74HC244 (octal buf, 3.3V re-buy) | 74HC244D | C52140409 | SOP-20L | $0.25 | 1,697 |
| 74HC245 (octal xcvr, 3.3V re-buy) | 74HC245D | C2675537 | SOIC-20-300mil | $0.65 | 912 |
| 74HC157/161/165/08/02 (3.3V re-buy) | *(unchanged)* | C5609/C5610/C5613/C5593/C5588 | — | — | existing parts.py codes already HC-grade, keep as-is |
| ÷2 divider — **use LVC, not HC** (check 7) | 74LVC74APW,118 | C6100 | TSSOP-14 | $0.30 | 7,807 |
| ÷3 divider fallback (check 7, mandatory) | 74LVC161PW,118 | C548136 | TSSOP-16 | $0.72 | 100 **thin** |
| UART | TL16C550CPTR | C181382 | LQFP-48 | $3.30 | **0 — sourced elsewhere** (TI/Mouser/Digi-Key; see check 3) |
| UART (socketed fallback, if ever needed) | TL16C550CIFNR | C2653193 | PLCC-44 | $7.86 | 10 |
| I2C RTC | PCF8563T/5,518 | C7440 | SO-8 | $0.59 | 166,556 — **preferred** library, deepest stock/cheapest of all RTC options checked |
| CR2032 holder | CR2032-BS-6 | C22363833 | SMD | $0.23 | 13,541 |

Notes:
- 74HC32/125/244/245 picks above come from smaller-name fabs (MDD/Toshiba)
  since the same Nexperia-branded parts either aren't stocked or are thin;
  all confirmed ≥2V-6V supply range in their JLC listings, compatible with
  the existing SOIC/SOP footprint conventions in `parts.py`.
- 74LVC161 and 74LVC574A are both thin (100/88 units) — flag for re-check
  immediately before BOM lock, same caution `parts.py`'s docstring already
  applies to TL16C550/DB25/MAX3241/TPS563200.

## Self-review (would a skeptical EE accept this?)

- Every verdict above cites a specific datasheet, section, table, or exact
  quoted sentence — no check was answered from memory alone. Two datasheets
  (V20 electrical spec, RP2350 5V-tolerance wording) required downloading the
  PDF via `curl`/direct fetch and `pdftotext`/page-range `Read` because
  `WebFetch` couldn't OCR the scanned/compressed originals; the resulting
  quotes are verbatim from the extracted text.
- Two findings go beyond a yes/no check and materially affect downstream
  tasks: (1) RESET doesn't need the 5V HCT04 buffer, only CLK does (check 1);
  (2) the ÷3 divider is *already* 74HC161, not 74HC4017 as both the spec and
  the design doc's summary still say, and *both* dividers fail the 3.3V fmax
  margin bar and need LVC-grade replacements (check 7). Both are flagged
  clearly above rather than buried.
- Check 5's budget is explicitly labeled an engineering estimate, not a
  measurement — the two hard numbers in it (SRAM 30mA, UART Icc 8mA) are
  datasheet-cited; the MCU/glue figures are conservatively padded and the
  verdict holds even if those estimates are doubled.
- Check 6 required tracing signal flow through 3 chips (U4/U5/U6) by hand
  from the sheet source rather than trusting the module docstring, which
  turned up a real discrepancy (GPIO29 vs. GPIO41) — flagged, not silently
  "fixed" (out of scope for a research-only task).

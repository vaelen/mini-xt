# Design review — 2026-07-03

> **Status update (same day):** ALL CRITICAL AND HIGH items are FIXED —
> C1–C5, H1–H8 (H2 in full: strobe/DEN pulls + IOCHRDY/~IOCHCK pull-ups,
> IRQ2–9 pull-downs, ~DACK2/3 pull-ups, AEN fixed-drive + pull-down).
> See "Fixes applied" at the end of this file. M1–M8 and the LOW/toolchain
> items remain open. The overturned per-sheet decisions have correction
> notes appended in their questions-*.md files.

Full-project review (docs + generated schematics + toolchain). Findings ranked
by severity; each has file:line, the defect, and a suggested fix. The
interface-fidelity waiver (open-questions Q2/Q10) was respected — nothing below
is a missing-passive or expected-ERC-noise item.

Cross-checked clean: clock tree topology, SRAM decode ('138+NAND, Y5 internal),
memory map, video-card ISA isolation, TPS563200 divider, com_port 10-bit decode
and MAX3241 DTE mapping, parallel decode + control-bit inversions, storage
Chuck-latch gating and CF True-IDE strapping, isa_conn 60-pin map vs standard
8-bit ISA, sidecar/card J_IN↔J_OUT pass-through, card_isatest transceiver
directions and shift chains, RTC Intel-mode strap + decode + IRQ8 inversion.

---

## CRITICAL — the machine cannot boot as drawn

### C1. SRAM /OE and /WE wired to raw V20 ~RD/~WR instead of ~MEMR/~MEMW
`sheets/cpu_core.py:148`. The doc (§4.1) requires `/OE = MEMR̄, /WE = MEMW̄`;
its "no I/O-cycle qualification needed" argument depends on it. As drawn:
every `OUT` also writes SRAM at the port address (latched A19=0 asserts SRAM#1
/CE during I/O cycles); every `IN` makes SRAM fight the I/O device on D0–D7;
and during Bus-MCU master cycles the V20 floats ~RD/~WR so the shadow-load
**cannot write SRAM at all** — no boot. Fix: wire to `~{MEMR}`/`~{MEMW}`.

### C2. Reset chain unimplemented and wrong polarity
`sheets/cpu_core.py:186-199`. U15 placed with only power; nets `V_RESET` and
`PWRGOOD` dangle; cpu_core's `RESET_DRV` has no in-sheet driver. The intended
combine (74HCT08 AND) is wrong polarity anyway: TCM809 ~RESET and ~CPURESET
are active-low, V20 RESET is active-high (needs NOR / OR-of-inverted).
Also `bus_mcu.py:169-173`: RESET_DRV sits in the U6 HLDA-DIR transceiver
group, so the MCU can only drive bus reset while it owns the bus — at cold
start RESET_DRV floats. RESET_DRV must be a fixed-direction always-driven
output.

### C3. Hard driver contention on address/strobes during bus-master handoff
- `bus_mcu.py:210`: the 74HCT163 counter Qs tie directly to A0–A19. A '163
  has **no output enable**, and the '573 latch OE is tied to GND
  (`cpu_core.py:104`) — two push-pull drivers on A0–A19 100% of the time.
  Needs a 74HCT541/244 stage (OE from HLDA) after the counter, and the '573
  OE released on HLDA (classic 8282-style handoff). Note
  `questions-bus_mcu.md` Q1(c) already says "through buffers gated by bus
  role" — the implementation contradicts the logged decision.
- `bus_mcu.py:179-189`: U3/U4/U5 (DIR=HLDA) drive A0–A19 as master from
  nets MA8–MA19 **that connect to nothing** (only MA0–7 exist), fighting the
  counter. Address group should be fixed B→A snoop; the counter, not the MCU,
  sources master addresses.
- `cpu_core.py:86-95` vs `bus_mcu.py:170-175`: U10/U11 strobe gates are
  push-pull with no OE; when the Bus MCU masters the bus both drive
  ~MEMR/~MEMW/~IOR/~IOW. Needs tri-state ('HCT125, OE from HLDA) + inactive
  pull-ups.
- BALE is in the U6 HLDA-DIR group (`bus_mcu.py:173`) but the V20 does NOT
  float ALE during HOLD — master mode would fight it. BALE is input-only for
  the MCU; move to a fixed-direction channel.

### C4. Address latches never latch — BALE_L has no driver
`sheets/cpu_core.py:104,117`. All three '573 Load pins tie to `BALE_L`, but
V20 ALE only goes to the `BALE` hier pin; the "buffer" in the comment doesn't
exist. A0–A19 are never valid. One-line fix (label ALE to BALE_L or add the
buffer gate).

### C5. INTA vector path broken — data transceiver direction wrong
`sheets/cpu_core.py:77-78,122-123`. U5 '245: DIR=~{RD}, CE=GND, and DEN /
DT/~R are marked no-connect ("min mode: unused" — incorrect; min mode provides
them precisely for this). During INTA, ~RD stays high → U5 drives *toward*
the bus from floated AD0–7, fighting the Bus MCU's vector; the vector never
reaches the CPU. During HOLD, ~RD floats → undefined direction. Fix:
DIR = DT/~R, enable = DEN with pull-up.

---

## HIGH

### H1. CH224K strap note is dangerous — grounding CFG1 selects 9–20 V, not 5 V
`sheets/power.py:70-72`, `questions-power.md` #2. Per the WCH datasheet,
CFG1 high/open = 5 V; low = the 9/12/15/20 V rows. Populating R3 per the
schematic note puts ≥9 V on the +5V rail (abs max 7 V on V20/SRAM/HCT/modules).
Fix: delete R3; note "CFG1 must be left open/high for 5 V".

### H2. Missing pulls on handoff/wire-OR control lines — AEN worst
No sheet pulls: **AEN** (only driven via U6 when HLDA=1; floats during all
CPU-owned cycles, yet every card qualifies I/O decode on AEN=0 — needs a
pull-down), IOCHRDY (wire-OR, floats between waits — pull-up), ~IOCHCK
(open-collector contract, sensed raw at `bus_mcu.py:80` — pull-up),
~RD/~WR/IO/~M (float during HOLD into the strobe gates — pull-ups),
MEMR/W/IOR/W across the handoff gap (pull-ups), IRQ2–9 at the '165
(`bus_mcu.py:226-230`, floating CMOS inputs → phantom IRQs — pull-downs),
and the declared-but-undriven ~DACK2/~DACK3.

### H3. MEMR/W/IOR/W gating unwired and mis-planned
`sheets/cpu_core.py:84-95`. U10/U11 inputs are never wired (~RD/~WR/IO/~M
don't enter the gates); the four strobe outputs are taken from pins 1/13 which
are gate *inputs* on both '32 and '08; and ~MEMW needs OR(~WR, IO/~M) — the
'08 AND would assert MEMW on every memory read. ~IOR/~IOW need inverted IO/~M
(one HCT04 gate). No `questions-cpu_core.md` exists despite the "detailed in
open-questions" pointer.

### H4. XT-IDE INTRQ pull-up parks IRQ5 asserted
`sheets/storage.py:187`. ATA INTRQ is active-high, tri-stated when no drive
selected; the +5V pull-up + always-enabled 'HCT125 (line 96-98) makes IRQ5
permanently asserted → interrupt storm when unmasked. `questions-storage.md`
Q4's logged pick defines the idle level at the *asserted* state. Fix: pull-down.

### H5. LPT Busy (status bit 7) not inverted
`sheets/parallel.py:169`. Real SPPs invert Busy on the card (bit7 = NOT-Busy);
BIOS INT 17h spins on bit7=1 = ready. As drawn, printing hangs while idle.
Fix: route P_BUSY through the spare U9 inverter (P12/P13 free at line 79).

### H6. TL072 cannot run single-supply +5 V with 2.5 V virtual ground
`sheets/audio.py:83-98`. TL072 min supply ±5 V and input CM no lower than
(V−)+4 V — outside spec on both counts (risk of phase reversal). Fix: RRIO
single-supply part (MCP6002/TLV2372; LM358 works too).

### H7. card_isatest DUT-power P-FET is on at power-up and can't turn off
`sheets/card_isatest.py:244-249`. Q1 source = V5RAW but gate pulled to +3V3
and driven by a 3.3 V '595 → "off" is Vgs = −1.7 V (at/past threshold), and
Vgs=0 is unreachable. Defeats spec §9 "DUT unpowered until enabled". Fix:
pull gate to V5RAW; drive via open-drain NPN/NMOS from DUT_PWR_EN.

### H8. card_isatest ÷3 never divides — TC→~PE reload unwired
`sheets/card_isatest.py:214`. `DIV3_TC` and `DIV3_LD` are two dangling nets
(and joining them directly is wrong polarity — TC is active-high, ~PE
active-low). '163 free-runs ÷16 → "4.77 MHz" is actually 0.895 MHz. cpu_core
is correct (its 'HCT04 spare gate inverts TC→~PE at `cpu_core.py:183`);
replicate that here (U19 has spare gates).

---

## MEDIUM

### M1. Supervisor↔Bus-MCU link pins have no hardware UART function
`sheets/supervisor.py:127-128` claims "UART1 TX/RX" on RP2040 GPIO2/3, but
those are UART0 CTS/RTS; hardware TX/RX pairs (0/1, 4/5, 8/9, 12/13) are all
consumed by console/POST. As drawn the multi-Mbaud image push must be a PIO
UART. Fix: move LINK to GPIO4/5 and shift POST segments, or document PIO-UART.

### M2. Address counter synchronous-load cascade hazard
`sheets/bus_mcu.py:197-215`. '163 load is synchronous, all five CPs share
CNT_CLK, CEP/CET tied high → each lane-load pulse also increments the other
stages; a stale stage at TC can carry into a just-loaded lane. Fix: gate
non-loading stages' CEP with "no load in progress" (one spare AND), or
document a firmware ordering workaround.

### M3. Bus MCU GPIO is 48/48, and PINS advertise dropped signals
`sheets/bus_mcu.py:44-91`. Budget margin was bought by silently dropping CLK
sense, raw ~WR, IO/~M, DRQ2/3, ~DACK2/3 — but PINS/_DIR still declare them,
so they dangle (DACK2/3 are declared outputs nothing drives). Reconcile with
doc §5.2 (which claims ≈44–46/48 "with margin") and prune PINS.

### M4. Storage register map matches no XTIDE Universal BIOS device type
`sheets/storage.py:104-121`. CS0 at +0, CS1 at +8, latch at +0x10 — rev 1 has
the latch at +8; rev 2/Chuck-mod (the doc's named target) is the A0↔A3 swap
with the latch at +1. Stock XTIDE UB has no module for +0x10 → unbootable
without a custom BIOS build. Wire the true rev-2 swap.

### M5. COM4/IRQ10 plan is dead; stale notes and contract drift
The 60-pin isa_conn dropped IRQ10/11/14, but doc §11.1/§14 still assign
COM4→IRQ10, and `questions-sidecar.md` still documents the old 64-pin header.
Also `~{REFRESH}` (isa_conn pin 35, bus_mcu GPIO47, card_isatest) never got
added to `mxbus.py` ISA_CTRL — the contract file is missing a real cross-sheet
signal. Update doc §14, retire/rewrite questions-sidecar.md, add ~{REFRESH}.

### M6. card_isatest clock tree on the switched DUT rail
`sheets/card_isatest.py:201-231` power OSC1/U15–U19 from "+5V" (downstream of
Q1) contrary to spec §8 (clock tree on USB rail). No CLK/OSC/CLK_SENSE until
DUT power is on, and 3.3 V PIO_CLK / '595 outputs back-power the unpowered
'HCT157s through clamp diodes. Fix: clock tree VCC → V5RAW; only slot/header
VCC on the switched rail.

### M7. card_isatest missing spec'd IRQ/DRQ idle pull-downs
Spec §4/§9 lists them; only ~BUF_EN/IOCHRDY/DUT_PWR_EN pulls exist (R1–R3).
Add pull-downs on IRQ2–8 / DRQ1–3 on the 5 V bus side.

### M8. COM TTL console header conflicts with MAX3241
`sheets/com_port.py:190-194`. J3 taps UART_RXD which the MAX3241's push-pull
R1OUT also drives — plugging a console in is driver-vs-driver. Also J3 is
5 V TTL with +5V on pin 4 (hostile to 3.3 V dongles). Fix: 3-pin jumper
selecting R1OUT vs console-TX (the doc says "jumpered" — the jumper doesn't
exist), plus level note.

---

## LOW

- **÷3 duty comment inverted** (`cpu_core.py:170`): Q0 is high 2/3 (67%), not
  ~33%; the correct 33%-high only appears because the 'HCT04 buffer inverts.
  Document that the buffer MUST stay inverting (V20 clock-low spec at 4.77).
- **mxbus.py contract drift** (`mxbus.py:64-65` etc.): SPEED_SEL comment still
  says "Supervisor static latch" (moved to Bus MCU); PRIV_CPU still lists
  ~{WR} (reclaimed for ~REFRESH); `~{Y5_VIDCS}` declared but actual net is
  sheet-local Y5_INT.
- **74HCT at 3.3 V on card_isatest** ('165s): HCT VCC spec is 4.5–5.5 V —
  must become HC/LVC at layout (the logged "threshold moot" note misses the
  supply-range violation).
- **card_isatest config bits on the address-latch hot path**
  (`card_isatest.py:160-163`): DUT_PWR_EN/SPEED_SEL/CLK_SRC ride U11 under
  RCLK_ADDR — every address shift rewrites them; move DUT_PWR_EN to U12 QH.
- **LPT IRQ7 push-pull and unlatched** (`parallel.py:68`): blocks future IRQ7
  sharing; the 1–12 µs ~ACK pulse may fall between '165 polls.
- **card_com IRQ ignores the base-address strap** (`card_com.py:21-22`):
  a card strapped to 0x2F8 still interrupts on IRQ4.
- **Supervisor USB-A VBUS unprotected** (`supervisor.py:96`): add a load
  switch/polyfuse; a shorted keyboard drops the whole 5 V rail (doc §13 calls
  this the tight loop).
- **RTC AS hold margin** (`rtc.py`): AS falls ~3 gate delays after ~IOW rises;
  tightest timing on the sheet — bench-verify.
- **Duplicate exports in cpu_core**: ~{RD} (lines 68, 81), RESET_DRV hier
  label twice (193, 198).

## Toolchain

- **`tools/build.py:227` always exits 0** (`sys.exit(0 if assemble() == 0
  else 0)`). Since expected-category ERC errors make kicad-cli exit nonzero,
  the mask is understandable but too blunt: parse the report histogram (as
  validate_sheet.py does) and fail on nonzero *structural* categories.
- **Hardcoded snap paths pin a snap revision**: `/snap/kicad/22/...` in
  build.py, validate_sheet.py, pins.py breaks on the next snap refresh. Use
  `/snap/kicad/current/...` or an env override.
- **Non-deterministic UUIDs → 7,500-line no-op diffs** (the current
  uncommitted changes are exactly this). Derive UUIDs deterministically
  (uuid5 of sheet name + stable item key) so rebuilds are reproducible and
  diffs show real changes.
- **Latent escape round-trip bug in mxsch** (`_tokenize`/`_atom`): escaped
  chars inside quoted strings are kept raw and re-escaped on dump →
  double-escaping if a library symbol property ever contains `"` or `\`.

---

## Fixes applied — 2026-07-03 (C1–C5 + prerequisite parts of H2/H3)

All in `sheets/cpu_core.py` / `sheets/bus_mcu.py`; rebuilt with
`tools/build.py`; netlist-verified; structural ERC = 0 (and `pin_to_pin`
dropped 66 → 7 — the modeled bus contention is gone).

- **C1** SRAM /OE//WE now `~{MEMR}`/`~{MEMW}` (verified: RAM101/RAM102 pins
  24/29 on those nets, which the Bus MCU also reaches via U6).
- **C2** Reset: TCM809 → `~{PWRGOOD}`; two spare U7 74HCT00 NANDs combine
  `~{PWRGOOD}` + `~{CPURESET}` into active-high `V_RESET` (V20 pin 21) and a
  separately-buffered `RESET_DRV` (now driven from cpu_core; consumed by
  video/COMx/parallel/storage/sidecar). RESET_DRV removed from the Bus MCU's
  interface and U6 group entirely — the MCU sequences reset via ~CPURESET.
- **C3** Address/strobe handoff:
  - '573 latches: OE = HLDA (release during master cycles); counter outputs
    renamed CA0–CA19 and buffered to the bus by U214–U216 74HCT244s with
    ~OE = ~HLDA (new U217 74HCT04 inverts HLDA). 8282-style handoff.
  - bus_mcu U3/U4/U5 address '245s: DIR fixed low (bus→MCU sense only);
    BALE moved onto a spare U5 channel (input-only — V20 holds ALE in HOLD).
  - U6 now carries ONLY the four role-flipping strobes (DIR = HLDA).
  - AEN + TC moved to new U13 '245, DIR fixed high (MCU→bus, always driven);
    R1 10k parks M_AEN low so cards' decode sees AEN=0 before firmware runs.
  - CPU strobe gates now reach the bus through U11 74HCT125 (~OE = HLDA).
  - Includes the H3 fix: U10 74HCT32 fully wired (~MEMR = ~RD OR IO/~M,
    ~MEMW = ~WR OR IO/~M, ~IOR/~IOW use IOM_INV from a spare U13 '04 gate).
  - H2 (partial): 10k pull-ups on ~RD/~WR/IO/~M/DEN (float during HOLD) and
    on ~MEMR/~MEMW/~IOR/~IOW (ownership gap); M_AEN pull-down. Remaining H2
    items (IOCHRDY, ~IOCHCK, IRQ2–9 pull-downs, ~DACK2/3) still open.
- **C4** '573 LE now on the BALE net (V20 ALE pin 25 → U102/U103/U104 pin 11,
  also video + sidecar); the undriven BALE_L label is gone.
- **C5** Data '245: DIR = DT/~R (V20 pin 27), ~OE = DEN (V20 pin 26, pulled
  up so the '245 goes Z during HOLD); DEN/DT-R no_connects removed. INTA
  cycles now pass the vector bus→CPU.
- Bonus: Bus MCU GPIO22 (freed by the RESET_DRV removal) now senses bus CLK
  directly, fixing the dangling CLK interface pin from M3 (RP2350 IOs are
  5 V-tolerant).

New parts: cpu_core U11 74HCT125, R1–R8 10k; bus_mcu U13 74LVC245A,
U14–U16 74HCT244, U17 74HCT04, R1 10k. Removed: cpu_core U15 74HCT08.

## Fixes applied — 2026-07-03, batch 2 (H1, H2 remainder, H4–H8)

Rebuilt (motherboard + all six cards); structural ERC = 0 everywhere;
netlist-verified. Overturned decisions corrected in questions-{power,storage,
parallel,audio,isatest}.md.

- **H1** power.py: R3 deleted, CFG1 no-connect with a schematic warning
  ("CFG1 OPEN = 5V; never strap low — that selects 9–20 V").
- **H2** (remainder) bus_mcu.py: R2 IOCHRDY pull-up, R3 ~IOCHCK pull-up,
  R4–R11 IRQ2–IRQ9 pull-downs at the '165, R12/R13 ~DACK2/~DACK3 pull-ups.
  (AEN fixed-drive + M_AEN pull-down landed in batch 1 with C3.)
- **H4** storage.py: R2 INTRQ pull changed +5V → GND (INTRQ is active-high,
  tri-stated with no drive selected; verified R1002 on IDE_IRQ with GND leg).
- **H5** parallel.py: DB25 Busy (J701.11) → spare U9 inverter (P13→P12) →
  BUSY_N → status buffer 1A0; status bit 7 is now ~Busy per SPP semantics.
- **H6** audio.py: U1 value TL072 → MCP6002 (RRIO; pin-identical dual op-amp
  body reused, same value-override pattern as the 74LVC245A).
- **H7** card_isatest.py: P-FET gate now pulls to V5RAW (R5, default OFF) and
  is driven by Q2 2N3904 open-collector (base R4 from DUT_PWR_EN; R3 now a
  pull-DOWN on DUT_PWR_EN). Enable polarity: DUT_PWR_EN=1 → DUT powered.
  Verified: PFET_G = {Q1.G, Q2.C, R5}, R5 → V5RAW.
- **H8** card_isatest.py: DIV3_TC → U19 spare inverter → DIV3_LD (~PE);
  verified U16.15→U19.3 and U19.4→U16.9. The '163 now divides by 3.

New parts: bus_mcu R2–R13; storage R2 repurposed; card_isatest Q2 (2N3904),
R4 4.7k, R5 10k. Removed: power R3.

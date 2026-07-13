# cpu_core — per-sheet decisions

Format: question / why / options / pick. Appended as decisions are made.

## 2026-07-14 — 3.3 V single-board conversion (Task 4)

### Q1. RESET path — does V20 RESET need the 5 V HCT04 buffer?
- **Why:** the design doc hedged ("RESET if flagged"); moving glue to 3.3 V
  makes this concrete.
- **Options:** (a) route V20 RESET through the 5 V U13 HCT04 like CLK; (b) drive
  RESET directly from 3.3 V logic.
- **Pick:** (b). Task1 check 1 (NEC IC-3552A §9.1) puts RESET in the general-input
  class, Vih = 2.2 V min — NOT the clock class (Vkh = 4.0 V). A 3.3 V swing clears
  2.2 V with margin. So the reset combiner U7 (now 74HC00 @ +3V3) drives V_RESET
  directly; only CLK keeps the 5 V U13 buffer. No reset gate on U13.

### Q2. Reset supervisor (U14 TCM809) rail?
- **Why:** U7 (its ~PWRGOOD consumer) moved to +3V3; a 5 V TCM809 output would
  overvolt the 3.3 V NAND input.
- **Options:** (a) keep TCM809 @ +5V and level-shift ~PWRGOOD; (b) move TCM809 to
  +3V3 and let it monitor the 3.3 V rail.
- **Pick:** (b). One fewer part, clean 3.3 V reset net, and the reset supervisor
  most usefully guards the 3.3 V logic rail the whole board runs on. V20 RESET
  tolerates the 3.3 V-derived reset (Q1). Threshold-variant selection
  (e.g. TCM809T ~3.08 V) is a parts.py concern, not a sheet change.

### Q3. Clock divider grade at 3.3 V (÷2 U8, ÷3 U9)?
- **Why:** both dividers move to the 3.3 V rail; Task1 check 7 found plain HC
  fails fmax margin at 3.3 V (÷2 74HC74 interp. ~14.8 MHz vs 14.318 MHz clock =
  ~3 %; ÷3 74HC161 interp. ~11.1 MHz = BELOW the clock).
- **Options:** (a) leave HC-grade; (b) LVC-grade.
- **Pick:** (b) — value overrides 74LVC74A (U8) and 74LVC161 (U9) on the existing
  '74/'163 bodies (same pinout, LVC spec'd 250/150 MHz). CP fed by OSC (5 V) lands
  on the LVC parts' 5 V-tolerant inputs. Note U9's ÷3 is a 74HC161-style preset-
  reload scheme on the mini-xt:74HCT163 body (NOT a 4017, as some docs say).

### Q8. Re-buffer BALE / CLK / OSC at 3.3 V (review fix, commit f6d0d34 finding).
- **Why:** review found three ISA bus nets driven at 5 V. The board's internal
  ISA bus is 3.3 V and reaches the non-5V-tolerant sidecar RP2040; NO 5 V push-
  pull output may drive a shared bus net. The offenders were: **BALE** (V20 ALE
  pin, 5 V push-pull, drove the bus net directly); **CLK** (U13 74HCT04 @ +5V
  buffered CLK7 → bus CLK); **OSC** (U13 @ +5V buffered OSC_3V3 → bus OSC). U13
  also *fed* the dividers via the 5 V OSC net — but OSC has no legitimate 5 V
  consumer (the V20 gets CPUCLK, not OSC), and the LVC dividers read 3.3 V fine.
- **Options:** (a) level-shift each net; (b) re-buffer all three at 3.3 V behind
  a single 74LVC125A (5 V-tolerant inputs, 3.3 V bus output); reuse a spare gate
  if one exists.
- **Pick:** (b). No spare 3.3 V buffer gate is free (U11 '125 and U7 '00 are
  full; the only buffer-capable spares are HC157 mux sections, which are NOT
  5 V-tolerant so can't take BALE's 5 V input) → placed ONE new **U15 74LVC125A
  @ +3V3**, ~OE tied low (always enabled):
  - **BALE** = buf(ALE_RAW). V20 ALE now labels the private `ALE_RAW` net which
    feeds the latch LE pins DIRECTLY (un-delayed latch timing, per the brief) and
    the U15 buffer input; only the buffered copy reaches the BALE bus pin. BALE's
    input is the raw 5 V ALE → the buffer MUST be LVC (5 V-tolerant input).
  - **CLK** = buf(CLK7). Kept the FIXED-7.16 MHz source (CLK7, not CLK_MUX): the
    speed mux only retimes the private CPUCLK; ISA CLK stays 7.16 MHz (existing
    turbo-down design intent). Input is 3.3 V.
  - **OSC** = buf(OSC_3V3). The ÷2/÷3 dividers now clock off OSC_3V3 (the raw
    3.3 V oscillator) directly, so the 5 V OSC net is deleted entirely.
  U13 keeps its ONE essential 5 V gate (CLK_MUX → CPUCLK, the V20's private clock
  needing Vkh = 4.0 V) plus the two internal inverters (DIV3_TC→~PE, IO/~M→INV);
  its three now-free gates are parked. Non-inverting re-buffer (vs U13's old
  inverting path) is fine — ISA CLK/OSC polarity is unspecified.
- **Evidence (hardware/mini-xt.net):** CLK = {J1201.37, U115.6, +consumers} (no
  U113/U101); OSC = {J1201.57, U115.8} (no U113/U101); BALE = {J1201.53, U115.3,
  +consumers} (no V20); ALE_RAW = {U101.25 ALE, U102/103/104.11 LE, U115.2};
  CPUCLK = {U101.19 CLK, U113.2} exactly.

### Q4. Strobe-path boundary — which package crosses 5 V→3.3 V, and does U10 move?
- **Why:** the brief frames U13 as "the one 5 V package," but U10 (74HCT32 strobe
  OR-combiner) reads the RAW 5 V V20 strobes (~RD/~WR/IO~M) — a 3.3 V 74HC there
  would be over-driven.
- **Options:** (a) move U10 to 3.3 V (needs the raw V20 strobes buffered first —
  no such buffer exists); (b) keep U10 @ +5V and make U11 (tri-state stage) the
  boundary via 74LVC125A (5 V-tolerant in, 3.3 V bus out).
- **Pick:** (b). U10 stays 74HCT32 @ +5V (unchanged — brief never lists it); U11
  becomes 74LVC125A @ +3V3, the strobe half of the boundary. So there are in fact
  TWO surviving 5 V packages (U10 '32 + U13 '04) plus the V20 — the brief's "one
  package" prose refers only to the glue being *converted*, not U10.
  **Amended (Q8):** the surviving 5 V outputs must ALSO never drive a shared bus
  net. U13 now drives ONLY the private CPUCLK; its old bus CLK/OSC drives (and the
  V20's raw ALE → BALE) were re-buffered to 3.3 V behind U15 (74LVC125A). U10's
  outputs were already contained behind the U11 '125 tri-state boundary.

### Q5. SPEED_SEL select routing after U12 mux moves to 3.3 V?
- **Why:** U12 (74HC157 speed mux) moves to +3V3. Its select was driven by a
  5 V U13 HCT inverter (SPEED_INV) — 5 V into a 3.3 V-powered select input would
  overvolt it.
- **Options:** (a) keep the 5 V inverter (overvolts the 3.3 V mux — rejected);
  (b) drive S directly from the 3.3 V SPEED_SEL GPIO and un-swap I0a/I1a.
- **Pick:** (b). 3.3 V GPIO clears HC's Vih (0.7·3.3 = 2.31 V) on the now-3.3 V
  mux. With true-sense select, I0a/I1a are un-swapped (I0a=CLK7, I1a=CLK4) so the
  firmware polarity holds: SPEED_SEL=0 → S=L → Za=CLK7 (7.16 MHz). Frees U13's
  P11/P12 gate — parked (P11→GND, P10 NC).

### Q6. Single SRAM placement + /CE polarity.
- **Why:** 2×AS6C4008 (DIP-32, 5 V, user-sourced) → 1×IS62WV51216BLL (TSOP-44,
  3.3 V, JLC-stocked, 512K×16 used as 1M×8 via byte-lane trick).
- **Pick:** RAM1 placed at (302.26, 109.22) in the area vacated by the two DIPs.
  Byte lane: chip A0..A18 ← system A1..A19; both IO bytes tied to D0..D7;
  ~{LB}=A0, ~{UB}=A0_INV. Both VDD (11,33)→+3V3, both GND (12,34)→GND.
  **/CE = NOT(Y5_INT)** via U7d NAND-as-inverter: 74HC138 Y5 (=Y5_INT) is
  active-LOW in the 0xA0000–0xBFFFF video window, so ~{CE}=HIGH (SRAM off) there
  and LOW (SRAM on) everywhere else = full 1 MB less the video window. The A0→UB
  inverter is U7a. Both inverters use the two U7 gates freed by deleting the old
  SRAM#2 select NAND.

### Q7. Decoupling rail split (step 4).
- **Why:** board logic is now 3.3 V; only V20/U10/U13 remain 5 V.
- **Pick:** decouple() pool defaults to +3V3 (14 caps, down 2 from the old 2-SRAM
  layout = the removed SRAM's decoupling). Two explicit +5V caps (C24/C25) for the
  surviving 5 V parts; C27 +5V bulk kept. Decoupling adequacy is not ERC-checked
  at this fidelity — this just keeps the rails honest.

### Q9. Reset supervisor threshold wrong for the 3.3V rail (Task 10 fix).
- **Found by:** Task 10's implementer, doing a final sweep before the 3.3V
  redesign shipped. `parts.py` bound U14 (`Power_Supervisor:TCM809`) to
  MCP809T-450I/TT — a **4.375 V** threshold — left over from when this part
  monitored the board's old +5V rail. U14's `VCC` moved to +3V3 in this same
  redesign (§ comment at cpu_core.py:333), but the LCSC binding didn't follow:
  a healthy 3.3V rail can never cross 4.375 V, so `~{PWRGOOD}` never
  deasserts and the board would sit in reset forever — a full no-boot bug,
  not cosmetic.
- **Why 4.5V-grade was wrong:** the -450I/TT grade's 4.375V threshold is
  ~1.14x the 3.3V nominal rail; even the buck's absolute max output can't
  reach it under any normal fault. It was the *correct* grade for the old
  +5V rail (4.375V is a sane brown-out point for 5V, ~87.5% of nominal) and
  simply never got re-picked when the rail it watches changed.
- **Pick:** `TCM809TENB713` (LCSC C47195, real Microchip TCM809 family — not
  a substitute — SOT-23-3, `-T` grade, **3.08 V** threshold, extended
  library, stock 94 at query time). Netlist-verified same pinout/footprint
  as the part it replaces (VCC/GND/~{RESET} only, footprint unchanged —
  `Package_TO_SOT_SMD:SOT-23`). Considered MCP809T-300I/TT (2.925V, C556907,
  stock 51) and MCP809T-270I/TT (2.625V, C145693, stock 58) as MCP809-family
  alternatives; picked the TCM809-family part instead since it's literally
  the wanted part (no substitution needed) and has the highest stock of the
  in-range candidates.
- **Margin arithmetic:** TPS563200 buck output regulation is ~±2%, so the
  3.3V rail's worst-case floor under normal operation is 3.3 × 0.98 =
  **3.234 V**. Threshold 3.08V is 0.154V (≈4.7% of nominal) below that floor
  — comfortably inside "asserts only on a real droop, stays deasserted
  through normal ripple/tolerance." It's also well above 0V/noise floor, so
  it still catches a genuine brown-out rather than never tripping. Sheet
  value string is unchanged (`place()` defaults value to `"TCM809"`, the
  bare lib_id suffix — the threshold binding lives only in `parts.py`'s
  (lib_id, value) → LCSC map, per the generic-schematic convention).

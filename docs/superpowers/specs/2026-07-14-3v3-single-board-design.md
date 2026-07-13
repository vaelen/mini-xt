# 3.3V single-board redesign

**Date:** 2026-07-14
**Status:** Approved design, pending implementation plan

## Summary

Collapse the multi-board, 5V-bus mini-XT into **one PCB with a 3.3V internal
bus**. The V20 becomes the only 5V chip on the board (plus one 5V-supplied
HCT buffer package and the expansion port's far side). The V20's existing
address-latch/data-transceiver stage, re-specified as 74LVC parts, *is* the
single 5V↔3.3V boundary — zero added chips at the CPU. Level shifting and bus
isolation exist in exactly one other place: a buffer bank at the external
expansion port, which continues to present a standard 5V-compatible 8-bit ISA
header to real period cards.

Estimated component count drops from ~455 to ~350, with BOM cost dropping
more than the count (sockets, duplicated inter-board headers, and per-section
transceivers were the expensive parts).

## Decisions (all confirmed with the user)

| # | Decision |
|---|----------|
| 1 | **One big board.** All sections merge onto a single PCB (> 100×100 mm, JLC larger tier). Inter-board 60-pin daisy-chain headers deleted. Sheets remain separate *schematic* sheets. |
| 2 | **3.3V internal bus** (Approach A). The 74HCT573 ×3 + 74HCT245 V20 demux stage becomes **74LVC573A ×3 + 74LVC245A** powered at 3.3V: 5V-tolerant inputs accept the V20 directly; their outputs are the internal bus. |
| 3 | **All-3.3V peripherals; no period-part swap-ins.** TL16C550C stays but as **TL16C550CPT (LQFP-48) soldered directly** at 3.3V — PLCC-44 sockets deleted. |
| 4 | **RTC emulated in the Bus MCU** (like PIC/PIT). DS12C887 and its ISA glue deleted. Hardware timekeeping: small **I2C RTC + coin cell on the Supervisor**; time synced to the Bus MCU over the existing UART link at boot. CMOS config bytes persist in Supervisor flash. |
| 5 | **One SRAM chip: IS62WV51216BLL-55TLI** (512K×16, 2.5–3.6V, 55 ns, LCSC C11315, deep stock) wired as **1M×8 via the byte-lane trick**. Replaces 2× AS6C4008 + 2 DIP-32 sockets. |
| 6 | **Expansion port keeps real-ISA compatibility** behind an isolation/buffer bank (~6× LVC245/244). Standard 8-bit ISA 60-pin pinout and fused +5V retained. |
| 7 | **Dev cards (`hardware/cards/`) retarget to the 5V expansion port** as genuine ISA cards; they keep their own local level shifters. The isatest jig remains the no-motherboard test host. |
| 8 | **The soft-card "ISA-signals-only" isolation rule is downgraded** from hard schematic requirement to a firmware-portability guideline. mxbus's PRIV_* hard split loosens accordingly. |

## Voltage architecture

3.3V everywhere, with exactly three 5V presences:

1. **V20** (DIP-40, socketed as before) on the 5V rail.
2. **One 74HCT04 package at 5V.** HCT reads 3.3V inputs (TTL Vih 2.0V) and
   its CMOS outputs swing to the 5V rail — needed only for the V20 **CLK**
   pin (Vih ≈ 0.7×Vcc, unreachable from 3.3V). Spare gates in the package
   cover RESET (and anything else the datasheet check flags as
   higher-than-TTL Vih).
3. **Expansion port far side**: fused `+5V_ISA` rail and card-driven 5V
   signals, isolated behind the port bank.

Everything else — clock dividers, decode/glue, SRAM, UARTs, MAX3241s, all
four MCUs, PicoGUS chip-down, audio, network, storage, LPT logic — runs at
3.3V. The 5V rail shrinks to V20 + HCT04 + port feed; the 3.3V buck carries
nearly the whole board (re-budget at plan stage).

### Signal-level rules replacing the old per-card shifter pattern

- **5V → 3.3V:** only via 5V-tolerant LVC inputs or RP2350B GPIOs (5V-tolerant
  when powered). The RP2040s (Supervisor, PicoGUS) are *not* 5V-tolerant but
  now see only 3.3V nets.
- **3.3V → V20 inputs:** direct. µPD70108 logic inputs are TTL-compatible
  (Vih 2.2V). CLK (and RESET if flagged) via the 5V HCT04.
- **3.3V → expansion port:** LVC 3.3V-high output legally drives a TTL ISA
  bus (Vih 2.0V) — the PicoGUS-on-real-ISA precedent.

## CPU boundary (unchanged structure, new parts)

- 3× **74LVC573A**: latch the V20's 5V AD bus (gated by ALE) into the 3.3V
  A0–A19 bus.
- 1× **74LVC245A**: D0–D7, direction from DT/R̄ as today.
- V20 control outputs (RD̄, WR̄, IO/M̄, ALE, DEN̄, DT/R̄, INTĀ, HLDA) feed
  5V-tolerant LVC glue / RP2350B pins directly.
- Latch /OE-on-HLDA bus-master handoff arrangement unchanged.
- **Bus MCU transceivers and role-driven DIR logic deleted entirely** — its
  RP2350B GPIOs sit directly on the 3.3V bus and tri-state natively when
  slave. Likewise video MCU (−3 LVC245), PicoGUS (−3, stock firmware, GPIO
  map preserved), audio (−1), and remaining sections.

## Memory

One **IS62WV51216BLL-55TLI** as 1M×8:

- System **A1–A19 → chip A0–A18** (word address).
- **IO0–7 and IO8–15 both tied to D0–D7**; exactly one byte lane enabled at a
  time, the other tri-states.
- **A0 → /LB direct; A0 → inverter → /UB.**
- **/OE = MEMR̄, /WE = MEMW̄** (unchanged; I/O cycles keep the pins high-Z).
- **/CE = Y5 inverted** — SRAM answers the full 1MB except 0xA0000–0xBFFFF
  (video MCU window). 74HC138 decode stays; the second-chip NAND trick dies.
- The two inverters are two gates of the existing 74HC00 package.
- BIOS shadow-load into SRAM unchanged.

## Peripherals

- **COM1/COM2:** TL16C550CPT (LQFP-48) ×2, soldered, 3.3V. MAX3241s
  unchanged (already 3.3V). No sockets.
- **RTC:** sheet's ISA interface deleted. Bus MCU emulates ports 0x70/71.
  I2C RTC (PCF8563/RX8025 class, chosen from JLC stock at plan stage) +
  CR2032 holder on the Supervisor. Boot-time sync over the existing 2-wire
  UART link; Bus MCU freewheels between syncs. CMOS bytes → Supervisor flash.
- **LPT:** DB25 is an external boundary — buffers stay, re-specified LVC
  (5V-tolerant inputs for printer-driven lines). Count unchanged.
- **Storage / network / audio / video:** HCT → HC (or LVC) at 3.3V;
  HCT packages that existed purely as 3.3V→5V buffers (see
  jlcpcb-sourcing.md) deleted.

## Expansion port

60-pin (2×30) header, standard 8-bit ISA pinout, unchanged reclaimed pins
(7→IOCHCK̄, 11→GND, 15→IRQ8) and fused `+5V_ISA` (2A polyfuse + SMBJ5.0A).
New: an isolation bank of ~6 packages, all 3.3V-powered LVC:

| Group | Parts | Direction |
|----------------------------------|----------|------------------------------------|
| A0–A19 + outbound control        | 3× LVC245| out (BALE, AEN, CLK, OSC, RESET, MEMR̄/W̄, IOR̄/W̄, DACK̄1-3, TC) |
| D0–D7                            | 1× LVC245| bidir, DIR flipped by read strobes |
| IRQ2–8, DRQ1–3, IOCHRDY, IOCHCK̄ | 1–2× LVC244| in                               |

Rationale: the bank is *isolation* (load, fault, contention), not primarily
level shifting — it would exist even for a 3.3V-only port. LVC makes the port
5V-card-compatible for free.

**Note:** external bus-master cards (MEMR̄ etc. driven *by* the card) are not
supported through the fixed-direction control buffers — same limitation as
the old design, now explicit.

## hardware/cards/

Retargeted to the expansion port as genuine 5V ISA cards; they keep their own
LVC shifters (correct for an external card). `build_cards()` stays. The
isatest jig still plays bus host for card bring-up.

## Docs / tooling impact

- `docs/xt-mcu-sbc-design.md`: §2 portability contract reframed (guideline,
  not rule); §4.2 level shifting rewritten; block diagram, SRAM, RTC, COM
  sections updated.
- `CLAUDE.md`: isolation rule, socket policy, 100×100 constraint, sub-board
  standalone rule all revised.
- `hardware/tools/mxbus.py`: PRIV_* hard split loosened.
- `hardware/notes/jlcpcb-sourcing.md`: most HCT substitution notes deleted;
  new parts recorded.
- Sheet structure and generator flow (`build.py`, `mxsch.py`) unchanged.

## Plan-stage verification checklist

Datasheet checks to perform before/while wiring:

1. µPD70108 DC characteristics: confirm Vih = 2.2V for logic inputs; find
   RESET and CLK Vih exactly (drives what routes through the 5V HCT04).
2. IS62WV51216BLL: confirm /LB//UB gate outputs on reads (byte-lane trick),
   and 55 ns timing closes 0-wait at 7.16 MHz with the inverter in the /UB
   path and INV(Y5) in the /CE path.
3. TL16C550CPT at 3.3V: confirm 3.3V operation over the LQFP-48 pinout;
   re-verify pin numbers against TI data (per the hand-authored-symbol rule).
4. RP2350B 5V-tolerance conditions (IOVDD powered) for every pin that sees a
   V20 5V output directly.
5. 3.3V buck re-budget: four MCUs + SRAM + UARTs + all glue now on 3.3V.
6. PicoGUS GPIO map: confirm direct-to-bus wiring preserves the stock
   firmware's pin assignments.
7. 74HC at 3.3V timing for the clock dividers (HC74 ÷2, HC4017 ÷3 at
   14.318 MHz) — HC at 3.3V is slower than at 5V.

## Component-count estimate

Deleted: ~12 internal LVC245s; ~15 buffer-only HCT packages; 1 SRAM chip,
2 DIP-32 + 2 PLCC-44 sockets; DS12C887 + ~4 glue packages; ~10 inter-board
60-pin headers; plus proportional decoupling caps and pull-ups.
Added: ~6 port-bank LVC packages, 1 I2C RTC, 1 coin-cell holder.

**Net: ~455 → ~350 components**, one assembly instead of ~10.

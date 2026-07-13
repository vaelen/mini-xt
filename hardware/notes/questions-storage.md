# Open questions -- storage sheet (XT-IDE Chuck-mod + CompactFlash @ 0x300)

## Q1. No CompactFlash symbol in the available libraries
**Question:** The authoring guide / `pins.py -s CompactFlash` / `-s CF` finds no
CompactFlash socket symbol. What footprint/symbol should the CF True-IDE socket use?
**Why:** Section 10 calls for a 40-pin IDE header + a CompactFlash socket in True-IDE
mode, wired in parallel with the IDE header.
**Options:**
  a. Use `Connector_Generic:Conn_02x25_Odd_Even` (50-pin) and map pins to the CF
     True-IDE pinout by hand.
  b. Omit the CF socket, IDE header only.
  c. Add a custom `mini-xt:CompactFlash_TrueIDE` symbol.
**Pick (proceeding):** (a) -- 50-pin `Conn_02x25_Odd_Even`, wired per the CF True-IDE
mode pinout (pin 9 -ATASEL, pin 36 -WE, pin 44 -REG tied to their True-IDE levels;
pins 18/19/20 = A2/A1/A0; CE1/CE2 = the two IDE chip selects). Replace with a proper
CF symbol later if one is added to the library.

## Q2. Exact XT-IDE register map / high-byte latch offsets
**Question:** Which I/O offsets within the 0x300-0x31F window carry CS0, CS1 and the
high-byte latch register?
**Why:** The Chuck-mod needs (a) the 8 task-file registers (CS0), (b) the control block
(CS1), and (c) a separate "high byte" register so 16-bit data transfers become two
8-bit transfers. The design doc says "I/O base 0x300 (jumperable)" but not the offsets.
**Options:** Various XT-IDE revisions differ.
**Pick (proceeding):** Decode A4,A3 with a '138 (DEC1):
  - 0x300-0x307 (A4=0,A3=0) -> IDE /CS0 (task file, A0-A2 = register)
  - 0x308-0x30F (A4=0,A3=1) -> IDE /CS1 (control block)
  - 0x310-0x317 (A4=1,A3=0) -> high-byte latch register (HB_SEL)
A second '138 (DEC2) decodes A0-A2 inside CS0; its ~Y0 = the 16-bit data register
(offset 0), which gates the read/write high-byte latches. Block qualifier =
A9&A8&~A7&~A6&~A5 & ~AEN.

## Q3. High-byte data path topology
**Question:** One bidirectional latch ('652) vs. two unidirectional '573s + a '245?
**Why:** The guide offers `74HC573` and/or `74HC245`.
**Pick (proceeding):** Two '573s + one '245 (period-correct, all in `mini-xt:`):
  - 74HC245 buffers bus D0-D7 <-> IDE/CF D0-D7 (low byte; DIR follows ~{IOR},
    enabled for any IDE register access).
  - 74HC573 "write latch": bus D0-D7 -> IDE D8-D15, captured on a write to the
    HB register, output-enabled only during an IDE data-register write.
  - 74HC573 "read latch": IDE D8-D15 -> bus D0-D7, captured during an IDE
    data-register read, output-enabled when reading the HB register.

## Q4. IRQ5 buffering and unused IDE control lines
**Pick (proceeding):** IDE/CF INTRQ -> 74HC125 buffer -> IRQ5 (OE tied low). IORDY
pulled up to +5V (8-bit PIO mostly ignores it). DMARQ/-DACK/-IOCS16/-PDIAG/-DASP/
card-detect/voltage-sense left unconnected (8-bit PIO, no DMA). IDE -RESET = inverted
RESET_DRV. CSEL grounded (master).
</content>
</invoke>

---
**Correction (2026-07-03, design review H4):** Q4's pick (pull-UP on INTRQ) was
wrong — ATA INTRQ is active-HIGH and tri-stated when no drive is selected, so a
pull-up parks IRQ5 asserted (interrupt storm). R2 is now a pull-DOWN.

---
**Correction (2026-07-03, design review M4):** Q2's guessed register map (CS0
at +0, CS1 at +8, latch at +0x10) matched no real XT-IDE revision and no XTIDE
Universal BIOS device type. The decode is now the TRUE rev-2 / Chuck-mod map
(bus A0<->A3 swap): data 0x300, latch 0x301, CS1 regs 0x307/0x30F, drive DA0 =
bus A3, 16-byte window. See design-review-2026-07-03.md batch 3 for the
DEC1/DEC2/DEC3 split.

---

## IRQ5 made tri-state + decoupling (design review 2026-07-11)
U5 '125 OE was grounded -> IRQ5 push-pull, permanently driven low when idle
(unshareable; asymmetric with the LPT IRQ7 fix). Now Q1 (2N7002) inverts INTRQ
into the '125 ~OE with R4 10k release pull-up: INTRQ high -> IRQ5 driven high,
else Z. ~200ns enable delay through R4 is fine for interrupt latency. Spare
'125 sections tied per com_port U6 pattern. Decoupling grown to one 100nF per
IC (C1-C11) + 10uF bulk (C12).

---

## Base strap + enable jumper (2026-07-11)
JP1 selects 0x300 vs 0x320 (differ only in A5; A5_SEL replaces nA5 in the
HI_MATCH tree -- the rest of the decode, including the rev-2 A0<->A3 swap, is
base-independent). JP2 lifts DEC1's spare ~E1: open kills /CS0 and /ODD_SEL,
so DEC2/DEC3, both high-byte latches and the low-byte '245 are all inert and
IRQ5 stays released (INTRQ pull-down). Same pattern as the LPT sheet. This
lets an on-board storage port coexist with a card_storage on the sidecar
chain (strap one to 0x300, the other to 0x320, or disable one).

---

## IRQ strap: IRQ14 default (2026-07-11)
JP3 selects IRQ14 (default, 1-2) or IRQ5 (2-3), open = polled. IRQ14 is the
AT primary-IDE convention and is now physically collected by the Bus MCU's
cascaded second '165; it is in the mxbus ISA contract but has NO pin on the
60-pin sidecar header, so it only works for the on-board instance -- fine,
since the standalone storage card was removed. IRQ5 remains the XT-style
fallback (and frees the IRQ5/LPT-alt collision). XTIDE Universal BIOS takes
the IRQ per-controller in its config, so either strap position is bootable.

---

## 3.3V single-board redesign (2026-07-14, spec decision, task 7)
Whole sheet moves to +3V3 except one deliberate exception:
- **Decode glue -> HC-grade:** U1 (74HC04), U2/U3 (74HC08), U4 (74HC32),
  U6/U7/U11 (74HC138) -- 74HCT is out-of-spec below 4.5V VCC and every input
  here is 3.3V-driven address/control logic.
- **Data-path + IRQ buffer -> LVC-grade:** U8 (74LVC245A, low byte), U9/U10
  (74LVC573A, high-byte write/read latches), U5 (74LVC125A, IRQ14 tri-state
  buffer). These specifically need LVC's 5V-tolerant inputs because their
  B-side/Q-side faces the IDE header and CF socket -- an external drive or
  CF adapter can legally drive ID0-15/INTRQ at 5V even though the board's
  logic domain is 3.3V (same connector-boundary rule used on the LPT sheet).
- **CF socket VCC feed pins stay +5V (J2 pins 13/36/38/44).** These are the
  CompactFlash slot's real power-supply pins (the card has no separate power
  connector, per the CF spec) -- a physical power requirement, not a logic
  signal, so they're untouched. The 40-pin IDE header (J1) carries no VCC
  pins at all (real ATA drives are powered by a separate 4-pin Molex), so
  there's no equivalent tie there.
- pwr()/decouple()/pullup() helper defaults changed from +5V to +3V3 (every
  call site on this sheet needed the new rail; no call overrode the old
  default). The card-bulk cap (C12) moved to +3V3 to match.

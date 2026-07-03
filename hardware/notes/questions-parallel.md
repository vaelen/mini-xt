# Open questions -- parallel (LPT) sheet

Design doc S11.2 only specifies: "Discrete 74HC (374 data latch + 244/240
status/control) @ 0x378, IRQ7 (usually polled)." Everything below was
under-specified; I picked a conventional SPP/Centronics implementation and
proceeded.

## 1. Register map / read-back capability
- Q: Which of the three SPP registers are readable, and how is data read back?
- Pick: Implemented the full classic SPP map -- 0x378 Data (R/W), 0x379 Status
  (RO), 0x37A Control (R/W). Data read-back uses a 74HC245 driving the latched
  '374 outputs onto the bus during a 0x378 read; control read-back uses a
  74HC244. This is what real-mode BIOS/driver code expects.
- Alt: write-only data port (cheaper, 1 fewer buffer) -- rejected, breaks
  software that reads back the data latch.

## 2. Address decode width
- Q: How many address bits to fully decode? XT only guarantees A0-A9 for I/O.
- Pick: Decode A0-A9 fully. A3-A9 == 0b1111011 (0x378>>3) via a 74HC08 AND tree
  + one 74HC04 inverter for ~A7; A0-A2 select the register via the 74HCT138;
  AEN low (CPU owns bus) gates the '138 via ~E0.
- Note: a real board would more likely use an 8-bit comparator (74HC688) or a
  jumper for 0x278/0x3BC. Kept to the allowed glue list (138 + 08/32/04).

## 3. LPT base address selection (0x378 vs 0x278/0x3BC)
- Q: Should the base be jumper-selectable across the three standard LPT bases?
- Pick: Hard-wired to 0x378 (LPT1) as the task specifies. No jumper modeled.

## 4. Control-line inversion
- Q: SPP control bits Strobe/AutoFeed/SelectIn are inverted by open-collector/
  inverting drivers at the connector; Init is not inverted.
- Pick: Strobe(O0), AutoFeed(O1), SelectIn(O3) pass through 74HC04 inverters to
  DB25 pins 1/14/17; Init(O2) drives DB25 pin 16 directly. Used push-pull HC04
  instead of the classic open-collector (e.g. 7405/OC) buffers for simplicity --
  fine electrically for a modern printer/peripheral, noted for review.

## 5. IRQ7 generation (polled vs interrupt)
- Q: Doc says IRQ7 is "usually polled". Provide an interrupt path anyway?
- Pick: Provided a gated edge path: ~Ack (DB25 pin 10) is inverted to a positive
  pulse and ANDed with the Control-register IRQ-enable bit (O4) to drive IRQ7.
  No latch/flip-flop on the IRQ (driver polls Status; the AND just follows Ack
  while enabled). If a true latched, edge-triggered IRQ is wanted, add a 74HC74.

## 6. Status register bit mapping
- Pick: D7=Busy, D6=~Ack, D5=PaperEnd, D4=Select, D3=~Error, D2..D0=0 (tied
  low through the '244). Matches the standard SPP status byte. The hardware
  polarity (Busy/Error active states) is captured by net names only; physical
  pull-ups/inversion at the connector are out of scope for this interface sheet.

## 7. DB25 symbol choice
- Q: Connector:DB25_Male requested but not present in the lib; available are
  DB25_Pins / DB25_Socket (+ MountingHoles variants).
- Pick: Connector:DB25_Pins (generic male-style pin connector). Swap to a
  footprint-specific male part at layout time.

## 8. Write strobe timing
- Pick: '374 clock = OR(register-select, ~IOW) via 74HC32, so the latch clocks
  on the rising edge of ~IOW at the end of the write cycle. Read enables =
  OR(register-select, ~IOR), active-low for the '244/'245 output buffers.

## 9. RESET_DRV usage
- Q: RESET_DRV is in the interface but the SPP '374s have no async clear pin.
- Pick: Left RESET_DRV available as an interface pin but not wired to a clear
  (the mini-xt:74HC374 symbol exposes no MR/CLR). Power-on/soft reset state of
  the control/data latches is therefore indeterminate until the BIOS writes
  them (standard for many simple LPT cards). If a defined reset state is
  required, substitute a '273 (has MR) for the control '374 and tie MR to
  RESET_DRV.

---
**Correction (2026-07-03, design review H5):** Q6's "polarity is out of scope"
call was wrong for status bit 7 — on a real SPP the card inverts Busy (bit7 =
NOT-Busy; INT 17h spins on bit7=1 = ready). DB25 Busy now passes through the
spare U9 inverter (P13->P12, net BUSY_N) into the status buffer's D7.

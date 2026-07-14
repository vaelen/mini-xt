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

## Status-input pull-ups + decoupling (design review 2026-07-11)
R1-R5 (4.7k to +5V) added on P_ACK/P_BUSY/P_PE/P_SEL/P_ERR -- these DB25 inputs
floated into HCT buffers with no printer attached (noise reads, phantom ~Ack
IRQ7 pulses when IRQ_EN set). Decoupling grown to one 100nF per IC (C1-C13)
plus a 10uF card bulk (C14).

## Base/IRQ straps + enable (2026-07-11)
JP1 selects 0x378 vs 0x278 (they differ only in A8; a spare U12 NAND makes
~A8). JP2 grounds the '138's spare ~E1 -- open kills every register select,
read enable and latch clock, disabling the port without touching the bus.
JP3 picks IRQ7 or IRQ5 (open = polled); IRQ5 conflicts with the storage
card's INTRQ if both are enabled -- both drivers are tri-state so nothing is
damaged, but don't configure both. PINS now export IRQ5+IRQ7.

## 3.3V single-board redesign (2026-07-14, spec decision, task 7)
Whole sheet moves to +3V3 -- unlike com_port/network/storage there is no
component that has to stay at +5V (the DB25 Centronics connector carries no
VCC pin, so there's no "external device needs real 5V power" case here).

The task-7 brief's swap table named 8 of the sheet's 13 chips explicitly
(U1/U2->74LVC574A, U3->74LVC244A, U4->74LVC245A, U13->74LVC125A,
U10/U11->74HC32, U12->74HC00). I traced every remaining chip's actual net
connections against the DB25 connector to fill the gap, using the same
electrical rule the brief states for the ones it does name ("the DB25 is an
external boundary; connector-facing parts go LVC, decode glue goes HC"):

- **U5 (control read-back, 74HCT244) -> 74LVC244A** (not in the brief's
  table). Its 1A2 input (CTRL2) is the SAME net as U2's Q2 output, which
  ties directly to DB25 pin 16 (Init) with no buffer in between -- U5
  inherits that connector exposure even though it isn't itself an
  "obviously" DB25-facing chip. Plain HC244 would be under-protected here.
- **U9 (inverters, 74HCT04) -> 74AHC14** (not in the brief's table, and not
  a value already used for U9's role elsewhere). This one gate package is
  wired to DB25 on BOTH sides: P_ACK/P_BUSY (DB25 pins 10/11) are raw
  connector inputs with zero buffering ahead of them, and P_STROBE/
  P_AUTOFD/P_SLIN (DB25 pins 1/14/17) are direct connector outputs. A plain
  3.3V-VCC HC part has no guaranteed input tolerance above VCC+0.5V, so this
  needs a 5V-tolerant-input grade just like U3/U5. There's no bound
  `("mini-xt:74HCT04","74LVC04A")` entry in parts.py (only 74HC04 and
  74AHC14 are bound on this body) and adding a new parts.py entry is out of
  this task's file scope, so I reused **74AHC14** (Schmitt-trigger hex
  inverter, "5V-tolerant in" per its parts.py comment) -- already bound on
  the identical `mini-xt:74HCT04` body and already used for exactly this
  kind of ISA/connector-facing inverter role in picogus.py (U7). The
  Schmitt-trigger hysteresis is a harmless (arguably beneficial, given a
  real printer cable) side effect, not a functional change.
- **U6, U7/U8, U12 -> plain HC-grade (74HC138, 74HC08, 74HC00).** All three
  are purely internal decode/gating with no path to a DB25 pin (U12's
  ACK_POS input is one hop downstream of U9's buffering, not the raw
  connector signal) -- HC-grade is correct and matches the brief's own
  stated rule for "decode glue."
- **R1-R5 (status-input pull-ups) and R6 (JP2/LPT_EN pull) -> +3V3**, not
  +5V: 3.3V is a fully valid logic-high for the (now 5V-tolerant-input)
  buffers reading these lines, and there's no reason to overdrive the idle
  level above the board's own rail.

---
**2026-07-14: block decode moved to the central `addr_decode` sheet** --
~{LPT_CS} replaces the on-card 2x 74HC08 AND tree (U7/U8 deleted); the
0x378/0x278 strap is JP1 there; U9's ~A7 and U12's ~A8 gates are spares now.
One PRIV net (~{LPT_CS}) now crosses this soft card -- logged liftability
trade, see questions-addr_decode.md.

---
**2026-07-14 (later still): IRQ driver + enable centralized.** U13 ('125)
and JP2/R6 moved to `addr_decode` (disable = JP5 there, fit to disable,
enabled by default); U12's NAND now exports ~{IRQ_LPT} (mxbus.PRIV_IRQREQ)
and the central '125 drives IRQ7. U6 '138 ~E1 ties to GND.

---
**2026-07-14 (third pass): U9 gate 1 hosts the motherboard HLDA inverter.**
The spare Schmitt gate (freed when ~A7 decode moved central) now inverts
HLDA -> ~{HLDA} (mxbus.PRIV_CPU) for bus_mcu's counter '244s, deleting
bus_mcu's U17 (74LVC04A, 1 of 6 gates used) and its BOM line. Reverse-
direction dependency, deliberately accepted: it is the board's only spare
5V-tolerant inverter (HLDA is a raw 5V V20 output). A standalone LPT card
would ground the input again and the motherboard would re-add an inverter.

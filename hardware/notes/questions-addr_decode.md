# Open questions -- addr_decode sheet

Central bus-interface sheet for the discrete peripherals (2026-07-14, two
steps the same day): decodes I/O for com_port / parallel / storage and
exports ~{COM1_CS} / ~{COM2_CS} / ~{LPT_CS} / ~{IDE_CS} (`mxbus.PRIV_CS`);
maps their IRQ requests (`mxbus.PRIV_IRQREQ`) onto the real ISA lines
through one shared 74LVC125A; and carries ALL FIVE per-peripheral disable
jumpers (JP1-JP5: COM1, COM2, LPT, IDE, VID -- the VID level travels as
`mxbus.PRIV_DIS`). Base addresses are hardwired (third pass, same day: the
JP1/JP2 base straps were deleted, see #5). Sections below that mention six
jumpers / the NIC predate the NIC's removal (see #8).

## 1. Which peripherals to centralize
- Q: The request was "all of the peripherals" -- which sheets actually have
  decode worth pulling out?
- Decision: **com_port, parallel, storage only** -- the three with discrete
  gate decode (6 chips between them). NOT the NIC: its 74HC138 double-duties
  as the JP1 isolation gate (it takes the buffered AEN_CHIP, which JP1 parks
  high to make the whole island ignore the bus), so a central ~NIC_CS would
  still need a local combine gate -- zero net savings and a semantic risk.
  Video / PicoGUS / Bus MCU decode in MCU firmware; audio has no decode.
- Why: centralize where it deletes chips, leave it where it doesn't.

## 2. Decoder structure
- Q: Comparators ('688), one '138 per peripheral, or shared windowing?
- Decision: **one 74HC138 + one 74HC00 + 74HC32 ranks** (replacing 6 chips
  of per-sheet gates). '138: C,B,A = A8,A7,A6, E2 = A9, ~E0 = AEN -> 64-byte
  windows in 0x200-0x3FF (~Y7 COM1, ~Y3 COM2, ~Y5 LPT-0x378, ~Y1 LPT-0x278,
  ~Y4 IDE). 0x3F8/0x2F8/0x378 all need offset 0x38-0x3F in their window, so
  ONE shared fine term Q = A5&A4&A3: the '00 builds ~Q in three NANDs (no
  3-input NAND in the flat glue set) and inverts A5 with the fourth. U3
  ('32) ORs each window with ~Q (COMs, LPT) or the A5 strap leg (IDE); U4
  ('32, added with the disable jumpers) ORs in DIS_x. The A4 split inside
  the IDE window stays on the storage sheet (its DEC1 '138, as before).
- Why: the shared fine term is the whole win; comparators would be 1 chip
  per peripheral and per-'138 fine decode can't share across windows.

## 3. IRQ mapping (added with the disable jumpers, 2026-07-14)
- Q: How do the peripheral IRQs reach the ISA lines once the jumpers are
  central, given a plain label-rename would trip the multiple_net_names
  structural ERC check?
- Decision: **the tri-state IRQ drivers move here too** -- one shared
  74LVC125A (U5) replaces the three per-sheet '125s (com U8, parallel U13,
  storage U5), and IS the mapping component: IRQ_COM1->IRQ4, IRQ_COM2->IRQ3,
  ~{IRQ_LPT}->IRQ7, ~{IRQ_IDE}->IRQ14. Channel semantics are unchanged from
  the local stages: COM channels take raw INTRPT as data with ~{OUT2} as ~OE
  (software masks by clearing OUT2, PC convention -- two nets cross per COM
  port); LPT/IDE strap the input high and pulse on their active-low requests
  (whose generators -- the LPT NAND, the IDE 2N7002+pullup -- stay local,
  they're peripheral-specific). Net -1 chip and the peripheral sheets no
  longer know which ISA IRQ they get.

## 4. Disable jumpers (JP1-JP6)
- Q: Where do the enables live, and with which sense?
- Decision: **all six on this sheet, sense inverted from the old on-sheet
  jumpers: ENABLED by default, fit a jumper to disable** (per the 2026-07-14
  request). DIS_x is pulled low (10k) and jumpered to +3V3; for COM/LPT/IDE
  U4 ORs it into the chip select, so a fitted jumper makes the peripheral
  never decode --
  which also silences its IRQ at the source, same causality the old enables
  relied on (COM: MCR resets to 0 so ~OUT2 stays high; LPT: ~Ack idles high
  via the DB25 pull-ups regardless of the unreset IRQ_EN latch; IDE: the
  INTRQ pulldown keeps the 2N7002 off) -- and frees the address for an
  expansion-port card. The old per-sheet enables (com JP3/JP4+CS1 pulldowns,
  parallel JP2/~LPT_EN, storage JP2/~STOR_EN) are deleted; the freed enable
  pins tie inactive (CS1 high, ~E1 low).
- Why one OR rank instead of gating the '125 OEs: killing the decode is the
  stronger disable (an expansion card can take over the address without the
  internal card fighting the data bus), and the IRQ silence follows for free.
- NIC and VID (third pass, same day): their gating hardware CANNOT
  centralize -- the RTL8019AS decodes its own address, so its disable must
  reach inside the 5V island (the local '125 tri-states IRQ2 and parks the
  chip's AEN high); video's "decode" is firmware, so its disable is a
  boot-strap GPIO. But the JUMPER is just a logic level, so JP5/JP6 live
  here and the levels cross as `mxbus.PRIV_DIS` (DIS_NIC drives the network
  '125 OEs -- polarity already matched; DIS_VID goes to video GPIO42 with
  the firmware polarity INVERTED vs the old VID_EN strap, which is free
  since no firmware exists yet). The old on-sheet jumpers + their pull-up
  resistors (network JP1/R6, video JP1/R30) are deleted; video's VID_BASE
  strap became video JP1.

## 5. Base straps -- DELETED (third pass, 2026-07-14)
- Q: Keep the relocated LPT (0x378/0x278) and IDE (0x300/0x320) base straps?
- Decision: **No -- hardwired to the defaults, LPT 0x378 and IDE 0x300**
  (user decision), the same reasoning that already killed COM's J2 strap:
  rarely-used flexibility, and one more unjumpered-strap failure mode for
  nothing. The '138's ~Y1 (0x240 window) is NC, the '00's ~A5 gate is
  spare, and the IDE OR-leg takes raw A5 (0x300 needs A5=0). Alternate
  bases, if ever needed, are a one-line sheet change (swap the window/leg
  nets), and an expansion-port card can still provide a second LPT/IDE at
  the alternate address with the on-board one enabled.

## 6. Private nets and the portability guideline
- Q: ~{*_CS} / IRQ-request nets cross into soft-card sheets -- is that an
  isolation problem?
- Decision (user-confirmed 2026-07-14): **No -- this is shared logic
  factored out, not an isolation break.** Each net is functionally
  equivalent to the IC(s) it replaced, and it makes the sub-sheets cleaner
  (they no longer reproduce shared logic). Breaking a block out to its own
  card means the wrapper schematic re-adds the decode/IRQ driver alongside
  the bus headers, exactly like it adds the edge connector. The nets are
  documented in `mxbus.PRIV_CS` / `mxbus.PRIV_IRQREQ`.

## 7. Timing
- Note: decode path is now '138 + two OR gates (3 levels) vs the old 3-4
  gate-level AND trees -- comparable or faster, and it still reads the
  latched address, so it is identical under V20 or Bus-MCU bus ownership.

## 8. NIC removal (2026-07-14, after the passes above)
- The RTL8019AS network sheet was removed from the board (user decision;
  git tag `full-board-with-nic` preserves the last with-NIC design). On
  this sheet: JP5/DIS_NIC deleted, JP6 (DIS_VID) renumbered to JP5, RN2
  down to one pulled element (three spares). `mxbus.PRIV_DIS` is now just
  DIS_VID. IRQ2 was retired as an internal net in bus_mcu (its '165 lane
  ties low, like IRQ6/IRQ8); expansion cards still reach it as EXT_IRQ2.

## Disable jumpers folded into ONE 2x5 block (2026-07-15, user decision)

JP1-JP5 (five Conn_01x02 breakaway 1x2s) -> ONE Conn_02x05_Odd_Even block,
ref **JP1**, value "DIS block (2x5)". Position n = COM1, COM2, LPT, IDE,
VID; odd pin (row 1) carries DIS_x, even pin (row 2) is +3V3, so a jumper
cap across column n disables peripheral n. Referenced in docs as JP1.n.
parts.py binds the value to **C492422** (XFCN PZ254V-12-10P, fixed 2x5
vertical male, ~137k stock) instead of the C2333 breakaway strip -- one
purchasable part for the whole block, and the fab places one component
instead of five. Electrically identical to the five separate jumpers
(same DIS_x / +3V3 pairs, same RN1/RN2 pulldowns).

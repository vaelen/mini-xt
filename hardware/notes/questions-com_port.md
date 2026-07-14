# Open questions -- com_port sheet

This sheet is generic and instantiated twice (COM1, COM2) by the harness via the
`INSTANCES` list. The two instances are electrically IDENTICAL; the only board
difference is the base-address strap (J2) and the per-instance IRQ remap of the
generic interrupt net `COM_IRQ` (-> IRQ4 on COM1, IRQ3 on COM2).

## 1. Base-address selection (0x3F8 vs 0x2F8)
- Q: How should the per-instance I/O base be set, given one generic sheet?
- Decision: A 3-pin strap header **J2** (`Conn_01x03`). 0x3F8 and 0x2F8 differ
  only in A8, so the decode ANDs A3..A7,A9 = 1 with ~AEN and an "A8 match"
  selected by the strap: Pin1=A8 (-> 0x3F8/COM1), Pin3=~A8 (-> 0x2F8/COM2),
  Pin2=A8_SEL into the AND tree. The decode is built from 74HC04 + 2x 74HC08 and
  drives the UART's active-low ~{CS2} (CS0/CS1 strapped high).
- Why: keeps a single generic design; the only stuffing difference between the
  two instances is the jumper position. A comparator (74HC688) would be cleaner
  but is not in the available part set.

## 2. Baud reference clock
- Q: The interface exposes the 7.16 MHz system `CLK`, but a 16C550 needs a
  1.8432 MHz reference for standard baud rates. Which clock drives the UART?
- Decision: Added a local **1.8432 MHz can oscillator (OSC1)** on XIN, with
  ~{BAUDOUT} looped back to RCLK. The interface `CLK` pin is kept (per the
  required PINS list) but is NOT used on this sheet.
- Why: 7.16 MHz / 14.318 MHz do not divide to standard bit rates cleanly; a
  dedicated 1.8432 MHz reference is the period-correct choice. If a shared baud
  clock is preferred, route a 1.8432 MHz net on the backplane and drop OSC1.

## 3. MAX3241 supply rail
- Q: Power the transceiver from +3V3 or +5V?
- Decision: **+5V**, matching the 5 V UART logic levels (TTL inputs see 5 V UART
  outputs; receiver outputs swing 0-5 V). MAX3241 is rated 3.0-5.5 V.
- Why: avoids any 5 V-into-3.3 V-input overstress on the TTL side. If a 3V3-only
  transceiver domain is desired, change VCC + the flying/reservoir caps to +3V3.

## 4. Interrupt gating
- Q: Drive COM_IRQ directly from INTR, or gate it?
- Decision: INTR is buffered onto **COM_IRQ through a 74HC125** enabled by the
  UART's ~{OUT2} (the standard PC serial-card convention: software masks the IRQ
  by clearing OUT2, tri-stating the shared edge-triggered line).
- Why: matches XT/ISA serial behaviour and lets the line be released cleanly.

## 5. TTL console header
- Q: Design S11.1 puts the TTL console on COM1 only, but the sheet is generic.
- Decision: Place a 4-pin header **J3** (GND / TX / RX / +5V) tapping the UART
  TTL lines ahead of the MAX3241 on BOTH instances; populate it only on COM1.
- Why: keeps one generic sheet; a DNP on COM2 is a stuffing choice, not a layout
  difference.

## 6. MAX3241 FORCEON/FORCEOFF
- Decision: ~{FORCEOFF} and ~{FORCEON} both tied to +5V (transceiver online with
  auto-power management). ~{INVALID} left unconnected. Adjust if explicit
  always-on driver behaviour is required.

---
**Corrections (2026-07-03, JLCPCB sourcing):**
- The MAX3241 symbol's control pins were wrong (MAX3243-style names, wrong
  numbers). Real part: SHDN# (22) tied high, EN# (23) tied LOW to enable the
  receiver outputs, R1OUTB/R2OUTB NC. Note ~FORCEON high would have DISABLED
  a real chip's receivers — the EN# ground is a functional fix.
- The 1.8432 MHz canned oscillator became a crystal on the 16C550's own
  XIN/XOUT amp: JLC stocks that frequency only as 3.3 V oscillators and a
  soft card has no 3.3 V rail.

## MAX3241 charge-pump caps resized (design review 2026-07-11)
All four pump caps were 100nF; the datasheet's 5V column wants C1=0.047uF and
C2-C4=0.33uF. C3 (flying 1) is now 47nF, C4/C5/C6 330nF. Also added 100nF
decoupling for U3-U6 (the decode/IRQ glue had none) and a 10uF bulk per card.

## On-board enable + IRQ straps (2026-07-11)
The motherboard COM instances previously had their IRQ hard-wired at build
time (COM1->IRQ4, COM2->IRQ3 via the INSTANCES remap). The remap is gone: the
sheet now exposes IRQ3+IRQ4 and JP2 picks one per instance (open = polled),
matching real cards -- U6 is tri-state so the unselected line is untouched,
and two instances sharing the pins is safe. JP3 gates the 16550's spare
active-high CS1 (open = R1 parks it low -> port can never be selected; IRQ
needs no extra gating since MCR resets to 0 -> ~OUT2 high -> U6 released).
card_com's own JP2 was deleted (the sheet's strap comes along for free).

## 3.3V single-board redesign (2026-07-14, spec decision 3 / task 7)
- **U1 16550 -> TL16C550CPT, soldered LQFP-48, +3V3.** The PLCC-44 socket is
  deleted; the fab reflows the LQFP-48 in the normal SMD pass (parts.py has
  0 JLC stock for TL16C550CPTR/PTRG4 as of 2026-07-14 -- source TI
  direct/Mouser/Digi-Key like the V20, same as noted in jlcpcb-sourcing.md).
  `mini-xt:TL16C550PT`'s pin names are the same UART signals as the old
  `Interface_UART:16550` symbol (verified via `pins.py`), just renumbered for
  LQFP-48 and with three cosmetic renames: `~{RD}`/`RD` -> `~{RD1}`/`RD2`,
  `~{WR}`/`WR` -> `~{WR1}`/`WR2`, `INTR` -> `INTRPT`, `GND` -> `VSS`. The
  package's 8 extra pins (LQFP-48 has more physical pins than the DIP/PLCC
  symbol modeled) are plain `NC` -- tied off by pin number.
- **Baud crystal kept as-is at 3.3V.** TL16C550C's on-chip oscillator runs
  the same 1.8432 MHz crystal at 3.3V as at 5V (standard UART practice, no
  datasheet conflict) -- no redesign needed, per the task brief's "don't
  redesign clocking unless electrically incompatible" rule.
- **U3/U4/U5 decode glue -> 74HC04/74HC08, +3V3.** 74HCT is out-of-spec below
  4.5V VCC; these gates' inputs (A8, AEN, address decode fan-in) are all
  3.3V-driven now, so plain HC-grade (2-6V) is the correct part, matching
  the cpu_core/bus_mcu precedent for pure combinational decode logic.
- **U6 IRQ buffer -> 74LVC125A, +3V3** (brief-specified): tri-state driver
  onto the shared COM_IRQ line, LVC grade for speed/5V-tolerant-input margin
  matching the port-bank convention used elsewhere in this redesign.
- **MAX3241 (U2) -> +3V3 (Task-10 final-review fix).** The spec said "leave it,
  already 3.3V-compatible," and it WAS left at +5V -- but that created an
  un-dispositioned overstress path: at +5V the MAX3241's receiver outputs
  (R*OUT) swing 0-5V straight into U1's TL16C550 TTL inputs, which are now
  +3V3-VCC and NOT 5V-tolerant. Fix: move U2 to +3V3 (the part is rated
  3.0-5.5V and makes valid RS-232 swings from 3.3V via its charge pumps). Now
  both sides of the TTL interface share +3V3 -- no cross-domain swing. Also
  moved: ~{SHDN} tie (VCC rail), the C2 decouple, and the C13 bulk, all +5V ->
  +3V3. **This sheet now has NO +5V rail at all** (netlist-verified). Charge-pump
  caps resized to the datasheet **3.0-3.6V column: all four = 0.1uF** (were the
  5V column's C1=47nF, C2-C4=330nF). Netlist: U502/U602 VCC (+SHDN) on +3V3.
- **Every net that ties directly to a U1 (3.3V) logic pin was moved from
  +5V to +3V3**, not just U1's own VCC: CS0 (tied high), the JP3 port-enable
  pull (feeds CS1), the JP1/R2 SIN idle pull-up, and J3's TTL console
  header pin 4 (self-powered-adapter feed -- console TTL levels are now
  3.3V, so a 3.3V-tolerant adapter is now the correct match, reversing the
  old caution about "most 3.3V dongles" not tolerating 5V TTL).
- **Decoupling split by rail:** C1 (U1), C9-C12 (U3-U6) moved to +3V3; C2
  (U2/MAX3241) stays +5V. Added a new +3V3 bulk cap (C14) alongside the
  existing +5V bulk (C13, now MAX3241-only) since the sheet now has two
  real supply domains.

---
**2026-07-14: COM1+COM2 merged onto ONE sheet (was one generic sheet instanced ×2).**

- Q: Keep two instances of a generic port, or one sheet with both ports?
- Decision: **One sheet, both ports**, so the per-copy glue collapses:
  - ONE address decoder: 0x3F8/0x2F8 differ only in A8, so the common term
    (A3..A7,A9=1, AEN=0) is built once and ANDed with A8 (COM1) / ~A8 (COM2).
    Glue is now 1× 74HC04 + 2× 74HC08 (all 8 AND gates used) — was 2×04 + 4×08.
  - ONE 74LVC125A gates both IRQs (each copy used 1 of its 4 buffers).
  - Net effect: 12 ICs → 8 on the COM subsystem.
- Consequences (supersedes Q1 and Q5 above):
  - **J2 base-address straps deleted, addresses hardwired.** The strap existed
    only because one generic sheet had to serve both addresses; with both ports
    explicit there is nothing to configure, and the "J2 must always be
    jumpered or A8_SEL floats" hazard goes away. (IRQs were already hardwired.)
  - **TTL console header (J3) + RX-select jumper (JP1) exist once, on COM1
    only** — matching design S11.1's intent; the old ×2 layout placed them on
    both and DNP'd COM2's. COM2's SIN is driven directly by its MAX3241 R1OUT
    (push-pull), so it needs no selector and no idle pull-up.
  - Port enables are now JP3 (COM1) / JP4 (COM2); interface pins IRQ4/IRQ3
    replace the per-instance COM_IRQ remap. Sheet is A2 (two ports outgrow A3).

---
**2026-07-14 (later): decode moved OFF this sheet entirely** -- ~{COM1_CS}/
~{COM2_CS} now arrive from the central `addr_decode` sheet (the merge-era
74HC04 + 2x 74HC08 shrank to a share of its '138+'00+'32). See
questions-addr_decode.md; supersedes the decode part of the merge note above.

---
**2026-07-14 (later still): IRQ stage + enables centralized; UART part swap.**
The shared 74LVC125A (U8) and the JP3/JP4 enables moved to `addr_decode`
(JP3/JP4 there, sense inverted: enabled by default, fit to disable); the
UARTs export raw INTRPT + ~{OUT2} as IRQ_COM1/2 + ~{COMx_IRQEN}
(mxbus.PRIV_IRQREQ), CS1 ties high. The bound part is now **TL16C550CPFBR**
(TQFP-48, LCSC C882798, thin stock) -- the LQFP PTR is dead at JLC; pinout
verified identical to the mini-xt:TL16C550PT symbol via jlc_get_pinout.

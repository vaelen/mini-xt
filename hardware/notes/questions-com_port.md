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

# Open questions -- sidecar (2x32 IDC ISA expansion header)

## 1. Exact 64-pin signal assignment / ground count
**Question:** The design doc (§4.3) lists the signal *set* the sidecar must carry
but not the pin-by-pin assignment of the 2x32 header.
**Why it matters:** The mandatory buffered-ISA set (A0-A19, D0-D7, the four command
strobes, BALE, AEN, IOCHRDY, ~{IOCHCK}, CLK, OSC, RESET_DRV, TC, DRQ1-3,
~{DACK1-3}) is already ~50 signals, plus IRQ lines, +5V and "many grounds" on only
64 pins. There is not room for both a dense ground interleave *and* the full signal
set + extended IRQs.
**Options:**
  - (a) Carry the full mandatory set + a generous extended-IRQ block, leaving only a
    couple of grounds.
  - (b) Carry the full mandatory set, 8-9 IRQ lines, and ground at each functional
    group boundary (~6 grounds) -- the practical "ground every ~10 signals" rule.
  - (c) Drop some signals to free more ground pins.
**Pick:** (b). Wired A0-A19, D0-D7, all four strobes, BALE/AEN/IOCHRDY/~{IOCHCK},
CLK/OSC/RESET_DRV, TC/DRQ1-3/~{DACK1-3}, IRQ2-7 plus extended IRQ10/IRQ11/IRQ14
(the doc's sidecar IRQs), two +5V pins, one key pin, and six grounds placed at the
boundaries between functional groups. A future re-buffering backplane (§4.3) adds
±12V and more grounds for arbitrary ISA cards.

## 2. Which extended IRQ lines to expose
**Question:** Doc says "IRQ2-7 (+ a few extended lines from the soft-PIC)".
**Pick:** IRQ10, IRQ11, IRQ14 -- the three the I/O-map (§14) tags "sidecar / spare".
IRQ9 (the IRQ2 redirect), IRQ12 (PS/2 mouse), IRQ13 (FPU) and IRQ15 are left as
declared interface pins but not routed to the header; they remain available for a
future revision. (All of IRQ2-IRQ15 stay in PINS as the full bus contract.)

## 3. Key-pin position
**Question:** Which pin to leave as the keying / no-connect position.
**Pick:** Pin 63 (a corner position), left as a no-connect; flagged with sch.text.
On the mating ribbon this hole is plugged so the cable cannot be inserted reversed.

## 4. Decoupling
Added two 100 nF bypass caps (C1/C2) across +5V/GND next to the header to keep the
cable's +5V quiet. Not strictly required for a pass-through connector but cheap
insurance per the guide's "representative decoupling".
</content>
</invoke>

---
**Superseded (2026-07-03, design review M5):** everything above describes the
ORIGINAL 64-pin header, which was replaced by the standard-pinout 60-pin 8-bit
ISA header in `isa_conn.py` (see open-questions.md "ISA connector re-based").
IRQ10/11/14 and the pin-63 key no longer exist; IRQ8 rides reclaimed pin 15,
~IOCHCK pin 7, extra GND pin 11, REFRESH# pin 35. A sidecar COM4 now uses the
bus IRQ2 line (delivered as IRQ9 via the AT redirect) — doc §11.1/§14 updated.

# Open questions / decisions -- rtc sheet (DS12C887 @ 0x70/0x71)

## 1. Bus mode strap (MOT pin)
- Question: Intel vs Motorola bus timing for the DS12C887?
- Why: The DS12C887 multiplexed bus can run either Intel or Motorola
  timing/pin-functions, selected by the MOT pin.
- Options: MOT->VCC (Motorola: DS=data strobe, R/W=read/write level),
  MOT->GND/VSS (Intel: DS=~{RD}, R/W=~{WR}, AS=ALE).
- Pick: **Intel mode -> MOT tied to GND.** The XT/ISA bus and the de-mux
  glue here are Intel-style (separate ~{IOR}/~{IOW} strobes). Per the
  DS12C887 datasheet, MOT=VSS selects Intel timing; then DS becomes the
  active-low read strobe and R/~{W} becomes the active-low write strobe.

## 2. Multiplexed AD bus on a de-multiplexed backplane
- Question: The chip uses a multiplexed AD0-7 bus + AS (ALE), but the
  buffered ISA bus is de-multiplexed (separate A and D), and the RTC is
  addressed as two I/O ports 0x70 (index) and 0x71 (data).
- Pick: Wire AD0-7 directly to data bus D0-7 (the chip is the only
  driver/consumer on its AD pins). Synthesize the chip's strobes from the
  I/O cycle, using A0 to distinguish the two ports:
    - A write to 0x70 (A0=0, ~{IOW} low) pulses **AS** high so the chip
      latches D0-7 as the register index. R/~{W} and DS are held inactive
      so this cycle does NOT also perform a data write.
    - An access to 0x71 (A0=1) drives **DS** (read) or **R/~{W}** (write)
      and holds AS inactive, so the previously-latched index is used.
  Logic:  nA0=~A0, nIOW=~(~{IOW}).
    AS    = nIOW AND nA0 AND (selected)      [active high pulse on 0x70 write]
    DS    = ~{IOR} OR nA0                     [active low, only when A0=1]
    R/~{W}= ~{IOW} OR nA0                     [active low, only when A0=1]
    ~{CS} = ~{RTC_SEL}                        [active low for 0x70 and 0x71]

## 3. Address decode coverage
- Pick: 74HCT138 decodes A6:A4 (=111 -> ~{Y7}). Enabled only when
  A1=A2=A3=A7=A8=A9=0 (gated via 74HC02 NOR + 74HC08 AND "all-zero"
  detector) and AEN=0. With A0 selecting index/data this resolves to
  EXACTLY 0x70/0x71 (no aliasing). port 0x70 bit7 = NMI mask is handled
  by the Bus MCU (not latched here); we only decode the RTC select.

## 4. ~{RESET} source
- Question: tie ~{RESET} high (never reset) or drive from bus reset?
- Pick: Drive ~{RESET} from the bus RESET_DRV via an inverter
  (RESET_DRV is active-high, ~{RESET} active-low). Resetting the DS12C887
  clears only its interrupt-enable/flag bits on power-up/reset; the clock
  and CMOS RAM are unaffected, so this is safe and matches AT behaviour.

## 5. ~{IRQ} -> IRQ8 polarity
- Question: DS12C887 ~{IRQ} is active-low, open-drain. The mini-xt soft
  IRQ contract presents IRQ lines as active-high outputs from cards.
- Pick: Pull ~{IRQ} up to +5V (R1, open-drain) and invert it (74HC04) to
  produce the active-high IRQ8 interface signal to the soft PIC (Bus MCU).

## 6. SQW pin
- Pick: square-wave output unused -> no-connect (not part of the ISA
  soft-card interface).

## Spare-gate + decoupling cleanup (design review 2026-07-11)
U3 gate-4 inputs (P11/P12) tied to GND -- they floated (CMOS). Decoupling grown
to one 100nF per IC (C1-C6) plus a 10uF card bulk (C7).

## IRQ8 exclusivity (2026-07-12)
Q: U6's IRQ8 drive is push-pull ('04 inverter), permanently driven -- on a
   shared line that would fight any card driving IRQ8.
Pick: IRQ8 removed from the 60-pin expansion header entirely (isa_conn pin 15
   is a GND return again); IRQ8 exists only between this sheet and the Bus
   MCU's '165 collector, so push-pull drive is correct and the '125 tri-state
   stage other cards use is unnecessary here.

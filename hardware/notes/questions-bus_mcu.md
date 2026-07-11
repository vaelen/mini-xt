# Open questions -- bus_mcu sheet

## Q1. §4.2 (address-group transceivers) vs §5.1 (external address counter): who drives A0-A19 in master cycles?
- Why: §4.2 says the Bus MCU needs *bidirectional* transceivers on the address
  group "because when it owns the bus it must drive A0-A19." §5.1 says the
  20-bit address is offloaded to an external loadable 74HC163 counter so the MCU
  never drives an address line directly. Both can't literally drive the bus.
- Options:
  (a) Counter drives A0-A19 directly onto the bus; no address transceivers.
  (b) Address transceivers only (no counter), MCU drives 20 GPIO -- blows the pin budget.
  (c) Both present: counter is the master-cycle address *source*; the §4.2
      address-group '245s are the 3.3V<->5V boundary (DIR = BUSDIR) so the MCU
      can sense the low address bits as a slave and the counter outputs reach the
      backplane through buffers gated by bus role.
- Pick: (c). Counter outputs label the bus A0-A19 nets; three 74LVC245A address
  transceivers (U3/U4/U5) bridge MCU-side MA0-MA19 to bus A0-A19 with DIR=BUSDIR.
  Only the low byte (MA0-MA7) is tapped by the MCU (GPIO8-15) for 8-bit I/O
  decode (§5.2 allows A0-A7 + an external COM3 gate). This honors both sections.

## Q2. Transceiver direction nets: one BUSDIR or separate per group?
- Why: §5.2 lists "Transceiver DIR -- master/slave, 0-1 pins, can be HLDA-derived
  externally." Data direction, however, flips with read vs write *within* a slave
  cycle, not just with bus role.
- Options: (a) single BUSDIR on all '245s; (b) BUSDIR (role) on addr+control,
  a separate DATADIR (read/write) on the data '245.
- Pick: (b). BUSDIR (role, = HLDA-derived) steers the address + control '245s;
  DATADIR (cycle read/write) steers the data '245. Both are driven by the MCU
  here (GPIO42=BUSDIR, GPIO43=DATADIR); on the board BUSDIR can instead be a
  cheap external gate off HLDA as §5.2 notes.

## Q3. '245 output-enable (CE) gating.
- Why: real master/slave arbitration gates the transceiver OE with AEN/HLDA so
  only one side drives the backplane at a time.
- Pick: tie CE (active-low OE) of all '245s to GND (always enabled) for schematic
  clarity; note that the board gates CE with AEN/bus-role. Multiple drivers on the
  shared A/D nets are expected and resolve at the root harness.

## Q4. IRQ collector width -- one '165 only covers 8 of 14 IRQ lines.
- Why: the interface carries IRQ2..IRQ15 (14 lines); a single 74HC165 has 8
  parallel inputs. §5.2 says ~10-12 lines / 2-3 pins.
- Pick: per the task ("one 74HC165"), wire IRQ2..IRQ9 to the single '165 (U12);
  its serial input DS is left for a cascaded second '165 (IRQ10..IRQ15) that the
  board adds without new MCU pins (DS chains '165s). Logged as a known gap.

## Q5. RP2350B core supply (DVDD) vs the "tie VDD to +3V3" instruction.
- Why: IOVDD/QSPI_IOVDD/USB_OTP_VDD/VREG_VIN/*AVDD are genuine 3.3V rails, but
  DVDD is the 1.1V core, normally fed by the on-chip switcher (VREG_VIN->VREG_LX
  ->L->DVDD, sensed by VREG_FB).
- Pick: tie the 3.3V rails to +3V3 and GND/VREG_PGND to GND as instructed; keep
  DVDD on its own net (DVDD pins + VREG_FB) with a decoupling cap, and label
  VREG_LX separately, rather than shorting the 1.1V core onto +3V3.

## Q6. Level shifting of the private V20<->MCU handshake (HOLD/HLDA/INTR/.../RD/WR).
- Why: these are 3.3V GPIO <-> 5V V20 signals but are not part of the buffered
  ISA group, so they don't pass through the bus '245s.
- Pick: route them directly to GPIO with their canonical net names (interface
  visible); note that the board adds a small fixed-direction '245 / 5V-tolerant
  buffering for them. IO/~{M} exceeds the 48-GPIO budget so it is exported as a
  hier pin only (not bonded to a GPIO here); the MCU infers cycle type from the
  buffered ~{MEMR}/~{IOR} strobes instead.

## GPIO22: CLK sense -> SPKR (design review 2026-07-11)
The audio sheet's SPKR net had NO driver anywhere (netlist: 1 node) -- the
soft-PIT ch2 speaker output was never brought out and the GPIO budget was
48/48. GPIO22 (bus-CLK sense, a diagnostics bonus from the C3 fix round, not
load-bearing: PIO tracks cycles from BALE/strobes) is reassigned as the SPKR
output, giving full port-61h direct-toggle fidelity from the PIT owner.
bus_mcu no longer lists CLK in its interface.

## Decoupling + spare-input cleanup (2026-07-11)
C8 was decoupling +3V3, a rail this sheet doesn't use -- now 3V3_BUS (typo).
Added C12-C17 (the +5V '244/'04 stage and the counter/xcvr banks had none or
shared one). U17 spare inverter inputs tied to GND (no_connect left them
floating on the real chip).
</content>
</invoke>

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

## Module-USB flashing made safe (2026-07-11)
The Core2350B's vendor schematic shows a single VBUS net -- no diode between
its on-module USB connector and the VBUS pin -- so the old direct +5V tie
meant plugging a PC in would back-power the whole board (board off) or
parallel two hard 5V supplies (board on). D1 (SS34) now feeds the module
Pico-style (+5V -> anode, VBUS_MCU -> cathode); the ME6217 LDO has ample
headroom at ~4.7 V. R16-R18 park DATADIR (B->A), M_TC (low) and HLDA (low)
while the MCU is Hi-Z in BOOTSEL/reset, so the always-enabled U2/U13
shifters can't drive the 5 V bus with indeterminate levels during flashing.

## IRQ collector extended to 16 bits (2026-07-11)
U19 (74HCT165) cascades into U12's DS, sampling IRQ10-IRQ15 (R19-R24 idle
pull-downs). Costs zero GPIO -- same IRQ_LOAD/IRQ_CLK/IRQ_SER, firmware
shifts 16 bits instead of 8. Motivation: the on-board storage now straps to
IRQ14 (AT primary-IDE convention) by default, which previously had no
physical path into the soft-PIC; this also un-dangles the IRQ10-15 pins the
sheet interface had declared all along. These lines are motherboard-internal
(the 60-pin header carries only IRQ2-8).

## 3.3V single-board redesign -- transceivers shed + EXT scan (2026-07-14, Task 5)

The bus is now 3.3V end to end (cpu_core already converted). The RP2350B GPIOs
are 5V-tolerant and tri-state natively, so they sit on the 3.3V bus DIRECTLY.

### D1. All SIX 74LVC245A deleted (brief said "3x"); 1:1 rewire, no GPIO moved.
The sheet actually had six '245s, not three: U2 data, U6 strobes, U3/U4/U5
address+BALE, U13 AEN/TC. Every one is a clean 1:1 channel map, so all six are
deleted and each MCU GPIO that fed a '245 MCU-side pin now carries the bus net
that '245 bridged (same GPIO):

| GPIO | old 245 channel        | bus net now on the GPIO |
|------|------------------------|-------------------------|
| 0-7  | U2  A0-A7 (MD0-7)      | D0-D7                    |
| 8-15 | U3  A0-A7 (MA0-7)      | A0-A7                    |
| 16   | U6  A0 (M_IOR)        | ~{IOR}                   |
| 17   | U6  A1 (M_IOW)        | ~{IOW}                   |
| 18   | U6  A2 (M_MEMR)       | ~{MEMR}                  |
| 19   | U6  A3 (M_MEMW)       | ~{MEMW}                  |
| 20   | U5  A4 (M_BALE)       | BALE                     |
| 21   | U13 A0 (M_AEN)        | AEN                      |
| 35   | U13 A1 (M_TC)         | TC                       |

A8-A19 are no longer sensed here: U4 and U5's upper channels were "unbonded
sense taps" (no GPIO on the MCU side), so deleting them rewires nothing. The
counter (via the '244s) remains the only master-cycle source of A8-A19.

### D2. GPIO43 (ex-DATADIR) freed -> EXP_DDIR. Only freed GPIO.
The '245 CHANNEL GPIOs above all stay in use (1:1). The only GPIO that frees up
is a DIR-driver: DATADIR (GPIO43), whose sole consumer was U2's direction pin.
Its park R16 is deleted with U2. Candidate list for EXP_DDIR: all 48 GPIO
(GPIO0-47) were assigned before this change; the only newly-free pin is GPIO43.
Pick: **GPIO43 = EXP_DDIR** (documented repurpose of the freed DIR pin, not a
silent one). U6's DIR was HLDA (GPIO26) which STAYS -- HLDA is still sensed and
still feeds U17 -> '244 ~OE. U3/U4/U5 DIR were tied to GND (no GPIO).

### D3. DEVIATION from brief Step 2: the '244 stage (U14-U16) is KEPT, not deleted.
Brief Step 2 says "the HCT244s buffered 3.3V MCU outputs onto the 5V bus --
delete them and wire the MCU GPIOs direct." That premise is wrong about what the
'244s do: they buffer the **counter** ('163) outputs, not MCU GPIO, and their
real job is the **tri-state output enable** (~OE = ~HLDA) that the '163 lacks.
Deleting them would leave the counter permanently driving A0-A19, fighting
cpu_core's '573 latches (OE = HLDA, confirmed in cpu_core.py:157-163) during
every CPU-owned cycle -- bus contention. This is exactly the dispatch's
"mixed duties you can't cleanly separate" case; the engineering-correct action
is to KEEP the '244s as the counter's tri-state, moved to +3V3 (value 74HC244).
U17 (the HLDA -> ~{HLDA} inverter feeding their ~OE) likewise stays, +3V3
(74HC04). Flagged for review; the alternative (a counter part with a built-in
OE) is a larger redesign not in scope.

### D4. Counters + all '165 move to 74HC at 3.3V -- fmax is fine.
U7-U11 ('161 counters) already valued 74HC161; VCC already 3V3_BUS; only the
load-data source changes MD0-7 -> D0-7 (GPIO0-7 sit on the data bus now).
U12/U19/U20 '165 -> value 74HC165, +3V3. U18 '08 stays (74HC08, 3V3_BUS) --
the CNT_RUN load-cascade guard is a real remaining function, not DIR logic.
74HC at 3.3V is safe here: the counter/scan clocks (CNT_CLK, IRQ_CLK) are slow;
Task-1 check-7's 3.3V fmax failure applied only to the 14.318 MHz cpu_core
clock dividers, which is why those (and only those) went LVC.

### D5. EXT scan chain order (firmware-visible -- documented in the sheet too).
Two more 74HC165 (U19, U20) extend the existing IRQ collector chain, wired
exactly like U12 (shared IRQ_LOAD/IRQ_CLK; serial cascade; ~{CE}=GND). Chain,
from the MCU serial-in pin outward (each '165 shifts D7 first):

    MCU(IRQ_SER) <- U12 <- U19 <- U20(DS=GND, end of chain)

Firmware clocks 24 bits: **U12 first (internal IRQ2-8 + IRQ14), then U19
(EXT_IRQ2..EXT_IRQ8), then U20 (EXT_DRQ1..EXT_DRQ3)**. U20 is furthest from the
MCU. Input assignment: U19 D0-D6 = EXT_IRQ2..8, D7 = GND; U20 D0-D2 =
EXT_DRQ1..3, D3-D7 = GND (6 unused inputs grounded). The EXT_* are the sidecar's
ISOLATED lines (PRIV_EXP) -- collected here, ORed into the soft-PIC/soft-8237 in
firmware, NEVER wired onto the internal IRQ/DRQ nets. R29-R38 idle them low so
the '165 inputs don't float when no sidecar is fitted.

### D6. Bus idle pull-ups moved +5V -> +3V3.
IOCHRDY, ~{IOCHCK}, ~{DACK2}, ~{DACK3} idle pulls were to +5V (old 5V bus);
now +3V3 (the bus rail). AEN/TC now come straight from GPIO21/35, so their
Hi-Z-window parks (R1=AEN low, R17=TC low) are kept; HLDA park (R18) kept
because HLDA also gates the '244s. C6/C7/C8 (decoupling for the deleted
data/addr/AEN '245s) removed; C10/C12-C15 moved +5V -> +3V3; C18/C19 added for
U19/U20.

## Task 10 final-review fixes (2026-07-14)

### F1. U17 (HLDA inverter) -> 74LVC04A: 5V input on a 3.3V part.
U17 ('04 @ +3V3) inverts HLDA to ~{HLDA} for the '244 ~OE. Its INPUT is HLDA,
which is a **5V push-pull output of the V20** (cpu_core U1 @ +5V). Plain 74HC04
is NOT 5V-tolerant -> value override to **74LVC04A** (5V-tolerant input, standard
'04 pinout on the same HCT04 body; parts.py binds C282341, Nexperia 74LVC04AD,118,
SO-14, ~1700 stock). Netlist: HLDA net includes U217.1; U217 value = 74LVC04A.

### F2. FIRMWARE CONTRACT -- HOLD is now ACTIVE-LOW at GPIO25.
cpu_core re-buffers the V20's READY/HOLD 5V-class inputs up from the 3.3V GPIO
drive through its spare U13 '04 gates (questions-cpu_core.md Q10). READY goes
through TWO gates (net non-inverting, no change). **HOLD goes through ONE
INVERTING gate**, so the V20 sees HOLD inverted. Therefore:

  ***FIRMWARE MUST DRIVE GPIO25 (HOLD) INVERTED -- assert a bus-master request
  by driving GPIO25 LOW, release by driving it HIGH.***

The mxbus "HOLD" contract NAME is intact bus-side (both sheets still call the
interface net HOLD; mxbus.PRIV_CPU unchanged) -- only the active SENSE flips.
Prominent comments are at the GPIO25 map entry here and at cpu_core U13. Netlist:
/HOLD = {M201.26 (GPIO25), U113.13 (U13 gate input)}.

---
**2026-07-14 (addendum to F1): U17 deleted entirely.** The 74LVC04A carried
1 of 6 gates; the HLDA -> ~{HLDA} inversion moved to the parallel sheet's
spare 74AHC14 Schmitt gate (U9 gate 1 there -- the board's only spare
5V-tolerant inverter), and ~{HLDA} now crosses as a PRIV_CPU interface net.
Park-safety unchanged (R18 parks HLDA low -> ~{HLDA} idles high -> '244s
off during MCU-Hi-Z). The 74LVC04A parts.py line (C282341) is deleted --
U17 was its only user. C15 (U17's decoupler) deleted with it.


---
**2026-07-14 (ERC-zero pass): IRQ6/IRQ8/EXT_IRQ8 formally RETIRED** --
resolving the IRQ8 repurpose-or-retire follow-up flagged in the PINS
comment. None of the three could ever be driven (IRQ6: firmware floppy
event, sidecar FDC arrives as EXT_IRQ6; IRQ8: firmware RTC, no header pin
since 2026-07-12; EXT_IRQ8: no header pin either). Their '165 lanes (U12
D4/D6, U19 D6) tie LOW at the SAME bit positions, so the firmware scan-bit
map is unchanged; pulls dropped (RN packs reshuffled to 7 full arrays).
This, plus the supervisor VDD_RTC PWR_FLAG, takes the board to ERC ZERO
(0 errors, 0 warnings) -- the standing bar is to keep it there.

## IRQ scan collapsed to one '165 + one '32; ISA-card DMA removed (2026-07-14, after the NIC removal)

User decision, three parts:

1. **EXT_DRQ1-3 deleted** (with U20, their '165): ISA-card DMA was never
   really supported -- only ch1 has a DACK, and it belongs to the on-board
   PicoGUS -- so the sidecar now leaves the header's DRQ1-3 AND ~{DACK1-3}
   pins unconnected (`isa_conn.place_header(nc=...)`; the DACKs were a
   second user pass the same day). Sidecar sheds its DRQ inbound '244 +
   3x 100k pulls AND a strobe-output '244 (the outbound group fell from
   10 lines to 7 without the DACKs -- fits one chip). Internal
   DRQ1/~{DACK1}/TC (PicoGUS ch1) are untouched; **DRQ2/3 + ~{DACK2/3}
   are retired as nets** (sidecar was ch2's last consumer; ch3's was the
   PicoGUS DMA jumper, deleted the same day -- see
   questions-picogus.md -- so ch1 is hardwired everywhere and is the only
   DMA channel that exists on the board).
2. **U19 became a 74HC32 OR rank**: the four internal IRQs that share a
   header pin with the expansion port merge in hardware --
   IRQn_ANY = IRQn | EXT_IRQn for n = 3/4/5/7 -- instead of occupying
   separate '165 lanes merged in firmware. Firmware loses the ability to
   tell internal from sidecar assertion; the soft-PIC ORed them anyway.
3. **U12 is the whole scan again** (DS = GND): D0 = EXT_IRQ2, D1-D3 =
   IRQ3/4/5_ANY, D4 = EXT_IRQ6, D5 = IRQ7_ANY, D6 = spare (low),
   D7 = IRQ14 -- the original pre-expansion 8-bit bit map, 8 clocks
   instead of 24.

Net: -2 '165, -2 '244 (sidecar), -1 RN pack, +1 '32. NCing the DACK pins
also ELIMINATES a hazard: a driven header DACK1̄ would have false-triggered
any card strapped to ch1 during on-board PicoGUS transfers -- now no
acknowledge can reach a card at all.

## GPIO47: ~{REFRESH} -> ~{EXT_DACK}; '165 D6 -> EXT_DRQ (2026-07-14, port DMA)

User decision (with the 50-pin sidecar header): ~{REFRESH} is RETIRED -- the
50-pin header has no room for it, no on-board device needs refresh (SRAM
board), and the planned ISA backplane re-creates it for DRAM cards. That frees
GPIO47 for **~{EXT_DACK}**, the expansion port's DMA acknowledge (park to
3V3_BUS in RN6, same as ~{DACK}). **EXT_DRQ** takes U12's spare D6 lane
(bit positions of all IRQs unchanged; RN6 gained its idle pull-down).
Internal ch1 renamed DRQ1/~{DACK1} -> DRQ/~{DACK}. The port-61h bit-4
refresh toggle was always firmware-only and is unaffected. (The alternative
considered -- reclaiming GPIO46 ~{RD} like the old ~WR reclaim -- was not
needed.)

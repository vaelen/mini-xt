# Bus MCU firmware specification (RP2350B soft chipset + bus master)

Standalone contract for the Bus MCU firmware, written so a separate firmware
repo needs no access to this hardware repo. Sources of truth it condenses:
`docs/xt-mcu-sbc-design.md` §5/§6/§11/§14, `hardware/sheets/bus_mcu.py` (the
authority on GPIO assignments), and `hardware/notes/questions-bus_mcu.md`. If
this file and the schematic ever disagree, the schematic wins — update this
file. Companion doc: `docs/video-firmware.md` (the video MCU).

## 1. What the card is

The **"fast hands"** node: a **Core2350B module (RP2350B, 48 GPIO — order the
0 MB-PSRAM variant**; GPIO47 is a bus signal here, so the PSRAM CS pin must be
free). It sits on the 3.3 V-native 8-bit ISA bus as **slave and master** and
emulates the whole PC/XT-to-AT chipset in firmware:

- Dual **8259A PIC** (cascaded, AT-style, 15 IRQs), **8254 PIT** (1.193182 MHz
  timebase synthesized internally — there is NO bus-clock input, see §10),
  **KBC** (XT 8255 or AT 8042, software-selectable), **8237 DMA** (functional,
  required by the PicoGUS), **RTC/CMOS at 0x70/0x71**, NMI mask, port-61h
  refresh toggle, POST 0x80 snoop, virtual COM3 serial mouse, and the
  tier-2 firmware-floppy registers.
- As **bus master** (HOLD/HLDA) it clears SRAM at boot, shadow-loads BIOS
  images, renders the pre-BIOS menu into the video card's 0xB8000 window, and
  runs DMA transfer cycles.

Its partner is the **Supervisor** (RP2040, off-bus: USB HID host, setup UI,
config + image storage, console, POST display), reachable ONLY via the 2-wire
UART link (§9). Suggested core split per the design doc: core 0 + PIO = the
hard-real-time bus engine; core 1 = the PIC/PIT/DMA/device state machines.

## 2. GPIO map

All bus signals are 3.3 V, wired to the GPIOs directly — no transceivers.
Master/slave role changes are firmware tri-state flips of the same pins.

| GPIO    | Net         | Dir (MCU view)   | Purpose                                                        |
|---------|-------------|------------------|----------------------------------------------------------------|
| 0-7     | D0-D7       | Bidir            | Data bus; also INTA vector out and counter-load bytes          |
| 8-15    | A0-A7       | In (bidir-cap.)  | Low address byte (A8/A9 on GPIO42/46 — full 10-bit I/O decode) |
| 16      | ~IOR        | Bidir            | Sense as slave, drive as master; active low                    |
| 17      | ~IOW        | Bidir            | Sense as slave, drive as master; active low                    |
| 18      | ~MEMR       | Bidir            | Sense as slave, drive as master; active low                    |
| 19      | ~MEMW       | Bidir            | Sense as slave, drive as master; active low                    |
| 20      | BALE        | In               | Cycle-start reference; address is valid/latched after it falls |
| 21      | AEN         | Out              | Drive HIGH during DMA cycles (cards ignore I/O decode); idle low |
| 22      | SPKR        | Out              | PIT ch2 / port-61h speaker (PWM/PIO) → audio op-amp summer     |
| 23      | IOCHRDY     | Bidir            | Sense (fold into READY, honor as master); open-drain if driven |
| 24      | ~IOCHCK     | In               | Card error input, active low → NMI (if unmasked)               |
| 25      | HOLD        | Out, **INVERTED**| ***Drive LOW to request the bus, HIGH to release*** (see §6)   |
| 26      | HLDA        | In               | Bus grant from V20, active high                                |
| 27      | INTR        | Out              | Interrupt request to V20, active high                          |
| 28      | ~INTA       | In               | V20 interrupt-acknowledge strobe; vector goes out on D0-D7     |
| 29      | NMI         | Out              | NMI to V20, active high                                        |
| 30      | IRQ_LOAD    | Out, active low  | '165 parallel-load strobe (IRQ scan, §5)                       |
| 31      | IRQ_CLK     | Out              | '165 shift clock                                               |
| 32      | IRQ_SER     | In               | '165 serial data (D7 first)                                    |
| 33      | DRQ         | In               | DMA request — hardwired to the on-board PicoGUS (ch1)          |
| 34      | ~DACK       | Out, active low  | DMA acknowledge to the PicoGUS; idle HIGH                      |
| 35      | TC          | Out              | DMA terminal count pulse, active high; idle low                |
| 36      | CNT_CLK     | Out              | Address-counter clock (load + increment, §4)                   |
| 37      | CNT_LD0     | Out, active low  | Counter load strobe, bits 0-7 lane                             |
| 38      | CNT_LD1     | Out, active low  | Counter load strobe, bits 8-15 lane                            |
| 39      | CNT_LD2     | Out, active low  | Counter load strobe, bits 16-19 lane (shares module user LED)  |
| 40      | LINK_B2S    | Out (UART TX)    | Link to Supervisor (§9)                                        |
| 41      | LINK_S2B    | In (UART RX)     | Link from Supervisor                                           |
| 42      | A8          | In               | Address bit 8 (was SPEED_SEL — now a cpu_core jumper)          |
| 43      | EXP_DDIR    | Out              | Expansion-port data direction: HIGH = outbound (safe default), LOW = inbound |
| 44      | READY       | Out              | V20 READY (net non-inverting; high = ready)                    |
| 45      | ~CPURESET   | Out, active low  | LOW = V20 held in reset (parked low until firmware acts)       |
| 46      | A9          | In               | Address bit 9 (was the raw ~RD sense — redundant, dropped)     |
| 47      | ~EXT_DACK   | Out, active low  | Expansion-port DMA acknowledge; idle HIGH (separate from ~DACK) |

Non-GPIO: module powers itself from bus +5V through a Schottky (module-USB
flashing is safe and cannot back-power the board); SWD and module-USB are
available for development.

## 3. Startup safe state

External pulls park the bus while the MCU is Hi-Z (BOOTSEL/pre-init): AEN low,
TC low, ~CPURESET low (V20 stays in reset), ~DACK/~EXT_DACK high, EXP_DDIR
high (port outbound-safe), IOCHRDY/~IOCHCK idle high, all IRQ/DRQ inputs idle
low. Firmware's FIRST act is to reproduce that state actively: strobes/data/
address as inputs, AEN low, TC low, ~DACK+~EXT_DACK high, EXP_DDIR high,
HOLD **HIGH** (= released, inverted pin!), READY high, ~CPURESET low, SPKR
low. Only then bring up clocks and the bus engine.

## 4. The external 20-bit address counter (master-cycle addresses)

Five cascaded 74HC161s hold and drive A0-A19 during master cycles, so the MCU
never spends GPIOs on high address bits. Their outputs reach the bus through
74HC244s gated by ~HLDA — the counter is physically off the bus except while
the V20 has granted HOLD (the '573 CPU-address latches enable in the opposite
phase; the handoff is contention-free by construction).

Protocol (all synchronous to CNT_CLK rising edges; '161 load is SYNCHRONOUS):

- **Load** (3 byte lanes): drive the byte on D0-D7 (GPIO0-7), assert ONE of
  CNT_LD0/1/2 LOW, pulse CNT_CLK, release. A hardware AND gate (CNT_RUN =
  LD0·LD1·LD2) freezes the non-loading stages during any load pulse, so lanes
  can be loaded in any order without the others counting. Lanes: LD0 = A0-A7,
  LD1 = A8-A15, LD2 = A16-A19.
- **Increment**: with all CNT_LD* high, one CNT_CLK pulse = address + 1. All
  master transfers are sequential by design (shadow-load, DMA blocks, menu
  writes); random addressing means a 3-lane reload.
- The MCU's A0-A9 GPIOs stay INPUTS during master cycles — the counter (not
  the MCU) drives the address bus.

## 5. The IRQ scan chain

One 74HC165 collects all physical interrupt/DMA-request lines onto 3 pins.
Pulse IRQ_LOAD low, then read IRQ_SER and clock IRQ_CLK 7 more times; bits
arrive **D7 first**:

| Shift order | '165 input | Signal    | Meaning                                            |
|-------------|------------|-----------|----------------------------------------------------|
| 1st         | D7         | IRQ14     | XT-IDE storage (AT primary-IDE convention)         |
| 2nd         | D6         | EXT_DRQ   | Expansion-port DMA request (NOT an IRQ)            |
| 3rd         | D5         | IRQ7_ANY  | LPT1 — internal OR expansion (hardware-ORed)       |
| 4th         | D4         | EXT_IRQ6  | Expansion port only (internal floppy is fw event)  |
| 5th         | D3         | IRQ5_ANY  | PicoGUS — internal OR expansion                    |
| 6th         | D2         | IRQ4_ANY  | COM1 — internal OR expansion                       |
| 7th         | D1         | IRQ3_ANY  | COM2 — internal OR expansion                       |
| 8th         | D0         | EXT_IRQ2  | Expansion port only → deliver as IRQ9 (IRQ2 redirect) |

All lines are active-high with idle pull-downs. A 74HC32 rank ORs internal
IRQ3/4/5/7 with their expansion-port twins BEFORE the '165 — firmware cannot
tell internal from sidecar assertion (the soft-PIC ORed them anyway).
Microsecond-rate polling is fine: ISA devices hold their IRQ until serviced.
IRQ0 (PIT), IRQ1 (KBC), IRQ4-as-mouse, IRQ6 (fw floppy), IRQ8 (RTC), IRQ12
(PS/2 mouse) are firmware-internal soft-PIC events with no physical line.

## 6. Polarity contracts (get these wrong and nothing works)

- **HOLD (GPIO25) is ACTIVE-LOW at the pin.** The motherboard re-buffers this
  net through one INVERTING 74HCT04 gate to reach the V20's 5 V-class HOLD
  input. Request the bus by driving GPIO25 LOW; release with HIGH. The net is
  still named "HOLD" everywhere — only the sense at this GPIO is flipped.
- READY (GPIO44) passes through TWO gates (non-inverting net): high = V20 runs,
  low = wait states. Firmware folds IOCHRDY (GPIO23) into READY during CPU
  cycles — this is a PIO-speed fast path, not a mainloop job.
- ~CPURESET (GPIO45): LOW holds the V20 in reset. The park keeps it low from
  power-on; firmware raises it only at boot-sequence step 6 (§8).
- ~DACK (GPIO34) / ~EXT_DACK (GPIO47): active low, MUST idle high. They are
  deliberately separate nets — an expansion card must never see the PicoGUS's
  acknowledge and vice versa.
- AEN (GPIO21): drive HIGH for the duration of DMA master cycles so cards
  ignore their I/O decode; LOW at all other times.
- CPU speed is NOT firmware-controlled (since 2026-07-20): it's a hardware
  jumper on the cpu_core sheet (JP1 there — open = 7.16 MHz default, fitted =
  4.77 MHz). No GPIO, no link message, no setup-menu item.

## 7. Bus-cycle handling

**Slave cycles (CPU → emulated chipset).** PIO watches BALE and the four
strobes (there is no bus-clock GPIO — all timing derives from BALE/strobes).
On ~IOR/~IOW low with AEN low: capture A0-A9, match against the emulated port
set (§11), and for reads drive the response byte on D0-D7 for the strobe
duration; stretch via IOCHRDY/READY only if the answer can't be produced in
time (register reads should be precomputed — keep 0-wait). The V20 min-mode
interrupt acknowledge arrives as ~INTA (GPIO28) pulses: classic 8088 timing is
two INTA cycles, vector driven on D0-D7 during the second.

**Master cycles.** Sequence: raise HOLD request (GPIO25 LOW) → wait for HLDA
high → the counter's '244s now own A0-A19 → load counter (§4) → per byte:
drive/sample D0-D7, pulse the relevant strobe (~MEMW for shadow-load writes,
~MEMR+~IOW pair for DMA mem→I/O, etc.), pulse CNT_CLK → when done, release
HOLD (GPIO25 HIGH), strobes back to inputs. Honor IOCHRDY as a master: a
wait-stated card stretches your cycle too.

**DMA engine (8237 emulation, the master-cycle reuse).** PicoGUS raises DRQ
(GPIO33); per the programmed 8237 ch1 state: acquire the bus, assert AEN,
assert ~DACK, run mem→I/O cycles (counter drives the address, SRAM drives the
data under ~MEMR, PicoGUS takes it on ~IOW — the MCU drives neither address
nor data, only strobes and CNT_CLK), pulse TC on terminal count, release.
The expansion-port channel (EXT_DRQ via the scan, ~EXT_DACK on GPIO47) runs
the same engine — map it as 8237 ch3 (ch1 is the PicoGUS; ch0/ch2 unused).
Page registers 0x80-0x83 apply as on a real XT.

## 8. Boot sequence duties (design doc §6)

1. Power-on: reset supervisor releases both MCUs; ~CPURESET park already holds
   the V20. Firmware enters safe state (§3), starts the link.
2. As bus master: **clear all SRAM** (0x00000-0xFFFFF) so the option-ROM scan
   finds no stray 0x55AA.
3. Supervisor streams menu-draw commands; render them as master writes to the
   video card's 0xB8000 text buffer. Forward keystrokes/POST both ways.
4. On setup exit: accept CMOS-write requests over the link into the emulated
   CMOS (§12).
5. Supervisor streams BIOS + option-ROM images (video BIOS @0xC0000, XTIDE
   @0xC8000, main BIOS); shadow-load each into SRAM via master writes.
6. Release ~CPURESET (per the reset-sandwich choreography, §13). The V20 boots
   the Xi 8088 BIOS from RAM. Runtime: HID events keep arriving over the link
   into the KBC/mouse emulation. (CPU speed is a hardware jumper — nothing to
   set here.)

## 9. The Supervisor UART link

GPIO40 (TX) / GPIO41 (RX), full-duplex, software-framed (length-prefix + CRC —
frame format is a firmware-repo decision, shared with the Supervisor repo).
Run it at multi-Mbaud (PIO UART if the hard peripheral tops out): the 128 KB
image push at boot should take ~0.1-0.4 s. Traffic: images (S→B, boot),
HID events (S→B, runtime), menu-draw (S→B, pre-BIOS), POST codes (B→S),
CMOS-write requests (S→B), time-of-day sync (S→B, boot, from the PCF8563),
config selections (S→B; CPU speed is NOT among them — it's a jumper).

## 10. Emulated device notes

- **PIT**: 1.193182 MHz timebase synthesized from sysclk (no bus clock
  exists). Ch0 → soft-PIC IRQ0; ch2 → SPKR (GPIO22) gated by port 0x61 bits
  0/1; the 0x61 bit-4 refresh toggle free-runs at ~66 kHz (firmware-internal,
  some POSTs check it).
- **KBC**: XT 8255 (scan set 1) or AT 8042 (set 2 + 0x64 command port) per
  config; fed by HID events from the link. Mouse: virtual 16550 at COM3
  0x3E8/IRQ4 (default) or 8042-aux PS/2 on IRQ12.
- **NMI**: sources are ~IOCHCK (GPIO24) and parity-style events (none exist);
  masked by port 0x70 bit 7 (AT-style — there is no XT 0xA0 mask; 0xA0 is the
  slave PIC).
- **POST**: snoop writes to 0x80, forward each byte over the link (Supervisor
  drives the hex display).
- **Firmware floppy**: 0x3F0-0x3F7 reserved for the tier-2 register interface
  (design doc §10.1); raises IRQ6 as a soft-PIC event, uses no DMA.

## 11. I/O decode

Ports owned by this MCU: 0x00-0x0F (DMA), 0x20/21 + 0xA0/A1 (PICs), 0x40-43
(PIT), 0x60-64 (KBC), 0x70/71 (RTC/CMOS + NMI mask), 0x80-83 (page regs +
POST), 0x3E8-0x3EF (COM3 mouse), 0x3F0-0x3F7 (fw floppy). Everything else
(COM1/2, LPT, IDE, PicoGUS, video) decodes elsewhere — do not answer it.

**A0-A9 are all sensed** (A0-A7 on GPIO8-15, A8 on GPIO42, A9 on GPIO46 —
since 2026-07-20), so the firmware does the full 10-bit ISA I/O decode and
the old 8-bit aliasing hazard (0x020 vs the PicoGUS's 0x220; COM3 0x3E8 vs
an expansion COM4 0x2E8) is gone. Decode order per cycle: strobe type first
(memory cycles never touch the port machinery), then AEN (DMA cycles are not
port accesses), then the 10-bit address. A10-A15 are deliberately not sensed:
I/O above 0x3FF aliases down mod 0x400, which is authentic ISA 10-bit-decode
behavior shared by every device on the bus.

## 12. RTC / CMOS (0x70/0x71)

Fully emulated here — index at 0x70 (bit 7 doubles as the NMI mask on
writes), data at 0x71. Time-of-day arrives once at boot from the Supervisor
(PCF8563-backed) and free-runs on the RP2350 afterward. CMOS config bytes:
RAM copy here, persistence in SUPERVISOR flash — on CMOS writes, echo the
change over the link; on boot, receive the stored image. Standard AT CMOS
layout (Xi 8088 BIOS pairing).

## 13. Constraints and gotchas summary

- HOLD is inverted at the pin (§6). The single most likely bring-up bug.
- No bus-clock input: PIO cycle tracking is from BALE + strobes only; the PIT
  timebase is synthesized.
- GPIO budget is 48/48 — there are no spare pins. The nearest reclaim
  candidates if one is ever needed: ~IOCHCK and DRQ could move to '165 scan
  lanes (both tolerate µs poll latency).
- **Boot-time bus mastering needs the reset sandwich** (resolved 2026-07-19
  from the µPD70108H datasheet §1.2: HLDAK is driven LOW throughout RESET —
  the V20 will NOT grant a hold while in reset, so "master the bus with the
  V20 held in reset" cannot be taken literally). Sequence: assert HOLD
  (GPIO25 LOW) while ~CPURESET is still low → release ~CPURESET → the V20
  exits reset with the request pending and grants HLDA at the first bus-idle
  opportunity (HLDRQ outranks INT and NMI; worst case it completes one
  harmless read-only fetch from FFFF0 first — it can never write, because
  executing anything needs bus cycles the hold blocks) → do ALL master work
  under this held V20 → re-assert ~CPURESET (reset overrides hold) → release
  HOLD → ≥4 CLKs of reset → release ~CPURESET for the real boot from loaded
  RAM. Bench-verify the first-fetch race once, then trust it.
- One '165 load+shift per poll; don't wire an IRQ latency assumption tighter
  than the scan period.
- GPIO39 (CNT_LD2) doubles as the module user LED — expect it to blink during
  counter loads; don't use LED examples.
- The expansion port has no bus-master arbitration: EXP_DDIR (GPIO43) is the
  only thing preventing data-bus contention with a port card. Set it inbound
  (LOW) only around reads a port card serves; default outbound (HIGH).
- Emulated-CMOS writes must round-trip to the Supervisor or they are lost on
  power-off (persistence lives in Supervisor flash).

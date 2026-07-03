# XT-Class SBC — MCU-Hybrid Design Notes

An **alternate** design for a DOS-compatible, XT-class single-board computer built
around the **NEC V20**, that deliberately **replaces the out-of-production Intel
8000-series support chips with modern microcontrollers** (Raspberry Pi RP2350B /
RP2040) and an on-board **PicoGUS**, while keeping the parts already on hand real.

Where the companion `xt-hardware-design.md` is "distinct period chips, education over
emulation," **this design optimizes for buildability with available parts**: the goal is
to need *as few out-of-production ICs as possible*. After this exercise, **the only
irreplaceable vintage silicon left is the V20 itself.**

See companion docs: `xt-hardware-design.md` (the period-chip build), `early-pc-cpus.md`,
`memory-management.md`, `pc-generations.md`.

Design date: 2026-06-28.

---

## 1. Design summary / decisions locked

| Area | Decision |
|---|---|
| CPU | NEC **V20** (µPD70108, **9 MHz grade**) in **min mode** (no 8087 → no 8288, no 8284) |
| Clock | **Single 14.31818 MHz oscillator**; ÷2 = 7.16 MHz (74HC74), ÷3 = 4.77 MHz (74HC4017) |
| CPU speed | **7.16 MHz** default, **4.77 MHz** turbo-down (selected in the boot menu, CPU held in reset) |
| Reset / power-good | Supervisor (TL7705A/MAX809) cold-start; **Bus MCU sequences reset** |
| RAM | **2× AS6C4008-55** SRAM (640 KB conventional + UMB); video RAM lives in the video MCU |
| ROM / BIOS | **None on board** — BIOS **shadow-loaded into SRAM** by the Bus MCU at boot |
| Bus | Buffered **8-bit XT/ISA backplane**; expansion via a **2×32 IDC "sidecar" header** |
| Support chipset | **Two-MCU split**: **Bus MCU (RP2350B)** soft-emulates PIC (×2, 15 IRQ), PIT, KBC, **functional DMA**, NMI, POST as bus master/slave; **Supervisor (RP2040)** runs USB/config/storage off-bus (§5) |
| Chipset link | **2-wire full-duplex UART** between Bus MCU ↔ Supervisor (boot image push + HID/menu/POST events) |
| Video | **RP2350B** soft CGA/MDA/Hercules (snoop-and-mirror), **VGA + HDMI** out (config-selected) |
| Audio | **On-board PicoGUS (RP2040, stock firmware)** — AdLib/SB/GUS/MPU/etc. + joystick |
| Input | **USB-A HID host** on the **Supervisor** MCU (keyboard; mouse via user's hub) |
| Mouse | Emulated **virtual COM3 serial mouse** (default) or **PS/2 on IRQ12** (option) |
| Storage | Discrete **XT-IDE** (8-bit, Chuck-mod) + CompactFlash; XTIDE Universal BIOS |
| Serial | **2× 16C550** + **MAX3241** (full DB9); TTL console header on COM1 |
| Parallel | Discrete **74HC** LPT @ 0x378 |
| RTC | **DS12C887** (integral battery + crystal) @ 0x70/0x71 |
| Config | **Pre-BIOS setup menu** (Supervisor MCU), shown on **video + MCU console**, entered by keypress |
| BIOS | **Xi 8088** (Sergey Kiselev), expected to be **forked** for our chipset |
| Debug | **2-digit hex POST display** (port 0x80), MCU console, logic-analyzer header |
| Power | Single **5 V in** (USB-C) → on-board **3.3 V buck**; no ±12 V |

**MCU count: 2× RP2350B** (Bus MCU, video) **+ 2× RP2040** (Supervisor, PicoGUS).
The chipset is deliberately split across two MCUs (§5) for clean separation: the **Bus MCU**
owns all hard-real-time bus work, the **Supervisor** owns the USB stack, setup UI, and
BIOS-image storage off-bus. The two *we* develop on RP2350B (Bus MCU) and RP2040 (Supervisor)
are independent; PicoGUS stays stock.

---

## 2. Philosophy & architecture

The organizing idea: **the buffered 8-bit XT/ISA bus is the integration contract.**
The V20 plus minimal 74HCT glue creates a real XT bus on the board; every function then
hangs off it either as a **real chip** (what we already have) or as an **MCU "soft card"**
that talks the bus exactly as a period ISA card would — each with its own local level
shifters, exactly like PicoGUS. This makes each subsystem independently developable,
testable, and (for the video and sound cards) **liftable onto a standalone ISA card later.**

Three classes of node:

1. **The "motherboard" — a two-MCU chipset** (the one special, non-card node). It turns the
   V20 into an XT and is split by timing domain (§5):
   - **Bus MCU (RP2350B) — "fast hands."** All hard-real-time bus work: PIC, PIT, KBC, DMA,
     NMI, POST, the shadow-load engine. A bus *slave* (answers I/O) **and** a bus *master*
     (boot shadow-load, sound DMA, pre-BIOS menu rendering). Never touches anything but the
     bus and its glue (counter, IRQ shift register) and the link to the Supervisor.
   - **Supervisor (RP2040) — "slow brain."** Off the system bus entirely: USB HID host, setup
     UI, persistent config, BIOS/option-ROM image storage, console, POST display. Talks to
     the Bus MCU only over a **2-wire full-duplex UART** (§5.3).
2. **Soft cards** — the **video** card (RP2350B) and **PicoGUS** (RP2040). Pure ISA
   peripherals on the bus.
3. **Real period-style chips** — V20, 2× AS6C4008 SRAM, 2× 16C550, DS12C887, plus
   discrete 74HCT for the bus, LPT, and XT-IDE.

**Portability contract.** A **soft card** (class 2) may use **only signals that exist on the
ISA bus** — it self-decodes its own address ranges and coordinates solely through standard
lines (`MEMR̄/MEMW̄/IOR̄/IOW̄`, `BALE`, `AEN`, `IOCHRDY`, `IRQ`, `DRQ/DACK/TC`, `CLK`, `RESET`).
No private motherboard side-channels, no dependence on host memory. This is the rule that
keeps the video card and PicoGUS **liftable to a standalone ISA board unchanged**, and it is
binding on any future soft card. The **class-1 motherboard MCUs are explicitly exempt** — they
*are* the motherboard: the Bus MCU bus-masters via `HOLD/HLDA`, sequences reset, and owns
motherboard-only signals (the SRAM-decode Y5 strobe, the speed-select latch, the external
address counter), and the Supervisor never sits on the bus at all. Neither is intended to
leave the board. Class-3 parts are fixed motherboard hardware and out of scope for the rule.

### Block diagram

```
        14.31818 MHz osc ──┬─ ÷2 (74HC74)   → 7.16 MHz ─┐
                           │                             ├─ 74HC157 sel ─ 5V buf ─► V20 CLK
                           ├─ ÷3 (74HC4017) → 4.77 MHz ─┘   ▲ (MCU speed GPIO, boot only)
                           └──────────────────────────────────────────────► ISA OSC pin (B30)

   ┌─────────┐  RD/WR/IO-M, ALE, HOLD/HLDA
   │   V20   │  (min mode)
   │ 8088-cmp│
   └────┬────┘
   AD bus│ multiplexed
   ┌─────┴───────────┐
   │ 74HCT573 ×3 latch│ → A0–A19 ┐
   │ 74HCT245 xceiver │ ↔ D0–D7  │   buffered 8-bit XT/ISA backplane
   └─────────────────┘          │   (+ MEMR/W, IOR/W, ALE, AEN, CLK, OSC, RESET,
        ┌───────────────────────┴────IOCHRDY, IOCHCK, IRQ, DRQ/DACK, +5V, GND)
        │
  ┌─────┼───────┬──────────────┬──────────────┬───────────┬──────────────┐
┌─┴──┐┌─┴──┐ ┌──┴─────────┐ ┌──┴─────────┐ ┌───┴────┐ ┌────┴─────┐  ┌─────┴──────┐
│SRAM││SRAM│ │  BUS MCU   │ │  VIDEO MCU │ │PicoGUS │ │ 2×16C550 │  │ 2×32 IDC   │
│ #1 ││ #2 │ │  RP2350B   │ │  RP2350B   │ │ RP2040 │ │ +MAX3241 │  │ sidecar    │
│512K││512K│ │ PIC/PIT/   │ │ CGA/MDA/   │ │ stock  │ │ COM1/2   │  │ (ISA bus   │
│ ×8 ││ ×8 │ │ KBC/DMA/   │ │ Herc snoop │ │ AdLib/ │ └──────────┘  │  off-board)│
└────┘└────┘ │ NMI/POST/  │ │ +mirror →  │ │ SB/GUS │ ┌──────────┐  └────────────┘
   ▲         │ boot-master│ │ VGA + HDMI │ │ +joy   │ │ XT-IDE   │
   │         └──┬──────┬──┘ └────────────┘ └───┬────┘ │ + CF     │
 74HC138        │      │ ▲  (owns video RAM)   │I2S   └──────────┘
 +NAND          │ glue:│ │UART link          PCM5102A  ┌──────────┐
 (SRAM /CE)     │ 5×'163│ │(2-wire,            audio    │ disc. LPT│
                │ counter│ │ full-duplex)   PC-spkr ─┐  │ @0x378   │
                │ '165   │ │                op-amp ──┴─►└──────────┘
                │ IRQ-in │ ▼                summer → line-out
                │     ┌──┴──────────┐
                │     │ SUPERVISOR  │  USB-A host (kbd/mouse hub)
                │     │   RP2040    │  setup UI · config (flash)
                │     │ off the bus │  BIOS/opt-ROM images (flash)
                │     │             │  console UART · POST display
                │     └─────────────┘
   DS12C887 RTC @0x70/71 · 2-digit hex POST @0x80 (Supervisor-driven) · 5V→3.3V buck
```

---

## 3. CPU, min mode, and clock

### 3.1 V20 in min mode
The part on hand is a **9 MHz-grade µPD70108**, comfortably above the 7.16 MHz default
(a 5 MHz part would not qualify). `MN/MX̄` strapped high. The V20 directly drives `RD̄`, `WR̄`, `IO/M̄`, `ALE`, `DEN̄`,
`DT/R̄`, `INTĀ`, and crucially **`HOLD`/`HLDA`** — the clean bus-grant handshake the
Bus MCU uses for all bus-master work. Min mode means **no 8288** (the CPU makes its
own control signals) and **no 8087** (dropped; software FP emulation if ever needed), and
since the clock no longer comes from an 8284, **no 8284 either**. Three vintage chips gone.

### 3.2 Single-oscillator clock tree
One **14.31818 MHz** canned oscillator does everything:

- **÷2 (74HC74)** → **7.15909 MHz**, clean 50 % duty → default CPU/bus clock.
- **÷3 (74HC4017 Johnson counter, Q3→MR)** → **4.77273 MHz**, ~33 % duty → turbo-down.
  A single flip-flop can't ÷3; the 4017 self-resetting at count 3 does it in one chip, and
  the 33 % duty is within the V20's clock spec (it is exactly what the 8284 supplied the
  original 8088). *(A 74HC161/163 preset to divide-by-3 is an equivalent substitute.)*
- A **74HC157** (one section) selects 7.16 vs 4.77; **its select line is a chipset-MCU GPIO**.
- **Speed is changed only in the MCU pre-BIOS boot menu**, while the V20 is held in reset —
  never live during execution. Because the mux select only ever moves while the CPU is in
  reset, the runt clock pulse a plain 74HC157 would produce on switching is harmless (no
  glitch-free PLD needed); the new divisor is settled before reset is released.
- The raw 14.318 also drives the **ISA OSC pin (B30)** for any real card on the sidecar.

**CLK level note:** the V20 clock input wants a near-Vcc swing (Vih ≈ 0.7–0.8 × Vcc), so
the mux output is buffered by a **5 V-powered 74-series gate** to meet it. This is also why
the MCU cannot drive the CPU clock directly (its 3.3 V pins won't meet Vih).

Because the **PIT is emulated in the Bus MCU**, the all-important **1.193182 MHz**
timer rate is synthesized internally and is *independent* of the CPU clock — none of the
old colorburst divider math is needed. The video MCU likewise makes its own pixel clocks.

### 3.3 Reset
A cold-start supervisor (TL7705A/MAX809) holds the board in reset until rails are stable.
Thereafter the **Bus MCU sequences the V20's reset**: it holds the V20 in reset
through its own boot, the pre-BIOS menu, and the BIOS shadow-load, then releases it.

---

## 4. The bus and the sidecar

### 4.1 Buffered 8-bit XT/ISA backplane
- **74HCT573 ×3** latch A0–A19 (gated by ALE); **74HCT245** buffers D0–D7.
- **SRAM chip-select decode — discrete 74HC, no PLD.** The 128 KB memory-map boundaries
  fall exactly on a **74HC138** (3→8) fed by latched **A17→A, A18→B, A19→C** (enables tied
  active). Each output is one 128 KB block (Y0–Y3 = SRAM #1, Y4/Y6/Y7 = SRAM #2,
  **Y5 = 0xA0000–0xBFFFF = video MCU**). The selects then reduce to almost nothing:
  - **SRAM #1 /CE = latched A19** (direct wire — A19=0 is all of 0x00000–0x7FFFF).
  - **SRAM #2 /CE = NAND(A19, Y5)** (one 74HC00 gate — low only when A19=1 *and* not the
    video block).
  - **Y5 is motherboard-internal** (it only feeds the SRAM #2 decode). The video subsystem
    **self-decodes** its 0xA0000–0xBFFFF window from latched A17–A19, using **no signal that
    isn't on the ISA bus**, so it stays a self-contained card that can be lifted to a
    standalone ISA board unchanged (§8).
  - Both SRAMs share latched A0–A18 and buffered D0–D7; **/OE = MEMR̄, /WE = MEMW̄**.
  No I/O-cycle qualification is needed: during I/O cycles MEMR̄/MEMW̄ are inactive, so the
  SRAM data pins stay high-Z even if a /CE happens to be asserted (no contention, no spurious
  write). The decode reads *latched* address, so it is identical under V20 or bus-master
  (MCU) ownership. This logic plus the latches/transceiver are in the **fast CPU critical
  path** and stay as hardware. (Total memory decode: **one 74HC138 + one NAND gate.**)
- In min mode the V20's `IO/M̄ + RD̄ + WR̄` are gated into `MEMR̄/MEMW̄/IOR̄/IOW̄`.
- **Wait states:** each soft card pulls **IOCHRDY** to buy time on a read; the Bus MCU
  (or a 74HC74) folds all IOCHRDY/ready signals back to the V20's READY input. 55 ns SRAM
  runs 0 wait at 7.16 MHz.

### 4.2 Level shifting
Every MCU is 3.3 V on a 5 V bus, so **each soft card has its own local level shifters**
(74LVC-class / the PicoGUS pattern). This is self-contained per card and is what makes a
card liftable to a standalone ISA board unchanged. **SN74LVC245A** octal transceivers are
the workhorse: powered at 3.3 V with 5 V-tolerant inputs, their 3.3 V output-high still
meets the bus's TTL Vih (2.0 V), so they drive a 5 V bus cleanly in both directions.

**Slave vs. master is the catch.** A pure-slave card (PicoGUS, the video MCU) only ever
*drives the data bus on reads* and *receives* everything else — its shifters have fixed or
simply-gated direction. The **Bus MCU is also a bus master** (boot shadow-load, sound
DMA, pre-BIOS rendering): when it owns the bus it must *drive* A0–A19, MEMR̄/MEMW̄/IOR̄/IOW̄,
and AEN that it otherwise only listens to. So the Bus MCU needs **bidirectional**
transceivers on the address and control groups with a **DIR line that flips with bus role
(master vs. slave)**, not just the data transceiver a slave card needs. Budget the extra
'LVC245A channels and the role-driven DIR logic for the chipset node accordingly (it is by
far the heaviest level-shifter consumer on the board).

### 4.3 Sidecar expansion header
Instead of on-board slots, a **2×32 (64-pin) 2.54 mm IDC header** carries the **full
buffered 8-bit ISA signal set** with interleaved grounds:

- A0–A19, D0–D7
- MEMR̄/MEMW̄/IOR̄/IOW̄, BALE, AEN
- CLK (7.16), OSC (14.318), RESET DRV
- IOCHRDY, IOCHCK̄
- IRQ2–7 (+ a few extended lines from the soft-PIC)
- DRQ1–3 / DACK1–3̄ / TC (wired to the Bus MCU so its emulated 8237 can service a real
  DMA card)
- +5 V and many grounds; a **key pin** prevents reversed insertion.

A future **backplane re-buffers** the bus to drive multiple slots, so the on-board
245/573 only ever drive the cable + one re-buffer. At 7.16 MHz over a short ribbon this is
comfortable. (±12 V for arbitrary ISA cards, if wanted, is brought by the backplane.)

---

## 5. Chipset — a two-MCU split (Bus MCU + Supervisor)

The "motherboard" is **two MCUs split by timing domain**, not one. The single-chip version is
feasible but **pin-bound** on a 48-GPIO RP2350B (≈47/48 with glue), and welds the hard-real-
time bus engine to the USB stack, filesystem, and setup UI on the same die. Splitting by
*what must happen in a bus cycle* vs. *what's complex but not timing-critical* keeps each half
clean and independently developable:

- **Bus MCU (RP2350B) — "fast hands."** Sits on the system bus as slave **and** master.
- **Supervisor (RP2040) — "slow brain."** Off the bus entirely; reachable only via the §5.3
  UART link.

The split does **not** relieve the Bus MCU's pins (those are set by the bus role and can't
move off-bus) — its value is firmware isolation, freeing both Bus MCU cores for bus/DMA work,
and a comfortable home for USB/storage/config on the RP2040. The Bus MCU still leans on two
cheap solder-only helpers (no PLD): a **loadable address counter** for bus-master cycles
(§5.1) and a **74HC165** to collect the ~10–12 IRQ inputs onto 3 pins.

### 5.0 Function assignment

| Function | Node | Emulates | Ports / lines |
|---|---|---|---|
| Interrupt controller | **Bus** | **Dual 8259A, cascaded, AT-style 15 IRQ** | 0x20/21, 0xA0/A1; INT 08–0F / 70–77; IRQ2→9 redirect |
| Timer | **Bus** | **8254 PIT**, 1.193182 MHz synthesized internally | 0x40–0x43; ch0 tick, ch2 → PC speaker |
| Keyboard controller | **Bus** | **XT 8255** *or* **AT 8042** (software-selectable) | 0x60/0x61(/0x64) |
| Mouse (register side) | **Bus** | **virtual COM3 16550** *or* **8042 aux PS/2** | 0x3E8/IRQ4 *or* IRQ12 |
| DMA | **Bus** | **8237 — functional** (required by PicoGUS SB/GUS) | 0x00–0x0F, page regs |
| NMI mask | **Bus** | **port 0x70 bit 7** (AT-style — 0xA0 is the slave PIC) | 0x070 bit 7 |
| Refresh toggle | **Bus** | **port 0x61 bit 4** free-running toggle (~66 kHz) | 0x061 bit 4 |
| POST capture | **Bus** snoops 0x80 → forwards code over the link | |
| Speaker | **Bus** | PIT ch2 tone (PWM/PIO) → 1 pin → op-amp summer | |
| Boot/bus master | **Bus** | HOLD/HLDA: SRAM clear, shadow-load, pre-BIOS render | |
| **USB HID host** | **Super** | (TinyUSB) keyboard + mouse → HID events over the link | |
| **Setup UI + config** | **Super** | menu state machine; settings in its flash | |
| **Image storage** | **Super** | BIOS + option-ROM images in its QSPI flash; streamed at boot | |
| **Console** | **Super** | dedicated UART (3-pin TTL header) — bring-up + setup output | |
| **POST display** | **Super** | drives the 2-digit hex display from forwarded 0x80 codes | |

The Bus MCU runs the hard-real-time bus interface on **core0 + PIO** (PIO latches the
multiplexed address on ALE and drives the fast read/write responses, PicoGUS-style); **core1**
is now free for the DMA/PIC engine instead of USB. The Supervisor owns the USB host stack and
filesystem with no bus-timing constraints to respect.

**DMA is no longer vestigial.** Sound Blaster / GUS digital audio is DMA-driven: PicoGUS
asserts DRQ and expects a real 8237 to run the memory→I/O transfer cycles. So the **Bus MCU's**
8237 must actually become bus master on DRQ, drive the transfer via the §5.1 counter, and
handle terminal count. It reuses the boot bus-master engine.

### 5.1 Bus-master addressing — external loadable counter (saves ~16 GPIO)

Driving a full 20-bit address from GPIO during master cycles would cost **20 pins**, which
the budget can't spare. But every master cycle — DMA blocks and BIOS/option-ROM shadow-load
alike — walks **sequential** addresses, so the address is offloaded to an external
**loadable 20-bit binary counter** (cascaded 74HC163, ~5 of them). The counter's own
flip-flops *hold* the address and its own outputs *drive* A0–A19; the MCU only:

1. **Loads the start address once per block** — multiplexed over the **existing D0–D7** plus
   a couple of load strobes (no new wide bus), and
2. **Pulses one COUNT pin per byte** to advance.

Pin cost drops from **~20 → ~4** (load strobes + count clock, reusing the data bus). Two
payoffs fall out of this:

- **Shadow-load:** load counter ← image base; per byte the MCU drives D0–D7 + MEMW̄ and
  pulses COUNT. It never drives an address line.
- **DMA (mem→I/O):** the MCU drives **neither address nor data** — the counter supplies
  A0–A19, SRAM puts the byte on D0–D7 under MEMR̄, and PicoGUS takes it on IOW̄+DACK (it keys
  on DACK, not address). The MCU only sequences the strobes and pulses COUNT — exactly the
  classic 8237 + page-latch behaviour.

*(A decoder is the wrong tool here — it is stateless one-hot translation, used for
chip-select in §4.1, and can neither hold nor sequence a 20-bit value. A plain 74HC573 latch
bank loaded over D0–D7 would also cut pins to ~3 but forces a full 3-byte reload every byte;
the counter keeps the pin saving **and** makes the sequential case fast via single-tick
increment. Latch bank = the slower fallback.)*

### 5.2 Bus MCU GPIO budget (the binding constraint)

Every signal, with the §5.1 counter and the '165 IRQ collector assumed. USB, console, POST
display, and image storage are **off on the Supervisor**, so they cost the Bus MCU nothing
beyond the 2-wire link (§5.3).

| Group | Signals | Pins | Notes |
|---|---|---|---|
| I/O address decode | A0–A9 | 10 | 10-bit ISA decode. A8/A9 **required** to separate 0x3E8 (COM3 mouse) from 0x2E8 (COM4); drop to A0–A7 + an external COM3-region gate to save ~1. |
| Data bus | D0–D7 | 8 | also carries the INTA vector + counter-load bytes |
| Command strobes | IOR̄/IOW̄ (bidir), MEMR̄/MEMW̄ (out) | 4 | sense as slave, drive as master |
| Bus control | ALE (in), AEN (bidir), RESET DRV (out) | 3 | |
| Ready / check | IOCHRDY (bidir), IOCHCK̄ (in) | 2 | |
| Bus grant | HOLD (out), HLDA (in) | 2 | V20 min-mode handshake |
| Interrupt deliver | INTR (out), INTĀ (in), NMI (out) | 3 | vector goes out on D0–D7 |
| IRQ inputs | 74HC165: LOAD, CLK, SER | 3 | collects ~10–12 IRQ lines; µs-poll is fine (ISA holds IRQ until serviced) |
| DMA handshake | DRQ1 (in), DACK1̄ (out), TC (out) | 3 | on-board PicoGUS channel; sidecar DMA via '165/'595 or deferred |
| Counter control | COUNT + load-steer ×3 | 3–4 | drives the external 20-bit address counter |
| Speaker | PWM → op-amp | 1 | |
| Transceiver DIR | master/slave | 0–1 | can be HLDA-derived externally |
| **Link to Supervisor** | **UART TX/RX** | **2** | §5.3 |
| **Total** | | **≈ 44–46 / 48** | fits with margin **because** the link is UART (2 pins). SPI (+3) would push to ~47–49 — at/over the edge. **As built: 48/48** — the margin was spent on a direct bus-CLK sense, ~{REFRESH}, and READY; the raw ~WR and IO/M̄ senses and DMA ch2/3 (DRQ/DACK) were dropped (DACK2/3 parked deasserted by pull-ups; first candidates for a '165/'595 expansion). |

Speed-select moves to the Supervisor (a static latch it sets before reset release), and the
POST display is Supervisor-driven — both off the Bus MCU. The link choice is worth ~3 pins
and is effectively the difference between comfortable and over-budget (§5.3).

### 5.3 Cross-MCU link — 2-wire full-duplex UART

The Bus MCU and Supervisor are joined by a **UART** (TX/RX), software-framed (length-prefix +
CRC). Traffic:

| Flow | When | Volume |
|---|---|---|
| BIOS + option-ROM images (Super → Bus) | boot, once | ~128 KB |
| Keystroke / mouse events (Super → Bus) | runtime | a few bytes each |
| Menu-draw commands (Super → Bus) | pre-BIOS | < 4 KB/screen |
| POST codes (Bus → Super) | boot | 1 byte each |
| CMOS-write requests (Super → Bus) | setup exit | a few bytes — only the Bus MCU can reach 0x70/71 |

**Why UART over SPI/I²C:**
- **Pins.** 2 vs SPI's ~5 (4 + an attention line). On the pin-critical Bus MCU that swing is
  what keeps §5.2 under 48.
- **Traffic shape.** Runtime is *asynchronous, bidirectional, low-rate* events. UART's
  separate TX/RX lets either side transmit the instant it has data — no master/slave, no
  attention line, no polling. A keystroke goes USB → Supervisor → UART → KBC with nothing in
  the path adding latency.
- **Bulk is irrelevant.** The 128 KB image push is one-time with the V20 in reset; ~0.1–0.4 s
  at multi-Mbaud (PIO UART if needed) is invisible, and nothing else is on the link then. The
  one thing SPI wins (throughput) is the one thing that doesn't matter here.
- **I²C is strictly dominated** — same 2 pins as UART but seconds-long bulk transfer,
  half-duplex, ACK overhead, and the touchiest electricals.

---

## 6. Boot sequence

1. **Power-on** → the TL7705A/MAX809 supervisor IC holds reset until rails are stable → both
   MCUs boot; the **Bus MCU holds the V20 in reset**.
2. Bus MCU, as **bus master**, **clears all of SRAM to a known value** (both chips, full
   0x00000–0xFFFFF span). This guarantees the option-ROM scan windows (0xC0000–0xEFFFF) hold
   no stray `0x55AA` signatures that would send the BIOS into garbage init, and gives a clean
   slate before any shadow-load.
3. **Supervisor** brings up the **USB host** and reads the keyboard.
4. Supervisor streams **menu-draw commands** over the link; the Bus MCU, as **bus master**,
   sets the video card to 80×25 text and writes them to **0xB8000**. The Supervisor echoes the
   same menu to its **console UART**.
5. **Hotkey within a timeout** → the **Supervisor** runs setup (CPU speed default, keyboard
   XT/AT, mouse serial/PS-2, IDE/boot options…); settings persist to **Supervisor flash**. For
   DOS-relevant bits it sends **CMOS-write requests** to the Bus MCU, which writes the
   **DS12C887** (only the Bus MCU can reach 0x70/71).
6. On exit/timeout → the Supervisor **streams the BIOS + option-ROM images** (video BIOS
   @0xC0000, XTIDE @0xC8000) over the link; the Bus MCU **shadow-loads** them into SRAM, then
   **releases V20 reset**.
7. V20 fetches the reset vector from RAM → **Xi 8088 BIOS** runs normally. At runtime the
   Supervisor forwards USB HID events over the link to the Bus MCU's KBC/mouse emulation.

The Bus MCU's master engine thus serves **three** duties: boot shadow-load, sound DMA, and
pre-BIOS menu rendering — all fed by the Supervisor over the §5.3 link.

---

## 7. Memory subsystem

- **2× AS6C4008-55** (512 K×8 each). SRAM #1 = `0x00000–0x7FFFF`; SRAM #2 = `0x80000–
  0x9FFFF` conventional top + optional **UMB**. Max conventional RAM = **640 KB**.
- **No flash IC** — the SST39SF010 is not used; BIOS lives in SRAM, written at boot by the
  **Bus MCU** from images the **Supervisor** holds in its QSPI flash (update via the
  Supervisor's USB/storage, not in-circuit reflash).
- **Power-on clear:** SRAM contents are undefined at power-up, so the **Bus MCU** **zeroes
  the entire SRAM span** before shadow-loading (§6 step 2). This prevents random bytes in the
  option-ROM scan windows (0xC0000–0xEFFFF) from falsely matching the `0x55AA` ROM signature.
- **Video RAM is *not* in system SRAM** — it lives inside the video MCU (see §8), so the
  `0xA0000–0xBFFFF` window is owned by the video card, and there is **no shared-framebuffer
  arbitration, no CPLD, no CGA snow.**

### Memory map

```
0xFFFFF ┌───────────────────────────┐
        │ System BIOS (64K, shadow) │ SRAM, MCU-loaded; reset vector @0xFFFF0
0xF0000 ├───────────────────────────┤
        │ reserved / optional UMB   │ SRAM #2
0xD0000 ├───────────────────────────┤
        │ XTIDE Univ. BIOS (32K)    │ SRAM, MCU-loaded option ROM @0xC8000
0xC8000 ├───────────────────────────┤
        │ Video BIOS (32K)          │ SRAM, MCU-loaded option ROM @0xC0000
0xC0000 ├───────────────────────────┤
        │ Video window A000–BFFF    │ owned by the VIDEO MCU (not system SRAM)
0xA0000 ├───────────────────────────┤
        │ Conventional 80000–9FFFF  │ SRAM #2 (128K)
0x80000 ├───────────────────────────┤
        │ Conventional 00000–7FFFF  │ SRAM #1 (512K)
0x00000 └───────────────────────────┘
```

---

## 8. Video card (RP2350B) — snoop-and-mirror

A soft **CGA + MDA + Hercules** card that **owns its video memory** and renders it to a
modern display, fully decoupled from the CPU.

- **Self-decodes its window** (0xA0000–0xBFFFF and the CRTC/mode ports) from the bus's own
  latched A17–A19 and `MEMR̄/MEMW̄/IOR̄/IOW̄` — it uses **no signal that isn't on the ISA bus**,
  which is what keeps it liftable to a standalone ISA card unchanged. (The motherboard's Y5
  block-strobe, §4.1, is for the SRAM #2 decode only; the video card never sees it.)
- **Snoop & accept writes** to `0xB0000–0xB7FFF` (MDA/Herc), `0xB8000–0xBBFFF` (CGA), and
  the CRTC/mode/color register ports (`3B4/3B5/3B8/3BA/3BF`, `3D4/3D5/3D8/3D9/3DA`) into
  its **own** internal video RAM + register state. **Writes are the hot path** (mode 13h
  game blits are almost all writes): the card latches address+data into its PIO FIFO and lets
  the cycle complete at **0 wait**, only pulling IOCHRDY if the FIFO backs up. This is the
  performance lever that matters, and it needs nothing but the standard bus.
- **Serve reads** of that region back onto the bus, wait-stated via **IOCHRDY** as needed —
  the card answers as the memory's owner. A wait-stated VRAM read is **period-authentic** (a
  real ISA video card serves its own reads the same way), and IOCHRDY is a standard ISA
  signal, so this stays fully portable. Reads are comparatively rare in the hot path.
- **Rejected alternative — shadowing the framebuffer into the (otherwise stranded) SRAM #2
  to serve fast local reads:** this would couple the video subsystem to motherboard memory
  and **break ISA-card portability**. Coordinating "who drives the read" needs either a
  private non-ISA signal or two devices both decoding 0xA0000–0xBFFFF — and 8-bit ISA has
  no arbitration for overlapping memory. It also can't return correct **planar** reads
  (stored bytes ≠ CPU bytes; reads have latch/color-compare side effects), so only the MCU
  can be the read source anyway. The window stays **wholly owned by the video subsystem**.
- **Status register coherence (0x3DA / 0x3BA):** games and demos poll the CGA/MDA status
  register's **display-enable (bit 0)** and **vertical-retrace (bit 3)** bits for tear-free
  updates and frame timing. Because the video MCU generates its own output timing decoupled
  from the CPU, it must report a 0x3DA/0x3BA value that **tracks its actual scan position** —
  i.e., the emulated retrace/display-enable must be coherent with the frame it is really
  displaying, not free-running. Reads are answered through the same IOCHRDY-wait path.
- **Render** the mirror continuously to output:
  - **VGA** — PIO + resistor-ladder DAC (e.g. 3R-3G-2B) + HSYNC/VSYNC, ~8 GPIO.
  - **HDMI/DVI** — the RP2350 **HSTX** block serializing TMDS out of GPIO with series
    resistors (no transmitter chip), ~8 GPIO.
  - The framebuffer is rendered **once in RAM**; **config selects the active output**
    (jumper / setup menu / HDMI hot-plug). Simultaneous dual-live output is a stretch goal.

**Pin pressure** (wide memory-window decode + two output stages) is why the video node is
the **48-GPIO RP2350B**.

### Scope (staged firmware — the board never changes)
- **v1:** CGA / MDA / Hercules (text + their native graphics). Solid, low risk.
- **Early add:** **VGA mode 13h** (320×200×256, linear) — easy, unlocks many games.
- **Later:** **EGA / VGA planar 16-color** (modes 10h/12h: 4 planes, latches, write modes,
  bit/map mask) — the hard part; every `A0000` write is a read-modify-write through plane
  logic within the bus cycle. RP2350 has the memory (520 KB SRAM + optional QSPI **PSRAM**
  for the 256 KB VGA aperture) and clock to attempt it; may need extra wait states.

The hardware is specified **VGA-capable** from the start; scope is a firmware milestone.

---

## 9. Audio — on-board PicoGUS (RP2040)

Treated as a **drop-in copy of the upstream open-hardware PicoGUS 2.0** (RP2040 + its own
level shifters + **PCM5102A I²S** audio output + joystick), wired to the local ISA bus and
running **stock, unmodified firmware** so upstream updates keep working. PicoGUS provides
(one personality at a time, re-selectable): **AdLib/OPL2, Sound Blaster, Gravis UltraSound,
MPU-401, CMS/Game Blaster, Tandy/PCjr**, plus the **analog joystick/gameport** (and MIDI on
the gameport).

- **Why RP2040, not RP2350B:** stock PicoGUS emulation firmware is RP2040-only; RP2350
  support in the project is limited to a developer analyzer tool. Forcing RP2350B would mean
  porting/maintaining PicoGUS ourselves — discarding the reason to use a real PicoGUS. So
  the board carries **two part numbers** (2× RP2350B + 2× RP2040); PicoGUS is the stock RP2040
  and the Supervisor is the other.
- **Requires functional DMA** in the Bus MCU (§5) — SB/GUS digital audio is DMA-driven.
- **Mixing:** PicoGUS line-out is summed with the **PC-speaker** signal in a simple op-amp
  summer → **line-out jack** (optionally an LM386 + small speaker).

---

## 10. Storage — XT-IDE + CompactFlash

Discrete and period-correct (uses 74HCT on hand):
- **XT-IDE rev 2 / "Chuck-mod"** 8-bit interface: a **74HCT573/652 high-byte latch** makes
  the 16-bit IDE data register two 8-bit transfers. **I/O base 0x300** (jumperable).
- **40-pin IDE header + CompactFlash** (True-IDE). 8-bit-capable CF can skip the latch; keep
  it for general IDE drives.
- Boot ROM = **XTIDE Universal BIOS**, shadow-loaded @0xC8000. Poll or IRQ5.
- *(Alternative not taken: an SD-card-backed virtual IDE on a small MCU. Discrete XT-IDE+CF
  is simpler and rock-solid.)*

---

## 11. Serial / parallel / RTC / input

### 11.1 Serial (2× COM)
- **2× 16C550**: **COM1 0x3F8/IRQ4**, **COM2 0x2F8/IRQ3**.
- **MAX3241** per port — 3 drivers + 5 receivers = a **full DB9** (TXD/RTS/DTR out;
  RXD/CTS/DSR/DCD/RI in), internal charge pump (single-supply, no ±12 V).
- **TTL console header** jumpered onto COM1 (ahead of the MAX3241) for headless bring-up.
- (TL16C554 quad rejected: ~6× the cost for 4× ports; add COM3/4 on the sidecar later — note
  **COM3 0x3E8 is reserved for the emulated serial mouse**, §11.4.) The 60-pin sidecar header
  carries only the standard 8-bit ISA IRQ lines (IRQ2–7, + IRQ8 on a reclaimed pin), so a
  sidecar COM4 cannot use IRQ10+: **COM4 (0x2E8) uses the bus IRQ2 line, delivered as IRQ9**
  (the standard AT IRQ2→9 redirect) rather than legacy-sharing IRQ3 with COM2 — still
  avoiding the ISA edge-triggered IRQ-sharing problem. The virtual COM3 mouse keeps
  **IRQ4** (the convention mouse drivers expect), so it *does* share IRQ4 with COM1; in
  practice you use one or the other (most mouse use implies COM1 is free).

### 11.2 Parallel (LPT)
Discrete **74HC** (374 data latch + 244/240 status/control) @ **0x378**, IRQ7 (usually polled).

### 11.3 RTC
**DS12C887** (integral battery + crystal) @ **0x70/0x71**. Holds CMOS config; pairs with
Xi 8088's CMOS setup.

### 11.4 Input — USB HID, mouse emulation
- **Single USB-A host jack** on the **Supervisor** MCU. Keyboard plugs straight in; a mouse
  needs the user's own hub (most XT software is keyboard-only).
- HID is a neutral middle layer: the **Supervisor** decodes USB HID and sends events over the
  §5.3 link; the **Bus MCU** presents them at the bus as **XT (8255/set 1) or AT (8042/set 2)**
  keystrokes per config, and the mouse as either a **virtual COM3 serial mouse** (default —
  works on any BIOS/DOS, no physical port or wasted UART) or a **PS/2 mouse on IRQ12** (for AT
  setups). Splitting HID decode (Supervisor) from bus presentation (Bus MCU) is the whole point
  of the two-MCU design.

---

## 12. Bring-up aids
- **2-digit hex POST display** — the **Bus MCU** snoops **port 0x80** and forwards each code
  over the §5.3 link; the **Supervisor** drives the display. *(Confirmed on-board.)*
- **Supervisor console UART** (3-pin TTL) — setup menu + bring-up logging; the single most
  useful debug tool here. Bring-up bonus: the Supervisor + console + USB come up and are fully
  testable **before** the Bus MCU's bus engine is working.
- **Logic-analyzer header** on the demuxed bus.
- Cold-start **reset/power supervisor**.

---

## 13. Power
- Single **5 V input** (USB-C) → on-board **3.3 V buck** for the four MCUs and USB.
- **No ±12 V** (MAX3241 charge pumps; PicoGUS audio is 3.3/5 V). 5 V must also source USB
  VBUS for the keyboard/hub, so the input has to supply the whole board *plus* a downstream
  USB device — the tight current loop to size for.
- **USB-C power negotiation:** the board only needs **5 V**, and at 5 V a Type-C sink can
  draw up to **3 A (15 W)** with *no PD silicon at all* — just the mandatory **5.1 kΩ Rd
  pulldowns on CC1/CC2**, which lets the board draw whatever current a Type-C source
  advertises via its Rp (up to 3 A). That is the cheap baseline. **Optionally** add a tiny
  fixed-function PD sink controller (**CH224K** or **HUSB238**, ~$0.50, a few resistors, no
  firmware) to *guarantee* a 5 V/3 A contract from PD-only supplies that won't hand out 3 A
  on Rp alone. Higher PD voltages are unnecessary since nothing on board wants >5 V.
- DS12C887 carries its own battery — no coin cell.

---

## 14. I/O map, IRQ, DMA

### I/O map
| Range | Device |
|---|---|
| 0x000–0x00F | 8237 DMA (Bus MCU, **functional**) |
| 0x020–0x021 / 0x0A0–0x0A1 | 8259 PIC master / slave (Bus MCU) |
| 0x040–0x043 | 8254 PIT (Bus MCU) |
| 0x060–0x064 | keyboard controller (Bus MCU; 8255 or 8042 mode); **0x061 bit 4 = refresh toggle** |
| 0x070–0x071 | DS12C887 RTC; **0x070 bit 7 = NMI mask** (AT-style) |
| 0x080–0x083 | DMA page regs; **0x080 POST latch** (snooped → hex display) |
| 0x201 | game/joystick port (PicoGUS) |
| 0x220.../0x240.../0x330/0x388 | PicoGUS (SB / GUS / MPU / OPL) |
| 0x2F8 / 0x3F8 | COM2 / COM1 (16C550) |
| 0x3E8 | **COM3 — emulated serial mouse** (Bus MCU, IRQ4) |
| 0x2E8 | COM4 (sidecar, **bus IRQ2 line → IRQ9**) |
| 0x300–0x31F | XT-IDE |
| 0x378 | LPT1 |
| 0x3B0–0x3BF / 0x3D0–0x3DF | MDA-Hercules / CGA (video MCU) |

### IRQ (AT-style, 15 lines via cascaded soft-PIC)
| IRQ | Use | | IRQ | Use |
|---|---|---|---|---|
| 0 | Timer | | 8 | RTC |
| 1 | Keyboard (USB-HID) | | 9 | IRQ2 redirect (sidecar COM4 etc.) |
| 2 | cascade → slave | | 10 | spare (no line on 8-bit header) |
| 3 | COM2 | | 11 | spare (no line on 8-bit header) |
| 4 | COM1 (+ COM3 mouse, shared) | | 12 | PS/2 mouse (if used) |
| 5 | XT-IDE / sound | | 13 | (FPU — unused) |
| 6 | Floppy (opt) / spare | | 14 | spare (no line on 8-bit header) |
| 7 | LPT1 | | 15 | spare (no line on 8-bit header) |

### DMA
| Ch | Use | | Ch | Use |
|---|---|---|---|---|
| 0 | (refresh — unused, SRAM) | | 2 | Floppy (opt) |
| 1 | **PicoGUS (SB/GUS)** | | 3 | sidecar / spare |

---

## 15. BOM — period part vs. this build

| Function | Period part | This build |
|---|---|---|
| CPU | 8088 | **NEC V20 (µPD70108, 9 MHz grade, on hand)** — min mode; ≥8 MHz part required for the 7.16 MHz default |
| Clock gen | 8284A + 14.318 xtal | **14.318 osc + 74HC74 (÷2) + 74HC4017 (÷3) + 74HC157 sel** |
| Bus controller | 8288 | **(none — min mode)** |
| Math | 8087 | **(none — software FP)** |
| Address latch / xceiver | 8282 / 8286 | 74HCT573 ×3 / 74HCT245 |
| Decoder | 74LS138 | 74HC138 + 74HC00 (SRAM /CE) |
| PIC / PIT / KBC / DMA | 8259 / 8253 / 8042 / 8237 | **Bus MCU: RP2350B (soft-emulated)** |
| Chipset Supervisor | (part of the chipset) | **RP2040** — USB host, setup UI, config + BIOS-image flash, console, POST |
| Bus-master address | (8237 internal + 74LS612 page) | **5× 74HC163** loadable counter (Bus MCU drives load/count) |
| IRQ collector | (8259 internal) | **74HC165** shift register (~12 IRQ → 3 pins) |
| Chipset link | — | **2-wire UART** (Bus MCU ↔ Supervisor) |
| RAM | 9× 4164 + parity | **2× AS6C4008-55 SRAM** |
| ROM / BIOS | mask ROM / 2764 | **none — shadow-loaded into SRAM by the Bus MCU (image from Supervisor flash)** |
| Video | MC6845 + discrete + RGBI | **RP2350B (soft CGA/MDA/Herc) → VGA + HDMI** |
| FM / digital audio | AdLib / Sound Blaster | **on-board PicoGUS (RP2040, stock fw)** |
| Game port | discrete 558 | **PicoGUS joystick** |
| UART | 8250 | **2× 16C550** |
| RS-232 | 1488/1489 | **MAX3241 (full DB9)** |
| LPT | discrete TTL | 74HC374 + 244 |
| RTC | MC146818 | **DS12C887** |
| Storage | ST-506 + WD ctrl | **XT-IDE + CompactFlash** |
| Keyboard | 8048 + 8255 + 74LS322 | **USB-HID host on the Supervisor MCU** |

**Out-of-production ICs eliminated vs. the period build:** 8284, 8288, 8087, 8259, 8253,
8237, 8255/8042, MC6845, YM3812/YM3014, and the BIOS ROM. **Remaining vintage part: the V20.**

---

## 16. Open decisions / next steps
- **Bus MCU GPIO pinout** — assignment is now drawn at 48/48 (see §5.2 "as built"); still to
  confirm: the partial-address-decode (A0–A7 sense only) and single-DMA-channel assumptions,
  and the core0-PIO (bus) / core1 (DMA+PIC) split under load.
- **Cross-MCU UART protocol** — define the framing (length + CRC) and message set (image push,
  HID event, menu draw, POST code, CMOS-write); pick the baud (hardware UART vs PIO multi-Mbaud)
  and confirm worst-case keystroke latency through USB → Supervisor → UART → KBC.
- **Bus-master timing** — detail HOLD/HLDA acquisition, the §5.1 counter load/count loop, the
  functional-8237 transfer cycle, and pre-BIOS video writes.
- **Video bus timing** — confirm **0-wait write** capture (PIO FIFO depth vs. sustained
  write bandwidth) is the design point; size the **IOCHRDY** budget for wait-stated reads
  (CGA/MDA now, planar VGA later). No SRAM shadow — the window stays ISA-portable (§8).
- **Xi 8088 fork** — slave-PIC init + IRQ2→9 redirect (15 IRQ); AT-style NMI mask at 0x70
  bit 7; confirm BIOS/timing code that polls the **0x61 bit 4 refresh toggle** is satisfied
  by the synthesized toggle; shadow-RAM execution; virtual-COM3 mouse; video/XTIDE
  option-ROM integration; confirm 8042 vs 8255 keyboard expectations.
- **PicoGUS integration** — copy the reference schematic faithfully; wire DRQ/DACK to the
  Bus MCU; route audio mixing.
- **Level-shifter selection** — per-card SN74LVC245A channel counts; the Bus MCU is the
  heaviest (bidirectional address/control groups with role-driven DIR for master vs. slave).
- **Setup menu** — define the stored settings (CPU speed, kbd mode, mouse mode, boot order)
  and the **Supervisor-flash** format.
- **Power budget** — 5 V rail sizing incl. USB VBUS; 3.3 V buck current for 4 MCUs. Decide
  whether 5.1 kΩ CC pulldowns alone suffice or a CH224K/HUSB238 PD sink is warranted to
  guarantee 5 V/3 A.
```

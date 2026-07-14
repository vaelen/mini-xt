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

**2026-07-14 update — 3.3V single-board redesign.** The board collapsed onto
**one PCB with a 3.3V internal bus** (was: multiple 5V-bus boards/sidecar
modules). The V20's own address-latch/data-transceiver stage, re-specified as
74LVC parts, *is* now the board's single 5V↔3.3V boundary; a second,
isolation-only buffer bank sits at the external expansion port. Sections below
are updated in place where the redesign changed them (RAM, RTC, COM UART,
voltage architecture, block diagram, §4). Full rationale, decision log, and
verification: `docs/superpowers/specs/2026-07-14-3v3-single-board-design.md`
and `hardware/notes/3v3-verification.md`.

---

## 1. Design summary / decisions locked

| Area | Decision |
|---|---|
| CPU | NEC **V20** (µPD70108, **9 MHz grade**) in **min mode** (no 8087 → no 8288, no 8284) |
| Clock | **Single 14.31818 MHz oscillator** (3.3V part); ÷2 = 7.16 MHz (74LVC74A), ÷3 = 4.77 MHz (74LVC161 preset-to-3) — LVC-grade for 3.3V fmax margin |
| CPU speed | **7.16 MHz** default, **4.77 MHz** turbo-down (selected in the boot menu, CPU held in reset) |
| Reset / power-good | Supervisor (TCM809, 3.3V) cold-start; **Bus MCU sequences reset** |
| Board | **One PCB** (>100×100 mm JLC tier) — the old per-subsystem boards / inter-board 60-pin daisy-chain headers are gone; sheets remain separate *schematic* sheets only |
| RAM | **One IS62WV51216BLL-55TLI** (512K×16, 3.3V, TSOP-II-44) wired **1M×8 via the byte-lane trick** (1 MB conventional+UMB less the video window); video RAM lives in the video MCU |
| ROM / BIOS | **None on board** — BIOS **shadow-loaded into SRAM** by the Bus MCU at boot |
| Bus | **3.3V internal** buffered 8-bit XT/ISA backplane; a **60-pin (2×30) buffered expansion port** (isolation/level-shift bank, `sidecar` sheet) presents a standard 5V-compatible 8-bit ISA header for real cards |
| Support chipset | **Two-MCU split**: **Bus MCU (RP2350B)** soft-emulates PIC (×2, 15 IRQ), PIT, KBC, **functional DMA**, NMI, POST, and RTC ports 0x70/71, as bus master/slave, GPIOs tied **directly** to the 3.3V bus (no local transceivers); **Supervisor (RP2040)** runs USB/config/storage off-bus plus the battery-backed RTC (§5) |
| Chipset link | **2-wire full-duplex UART** between Bus MCU ↔ Supervisor (boot image push + HID/menu/POST/RTC-sync events) |
| Video | **RP2350B** soft CGA/MDA/Hercules (snoop-and-mirror), **VGA + HDMI** out (config-selected); 4× 74LVC245A kept as a PIO-driven time-share address/data mux (GPIO budget), not level shifters on this 3.3V board |
| Audio | **On-board PicoGUS (bare RP2040 "chip-down" copy, stock firmware)** — AdLib/SB/GUS/MPU/etc.; no gameport (USB HID instead) |
| Network | **On-board RTL8019AS NE2000 NIC** @ 0x340, IRQ2→9 — a deliberate **5V island**: its 8-bit data bus (SD0-7) sits behind a gated 74LVC245 + 74HC138 decode, AEN/INT0 via 74LVC125A |
| Input | **USB-A HID host** on the **Supervisor** MCU (keyboard; mouse via user's hub) |
| Mouse | Emulated **virtual COM3 serial mouse** (default) or **PS/2 on IRQ12** (option) |
| Storage | Discrete **XT-IDE** (8-bit, Chuck-mod) + CompactFlash; XTIDE Universal BIOS. Floppy = **all-firmware emulation** (§10.1, no FDC hardware) |
| Serial | **2× TL16C550CPFBR** (TQFP-48, soldered, 3.3V — thin JLC stock, C882798) + **MAX3241** (full DB9); TTL console header on COM1 |
| Parallel | Discrete **74HC/74LVC** LPT @ 0x378 (jumpers: 0x278 alt, enable; IRQ7 hardwired) |
| RTC | **Emulated in the Bus MCU** (ports 0x70/0x71, like PIC/PIT); battery-backed timekeeping via a **PCF8563 I2C RTC + CR2032 coin cell on the Supervisor**, synced over the UART link at boot |
| Config | **Pre-BIOS setup menu** (Supervisor MCU), shown on **video + MCU console**, entered by keypress |
| BIOS | **Xi 8088** (Sergey Kiselev), expected to be **forked** for our chipset |
| Debug | **2-digit hex POST display** (port 0x80), MCU console, logic-analyzer header |
| Power | Single **5 V in** (USB-C) → on-board **3.3 V buck** carrying nearly the whole board; no ±12 V. 5V presences that remain: V20; cpu_core U10 (74HCT32 strobe combiner); cpu_core U13 (74HCT04 — V20 CLK + READY/HOLD buffers); the RTL8019AS NIC island; the fused +5V_ISA port feed; the audio MCP6002 (analog). MAX3241s are 3.3V |

**MCU count: 2× RP2350B** (Bus MCU, video) **+ 2× RP2040** (Supervisor, PicoGUS).
The chipset is deliberately split across two MCUs (§5) for clean separation: the **Bus MCU**
owns all hard-real-time bus work, the **Supervisor** owns the USB stack, setup UI, and
BIOS-image storage off-bus. The two *we* develop on RP2350B (Bus MCU) and RP2040 (Supervisor)
are independent; PicoGUS stays stock.

---

## 2. Philosophy & architecture

The organizing idea: **the buffered 8-bit XT/ISA bus is the integration contract.**
The V20 plus minimal glue creates a real XT bus on the board; every function then
hangs off it either as a **real chip** (what we already have) or as an **MCU "soft card"**
that talks the bus exactly as a period ISA card would. This makes each subsystem
independently developable, testable, and (for the video and sound cards) **liftable
onto a standalone ISA card later.**

**2026-07-14 update:** the whole internal bus is now 3.3V, so soft cards on the
motherboard tie their MCU GPIOs to it **directly** — no local level shifters —
except where a chip is a genuine 5V island (the on-board RTL8019AS NIC) or the
video card's GPIO-budget mux (below). Local shifters remain load-bearing only at
the buffered expansion port (§4.3) and on any card that plugs into it as a real
5V ISA card.

Three classes of node:

1. **The "motherboard" — a two-MCU chipset** (the one special, non-card node). It turns the
   V20 into an XT and is split by timing domain (§5):
   - **Bus MCU (RP2350B) — "fast hands."** All hard-real-time bus work: PIC, PIT, KBC, DMA,
     NMI, POST, RTC ports 0x70/71, the shadow-load engine. A bus *slave* (answers I/O)
     **and** a bus *master* (boot shadow-load, sound DMA, pre-BIOS menu rendering). No
     local transceivers — its GPIOs sit on the 3.3V bus directly and tri-state natively
     for role changes. Touches only the bus, its glue (address counter, IRQ shift
     register), and the link to the Supervisor.
   - **Supervisor (RP2040) — "slow brain."** Off the system bus entirely: USB HID host, setup
     UI, persistent config, BIOS/option-ROM image storage, console, POST display, and the
     battery-backed PCF8563 RTC (synced to the Bus MCU's emulation over the link at boot).
     Talks to the Bus MCU only over a **2-wire full-duplex UART** (§5.3).
2. **Soft cards** — the **video** card (RP2350B) and **PicoGUS** (RP2040). Pure ISA
   peripherals on the bus, GPIOs tied directly to the 3.3V bus (video keeps a 4×
   74LVC245A PIO-driven time-share mux for GPIO budget, not for level shifting).
3. **Real period-style chips** — V20, one IS62WV51216BLL SRAM, 2× TL16C550CPFBR UART,
   RTL8019AS NIC (a 5V island, isolated behind its own buffer/decode), plus discrete
   74HC/74HCT/74LVC glue for the bus, LPT, and XT-IDE.

**Portability guideline** (downgraded 2026-07-14 from a hard schematic rule — decision
#8 of the 3.3V redesign). A **soft card** (class 2) is still meant to use **only
signals that exist on the ISA bus** — self-decoding its own address ranges, coordinating
solely through standard lines (`MEMR̄/MEMW̄/IOR̄/IOW̄`, `BALE`, `AEN`, `IOCHRDY`, `IRQ`,
`DRQ/DACK/TC`, `CLK`, `RESET`), no dependence on host memory — because that is what keeps
it liftable to a standalone ISA board. But with the whole board now one 3.3V bus, this is
firmware/architectural discipline rather than an electrically-enforced boundary, so it is
a **guideline**, not a binding constraint (`mxbus`'s `PRIV_*` split loosened accordingly).
The **class-1 motherboard MCUs remain explicitly exempt** — they *are* the motherboard: the
Bus MCU bus-masters via `HOLD/HLDA`, sequences reset, and owns motherboard-only signals
(the SRAM-decode Y5 strobe, the speed-select latch, the external address counter), and the
Supervisor never sits on the bus at all. Class-3 parts are fixed motherboard hardware and
out of scope for the rule.

**Central I/O decode + IRQ map (2026-07-14).** The discrete peripherals no longer carry
their own bus-interface plumbing. One **`addr_decode` sheet** (74HC138 windowing on A6-A8
with A9/AEN enables, a 74HC00 building the shared A3·A4·A5 fine term, two 74HC32 ranks)
hands **~COM1_CS / ~COM2_CS / ~LPT_CS / ~IDE_CS** (`mxbus.PRIV_CS`) to the COM/LPT/XT-IDE
sheets, and its shared **74LVC125A** drives the real IRQ lines (COM1→IRQ4, COM2→IRQ3,
LPT→IRQ7, IDE→IRQ14) from the peripherals' private requests (`mxbus.PRIV_IRQREQ`; the COM
channels stay ~OUT2-gated per the PC convention). Base addresses are **hardwired** (LPT 0x378, IDE
0x300 — the straps went the way of COM's, 2026-07-14 later the same day). All six
per-peripheral **disable jumpers JP1–JP6** (COM1, COM2, LPT, IDE, NIC, VID — enabled by
default; fit a jumper to disable) live here: COM/LPT/IDE gate their chip selects through
a second '32 rank, while **DIS_NIC / DIS_VID** (`mxbus.PRIV_DIS`) are just the jumper
levels routed to gating that must stay local (the NIC's isolation '125 inside its 5V
island; the video MCU's firmware boot strap, polarity inverted vs the old VID_EN). These private nets are
shared logic factored out, not an isolation break: each is functionally equivalent to
the gate chips it replaced, and a block broken out to a standalone card gets decode + IRQ
driver back in its wrapper schematic exactly as it gets the bus edge connector
(`questions-addr_decode.md`). The NIC's *decode* is not centralized — the RTL8019AS
self-decodes and its '138/'125 isolation gates stay in the 5V island — and
video/PicoGUS/Bus-MCU decode in firmware; only their disable jumpers moved here.

### Block diagram

```
        14.31818 MHz osc ──┬─ ÷2 (74LVC74A) → 7.16 MHz ─┐         (3.3V clock tree;
                           │                            ├─ 74HC157 sel ─ 5V buf ─► V20 CLK
                           ├─ ÷3 (74LVC161) → 4.77 MHz ─┘   ▲ (MCU speed GPIO, boot only)
                           └──────────────────────────────────────────────► ISA OSC pin (B30)
                                                     (74HCT04 = the ONLY other 5V package)

   ┌─────────┐  RD/WR/IO-M, ALE, HOLD/HLDA
   │   V20   │  (min mode, 5V — the board's one vintage/5V chip)
   │ 8088-cmp│
   └─────┬───┘
   AD bus│ multiplexed
   ┌─────┴────────────┐  <- the board's ONE 5V<->3.3V boundary
   │ 74LVC573A×3 latch│ → A0–A19 ┐
   │ 74LVC245A xceiver│ ↔ D0–D7  │   buffered 3.3V internal XT/ISA bus
   └──────────────────┘          │   (+ MEMR/W, IOR/W, ALE, AEN, CLK, OSC, RESET,
         ┌───────────────────────┴────IOCHRDY, IOCHCK, IRQ, DRQ/DACK, +3V3, GND)
         │
  ┌──────┼────────┬────────────────┬────────────────┬───────────┬───────────────┬──────┐
      ┌──┴──┐ ┌───┴──────────┐ ┌───┴──────────┐ ┌───┴────┐ ┌────┴────────┐ ┌────┴──────┐
      │SRAM │ │   BUS MCU    │ │  VIDEO MCU   │ │PicoGUS │ │ 2×TL16C550  │ │port bank  │
      │1M×8 │ │   RP2350B    │ │   RP2350B    │ │RP2040  │ │CPT+MAX3241  │ │ (~9 LVC   │
      │IS62 │ │ GPIOs DIRECT │ │ 4x LVC245A   │ │ stock  │ │  COM1/2     │ │245/244/   │
      │WV.. │ │ on 3.3V bus  │ │ PIO mux      │ │ AdLib/ │ └─────────────┘ │2G07 pkgs) │
      └─────┘ │ (no local    │ │  (GPIO       │ │SB/GUS  │ ┌───────────┐   │ isolates  │
         ▲    │ xceivers)    │ │  budget, NOT │ │chip-dwn│ │  XT-IDE   │   │ 5V ISA    │
         │    └───┬───────┬──┘ │  level-shift)│ └───┬────┘ │  + CF     │   │ header    │
   74HC138        │       │ ▲  └──────────────┘     │I2S   └───────────┘   │ (60p 2x30)│
   +NAND          │ glue: │ │UART link            PCM5102A ┌──────────┐    └───────────┘
   (SRAM /CE)     │5×'163 │ │(2-wire,             audio    │ disc. LPT│  ┌───────────┐
                  │counter│ │full-duplex)     PC-spkr ─┐   │ @0x378   │  │RTL8019AS  │
                  │ '165  │ │  RTC sync   op-amp ──────┴─► └──────────┘  │ NIC: 5V   │
                  │IRQ-in │ ▼              summer → line-out             │ island,   │
                  │   ┌───┴────────────┐                                 │ gated     │
                  │   │  SUPERVISOR    │  USB-A host (kbd/mouse hub)     │ LVC245/   │
                  │   │    RP2040      │  setup UI · config (flash)      │ HC138     │
                  │   │  off the bus   │  BIOS/opt-ROM images (flash)    └───────────┘
                  │   │  PCF8563 RTC   │  console UART · POST display
                  │   │  + CR2032      │  (Bus MCU emulates ports 0x70/71,
                  │   └────────────────┘   synced from here over the link)
   2-digit hex POST @0x80 (Supervisor-driven) · one 5V→3.3V buck carries nearly the whole board
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
One **14.31818 MHz** canned oscillator does everything. **2026-07-14 update:** the
whole tree now runs at 3.3V (canned 14.318 MHz oscillators are only stocked as
3.3V parts at JLC) — plan-stage verification (`hardware/notes/3v3-verification.md`
check 7) found plain HC-grade dividers fail their fmax margin at 3.3V (74HC74's
guaranteed fmax interpolates to ~14.8 MHz, 74HC161 to ~11.1 MHz — both too close
to or below the 14.318 MHz clock), so both dividers are **LVC-grade**:

- **÷2 (74LVC74A)** → **7.15909 MHz**, clean 50 % duty → default CPU/bus clock.
  (Spec'd 250 MHz — no margin question at 3.3V.)
- **÷3 (74LVC161 preset-to-3, same topology as a '163)** → **4.77273 MHz**, ~33 %
  duty (after the inverting 5V buffer stage below) → turbo-down. A single
  flip-flop can't ÷3; the preset-reload counter does it in one chip, and the
  33 % duty is within the V20's clock spec (it is exactly what the 8284 supplied
  the original 8088). Spec'd 150 MHz at 3.3V — comfortable margin, but JLC stock
  is thin (re-verify before ordering).
- A **74HC157** (one section, now 3.3V-powered) selects 7.16 vs 4.77; **its
  select line is a chipset-MCU GPIO**, driven directly (3.3V clears HC's Vih at
  3.3V, so the old 5V inverting-select stage is gone).
- **Speed is changed only in the MCU pre-BIOS boot menu**, while the V20 is held in reset —
  never live during execution. Because the mux select only ever moves while the CPU is in
  reset, the runt clock pulse a plain 74HC157 would produce on switching is harmless (no
  glitch-free PLD needed); the new divisor is settled before reset is released.
- The raw 14.318 also drives the **ISA OSC pin (B30)** for any real card on the port bank —
  re-buffered to 3.3V by a 74LVC125A (no 5V push-pull output may drive a shared bus net that
  reaches a non-5V-tolerant GPIO).

**CLK level note:** the V20 clock input wants a near-Vcc swing (datasheet-confirmed
Vkh min = 0.8×Vdd = **4.0 V**, check 1), so the mux output is buffered by a
**5 V-powered 74HCT04 package (U13)** to meet it. The same U13 package also
re-buffers the V20's **READY/HOLD** inputs (Task-10: their Vih ≈ 0.6×Vdd = 3.0 V
is barely met by a 3.3 V MCU drive — HOLD via one *inverting* gate, so firmware
drives HOLD active-low). All U13 outputs drive *only* private V20 nets, never a
shared bus line. (U13 and U10's 74HCT32 strobe combiner are this design's two
surviving 5 V logic packages.) This is also why the MCU cannot drive the CPU
clock directly (its 3.3 V pins won't meet Vkh). **RESET, by contrast, does NOT
need the 5V buffer** — the V20's
general-input Vih (2.2V) is well within reach of 3.3V logic (check 1), so RESET and
RESET_DRV are driven straight from 3.3V.

Because the **PIT is emulated in the Bus MCU**, the all-important **1.193182 MHz**
timer rate is synthesized internally and is *independent* of the CPU clock — none of the
old colorburst divider math is needed. The video MCU likewise makes its own pixel clocks.

### 3.3 Reset
A cold-start supervisor (**TCM809, now 3.3V-powered**) holds the board in reset until rails
are stable. Thereafter the **Bus MCU sequences the V20's reset**: it holds the V20 in reset
through its own boot, the pre-BIOS menu, and the BIOS shadow-load, then releases it.

---

## 4. The bus and the buffered expansion port

**2026-07-14 update:** the internal backplane is now **3.3V end to end**. The V20's own
address-latch/data-transceiver stage — re-specified as 74LVC parts — *is* the board's
single 5V↔3.3V boundary (§4.2); no other on-board node needs a level shifter. A second,
separate isolation/buffer bank sits only at the external **buffered expansion port**
(§4.3, `sidecar` sheet) to keep it 5V-real-card-compatible.

### 4.1 Buffered 3.3V internal XT/ISA backplane
- **74LVC573A ×3** latch A0–A19 (gated by raw ALE, `cpu_core` U2–U4); **74LVC245A** buffers
  D0–D7 (`cpu_core` U5). Both are 3.3V-powered with 5V-tolerant inputs, so they read the V20's
  5V AD bus directly and drive a clean 3.3V bus on the other side.
- **SRAM chip-select decode — a single 74HC138 + one 74HC00 package, no PLD.** With one SRAM
  chip (below) the old two-chip NAND-select scheme collapses: `cpu_core` U6 (74HC138, 3.3V
  input/output — every input is now 3.3V-driven, so plain HC, not HCT, is fine) still decodes
  the 128 KB blocks from latched **A17→A, A18→B, A19→C**, but only its **Y5** output
  (0xA0000–0xBFFFF = the video MCU window) is used; the SRAM's own `/CE` is simply
  **NOT(Y5)** — one inverter (a spare gate in `cpu_core` U7, a 74HC00) — so the SRAM answers
  the *entire* 1 MB address space except the video window. **Y5 is motherboard-internal**
  (it only feeds the SRAM `/CE` inverter). The video subsystem still **self-decodes** its
  0xA0000–0xBFFFF window from latched A17–A19, using no signal off the ISA bus, so it stays
  liftable to a standalone ISA board unchanged (§8).
  - SRAM `/OE = MEMR̄, /WE = MEMW̄` (direct — the read path's whole critical delay budget,
    verified against the -55 SRAM's 25 ns tDOE at 7.16 MHz with wide margin,
    `hardware/notes/3v3-verification.md` check 2).
  No I/O-cycle qualification is needed: during I/O cycles MEMR̄/MEMW̄ are inactive, so the
  SRAM data pins stay high-Z even with `/CE` asserted (no contention, no spurious write). The
  decode reads *latched* address, so it is identical under V20 or bus-master (MCU) ownership.
  (Total memory decode: **one 74HC138 + one inverter gate.**)
- In min mode the V20's `IO/M̄ + RD̄ + WR̄` are gated into `MEMR̄/MEMW̄/IOR̄/IOW̄` by a
  **74HCT32** (`cpu_core` U10) — this gate package stays on the 5V rail (it reads the raw 5V
  V20 strobes directly) but its outputs cross to the 3.3V bus only through a tri-state
  74LVC125A stage (U11, `~OE = HLDA`) — see §4.2.
- **Wait states:** each soft card pulls **IOCHRDY** to buy time on a read; the Bus MCU folds
  all IOCHRDY/ready signals back to the V20's READY input. The SRAM runs 0 wait at 7.16 MHz.

### 4.2 Level shifting — the boundary is now at the V20, not per-card
The old "every MCU is 3.3V on a 5V bus, so every soft card carries its own level shifters"
picture is gone. With the whole internal bus at 3.3V, **the only 5V↔3.3V boundary on the
board is the V20's own demux stage** (`cpu_core`):

- **Address:** 3× 74LVC573A latches (5V-tolerant D inputs from the V20's muxed AD bus,
  3.3V Q outputs onto A0–A19).
- **Data:** 1× 74LVC245A transceiver (5V-tolerant CPU-side, 3.3V bus-side), `DIR = DT/R̄`.
- **Strobes:** the 74HCT32 gates that combine `RD̄/WR̄ + IO/M̄` into `MEMR̄/MEMW̄/IOR̄/IOW̄`
  stay on +5V (they read the raw 5V V20 strobes), but reach the 3.3V bus only through a
  74LVC125A tri-state stage (`~OE = HLDA`, enabled only while the V20 owns the bus) — a 5V
  push-pull output must never drive a shared bus net that reaches a non-5V-tolerant GPIO
  (e.g. the port bank's RP2350B-adjacent side, or the expansion-port far side pre-buffer).
  Pull-ups park the gated strobes inactive across the ownership handoff gap.
- **BALE / CLK / OSC re-buffer (`cpu_core` U15, 74LVC125A):** these three bus copies were
  historically driven straight off 5V logic (raw ALE, the CLK/OSC buffer below); they are
  now re-buffered to a clean 3.3V swing before joining the shared bus, for the same
  5V-push-pull-can't-drive-a-3.3V-only-net reason.
- **CLK only** still needs a 5V driver: the V20's CLK input requires Vkh ≥ 0.8×Vdd = 4.0V
  (datasheet-verified, unreachable from 3.3V) — the board's **one remaining 5V logic
  package**, a 74HCT04 (`cpu_core` U13), whose *only* output is the private V20 CLK net (it
  never touches a shared bus line). RESET does **not** need this treatment (Vih = 2.2V,
  reachable from 3.3V directly).

Everywhere else on the board, an MCU's GPIOs (or a 3.3V-native chip's pins) sit on the bus
**directly** — no local transceiver:
- **Bus MCU:** its six former 74LVC245A transceivers and role-driven DIR logic are deleted;
  its RP2350B GPIOs tie 1:1 to the bus and tri-state natively for master/slave role changes
  (a firmware property now, not a hardware DIR pin). It keeps its external 20-bit address
  counter (§5.1) and its own 3× 74HC244 tri-state buffers (`cpu_core`-adjacent, `bus_mcu`
  U14–U16) so the counter's outputs don't fight the CPU-side '573 latches on A0–A19 during
  V20-owned cycles — those are tri-state control for the shared address bus, not level
  shifters, and they stay.
- **Video MCU:** keeps 4× 74LVC245A, but repurposed — the RP2350B doesn't have enough spare
  GPIO to dedicate one pin per bus signal, so these chips are a **PIO-driven time-share
  address/data mux**, not a voltage boundary (deleting them was never on the table; only the
  sheet's *pure* buffer packages were removed).
- **PicoGUS:** stays a stock RP2040 design; its former 3-package level-shift stage (address/
  data mux excepted — that one is functional, not a shifter, see `questions-picogus.md`) is
  gone now that the bus it sits on is already 3.3V.
- **RTL8019AS NIC — the one deliberate exception.** The NIC chip itself is a genuine **5V
  island**: its 8-bit data bus (SD0–7) is isolated from the 3.3V bus behind a **gated
  74LVC245 + 74HC138 decode** (`network` U4/U5), and `AEN`/`INT0` cross through a 74LVC125A.
  Its MAC EEPROM is on the same 5V island. This is the one place outside the V20 boundary
  and the expansion port where a real level-shift/isolation stage still exists, because the
  chip itself is unavoidably 5V.

### 4.3 The buffered expansion port (`sidecar` sheet)
The only other 5V↔3.3V crossing on the board is a dedicated **isolation/buffer bank**
between the 3.3V internal bus and a **60-pin (2×30) 2.54 mm external ISA header**, laid out
as the **standard 8-bit ISA edge pinout** (the PicoGUS `Bus_ISA_8bit` arrangement) so it —
and any dev card built to it (`hardware/cards/`) — is pin-compatible with real 8-bit ISA
cards. It would exist even on an all-3.3V board (isolation against load/fault/contention
from a plugged card); LVC parts make it 5V-card-compatible for free.

The bank is **~9 packages**, all 74LVC-class, 3.3V-powered with 5V-tolerant inputs:

| Group | Parts | Direction |
|-------------------------------------|-----------|-------------------------------------|
| A0–A19 + BALE/AEN/CLK/OSC (24 lines) | 3× 74LVC245A | out, DIR strapped permanently outbound |
| Command strobes (10 lines: MEMR̄/MEMW̄/IOR̄/IOW̄/RESET_DRV/TC/DACK1-3̄/REFRESH̄) | 2× 74LVC244A | out |
| D0–D7 | 1× 74LVC245A | bidir, `DIR = EXP_DDIR` (Bus MCU-owned, defaults outbound via a pull-up) |
| IRQ2–7 + DRQ1–3 (inbound, onto private `EXT_*` nets — see below) | 2× 74LVC244A | in |
| IOCHRDY / IOCHCK̄ (open-drain, wired-AND) | 1× dual 74LVC2G07 | bidir (open-drain) |

Header signals:
- A0–A19, D0–D7; MEMR̄/MEMW̄/IOR̄/IOW̄, BALE, AEN; CLK (7.16), OSC (14.318), RESET DRV
- IOCHRDY; the unused analog rails are reclaimed: pin 7 (−5 V) → **IOCHCK̄**,
  pin 11 (−12 V) and pin 15 (+12 V) → extra **GND** returns (IRQ8 was pulled off this header
  entirely — see below — so pin 15 is no longer IRQ8)
- IRQ2–7, REFRESH̄ on its standard pin (driven by the Bus MCU's internal refresh timer)
- DRQ1–3 / DACK1–3̄ / TC (serviced by the Bus MCU's emulated 8237 for a real DMA card)
- +5 V and grounds: the port feeds `+5V_ISA` through a **2 A polyfuse + SMBJ5.0A clamp**, so
  a faulted expansion trips its own fuse instead of dropping — or back-driving — the board
  rail.

**IRQ2–7/DRQ1–3 land on private `EXT_IRQ*`/`EXT_DRQ*` nets, not the internal IRQ/DRQ nets** —
the buffer bank's inbound 74LVC244A pair drives dedicated `EXT_*` signals so a floating or
misbehaving external line can never contend with an internal driver. The Bus MCU's IRQ
collector and DMA engine **merge** the `EXT_*` lines with their on-board sources in firmware
(same collector shift-register hardware, extra input taps) — there is no separate hardware
arbitration; a card and an on-board peripheral must still not be jumpered to the same line
simultaneously. (IRQ8 was removed from the header on 2026-07-12, before this redesign — the
RTC's interrupt is now firmware-internal to the Bus MCU's PIC emulation, so there is nothing
for a header IRQ8 line to carry; `EXT_IRQ8` exists Bus-MCU-side for symmetry but has no
physical header pin and idles low.)

**Bus-master limitation, unchanged in spirit:** the port's outbound buffers have a
**fixed, firmware-chosen direction** (`EXP_DDIR` for data; the address/control banks are
permanently outbound). There is no request/grant arbitration to the port, so **an external
card that wants to drive the bus itself (be a bus master) is not supported** — the same
limitation the old sidecar design had, now stated explicitly against the new buffer bank.

Only two soft cards earn a **separate PCB** (`hardware/cards/`): **video** and the
**isatest jig** (a Pico playing the bus *host* — the opposite role — so any card can be
exercised with no motherboard present). Both are now genuine **5V ISA cards** that plug into
this port and keep their own local level shifters, same as any real period card would.
**COM ×2, LPT, and storage are motherboard-only** (§10/§11): each is still a soft-card
sheet (COM1+COM2 share one merged sheet since 2026-07-14), and its enable jumpers (plus
base-address straps on LPT/IDE) free the slot for an expansion-port replacement. (The RTC no longer has an on-board ISA sheet at all — it moved off-bus, §11.3.)

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
| IRQ inputs | 74HCT165: LOAD, CLK, SER | 3 | collects the 8 live IRQs (D0–D6 = IRQ2–8, D7 = IRQ14 for on-board XT-IDE; IRQ9–13/15 have no possible source — second cascaded '165 if one ever appears); µs-poll is fine (ISA holds IRQ until serviced) |
| DMA handshake | DRQ1 (in), DACK1̄ (out), TC (out) | 3 | on-board PicoGUS channel; sidecar DMA via '165/'595 or deferred |
| Counter control | COUNT + load-steer ×3 | 3–4 | drives the external 20-bit address counter |
| Speaker | PWM → op-amp (GPIO22) | 1 | PIT ch2 direct output; bus-CLK sense dropped (PIO tracks via BALE/strobes) |
| Transceiver DIR | master/slave | 0–1 | can be HLDA-derived externally |
| **Link to Supervisor** | **UART TX/RX** | **2** | §5.3 |
| **Total** | | **≈ 44–46 / 48** | fits with margin **because** the link is UART (2 pins). SPI (+3) would push to ~47–49 — at/over the edge. **As built: 48/48** — the margin was spent on SPKR (PIT ch2), ~{REFRESH}, and READY; the raw ~WR and IO/M̄ senses and DMA ch2/3 (DRQ/DACK) were dropped (DACK2/3 parked deasserted by pull-ups; first candidates for a '165/'595 expansion). |

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
   DOS-relevant bits it sends **CMOS-write requests** to the Bus MCU, which writes its
   **emulated CMOS bytes** (only the Bus MCU answers 0x70/71; the values persist in
   Supervisor flash, §11.3).
6. On exit/timeout → the Supervisor **streams the BIOS + option-ROM images** (video BIOS
   @0xC0000, XTIDE @0xC8000) over the link; the Bus MCU **shadow-loads** them into SRAM, then
   **releases V20 reset**.
7. V20 fetches the reset vector from RAM → **Xi 8088 BIOS** runs normally. At runtime the
   Supervisor forwards USB HID events over the link to the Bus MCU's KBC/mouse emulation.

The Bus MCU's master engine thus serves **three** duties: boot shadow-load, sound DMA, and
pre-BIOS menu rendering — all fed by the Supervisor over the §5.3 link.

---

## 7. Memory subsystem

- **One IS62WV51216BLL-55TLI** (512K×16, 2.5–3.6V, 55 ns, TSOP-II-44), wired **1M×8 via the
  byte-lane trick** (2026-07-14 update — replaces the old 2× AS6C4008 pair + 2× DIP-32
  sockets): system `A1–A19` address the chip's 19-bit word space; `A0` selects the byte lane
  (`A0 → /LB` direct, `A0 → inverter → /UB`); **both `IO0-7` and `IO8-15` tie to the same
  D0–D7**, and the `/LB`/`/UB` pair guarantees exactly one lane ever drives (verified against
  the ISSI truth table, `hardware/notes/3v3-verification.md` check 2). `/CE` = NOT(latched
  Y5) (§4.1) — the chip answers the **entire 1 MB** space except the 0xA0000–0xBFFFF video
  window. Max conventional RAM (less the video window) = **1 MB**, still bounded by the
  address decode the same way as before; the two "conventional/UMB" regions below are no
  longer separate physical chips, just address ranges within the one SRAM.
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
        │ reserved / optional UMB   │ one SRAM chip, same /CE = NOT(Y5) block
0xD0000 ├───────────────────────────┤
        │ XTIDE Univ. BIOS (32K)    │ SRAM, MCU-loaded option ROM @0xC8000
0xC8000 ├───────────────────────────┤
        │ Video BIOS (32K)          │ SRAM, MCU-loaded option ROM @0xC0000
0xC0000 ├───────────────────────────┤
        │ Video window A000–BFFF    │ owned by the VIDEO MCU (not system SRAM; Y5 block)
0xA0000 ├───────────────────────────┤
        │ Conventional 80000–9FFFF  │ one SRAM chip (128K of its range)
0x80000 ├───────────────────────────┤
        │ Conventional 00000–7FFFF  │ one SRAM chip (512K of its range)
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
- **Boot straps** (firmware-read GPIOs — decode lives in firmware, so there is no
  hardware chip-select to gate): **DIS_VID** (from **addr_decode JP6**, 2026-07-14 —
  replaced the on-sheet VID_EN jumper, polarity inverted) high = card disabled — firmware
  keeps every bus-facing OE off, and all its drivers are MCU-gated tri-states, so a
  disabled card is electrically silent; **JP1 (VID_BASE)** picks the default window set,
  closed = CGA
  (0x3D4–3DF / 0xB8000), open = MDA/Hercules (0x3B4–3BF / 0xB0000) — the snoop-design
  equivalent of a period card's MDA/CGA switch, and how an on-board video coexists with a
  `card_video` on the sidecar chain.
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

## 9. Audio & Network — on-board PicoGUS + RTL8019AS NIC

A **faithful copy of the upstream PicoGUS 2.0 "chip-down" design** (CERN-OHL-P;
`picogus/hw-chipdown/` sources): a **bare RP2040** + W25Q128 flash + 12 MHz crystal (the
same three parts as the Supervisor — one assembly line item each), the signature
**ADS-muxed shared AD0–AD7** bus interface through SN74CB3T FET switches, the BUSOE
power-up latch, AEN·DACK IOR̄/IOW̄ masking, open-drain IOCHRDY, **APS6404L-3SQR** sample
PSRAM, and a **PCM5102A I²S DAC** — running **stock, unmodified firmware** (GPIO29
grounded is the stock board-detect strap). Personalities (one at a time): **AdLib/OPL2,
Sound Blaster, Gravis UltraSound, MPU-401, CMS/Game Blaster, Tandy/PCjr**.

- **Why RP2040, not RP2350B:** stock PicoGUS emulation firmware is RP2040-only. The board
  still carries two part numbers (2× RP2350B + 2× RP2040) — but both RP2040s are now the
  same bare-chip design, sharing flash/crystal parts.
- **Requires functional DMA** in the Bus MCU (§5) — SB/GUS digital audio is DMA-driven.
  **DMA must be jumpered to channel 1** (the only MCU-serviced channel); the reference
  jumper block is trimmed to the DMA pairs, and the **IRQ is hardwired to IRQ5** (the
  free line, sole driver — pgusinit sets the firmware to match).
- **Deviations from the reference card** (logged in `notes/questions-picogus.md`): no USB-A
  joystick port (the Supervisor owns HID, so **no gameport** — 0x201 unused); **no
  wavetable header and no MIDI-out jack** (build simplification — and with the wavetable
  gone, the reference's M62429 volume chip and passive mix node go too; stock firmware
  still drives the volume/MIDI GPIOs, which are documented no-connects); **no local audio
  jack** — the RC-filtered DAC output leaves the sheet as PG_L/PG_R into the op-amp summer
  with the PC speaker → the board's one line-out jack; **no local programming USB** — the
  Supervisor's shared programming port reaches this RP2040 via the SW2 selector (§12), a
  documented soft-card isolation exception. All removed blocks remain in the reference
  sources if ever wanted back.

### 9.1 Network — RTL8019AS NE2000 NIC

A **NE2000-compatible NIC** built around the **RTL8019AS** (the same ISA8019 lineage as
the original Realtek NE2000 clone cards) — **10BaseT only** (twisted-pair, link test
enabled via PL=00; no AUI/BNC). **I/O 0x340–0x35F, hardwired** (no base-address strap);
**IRQ2**, delivered as **IRQ9** via the soft PIC's standard AT redirect (the same '165
collector line and redirect path the rest of the 8-bit IRQs use).

- **No boot ROM.** Like XT-IDE, a NIC boot ROM would need Bus MCU shadow-loading — but
  nothing on this board needs PXE/RPL boot, so none is populated.
- **MAC address** lives in a **93C46 EEPROM**, shipped **blank**; program it once with
  Realtek's **RSET8019.EXE** (the same utility period NE2000 clones used).
- **Disable = addr_decode JP5** (2026-07-14: the on-sheet JP1 moved there, sense
  inverted — enabled by default, fit to disable): DIS_NIC high tri-states the IRQ2 line
  through the island's **74LVC125A** gate and forces the chip's **AEN input high**, so a
  disabled NIC ignores every I/O cycle and frees IRQ2 for the sidecar. The gate stays
  local (the RTL8019AS self-decodes; the disable must reach inside the 5V island) — only
  the jumper is central, same row as the other disables (addr_decode JP1–JP6).

---

## 10. Storage — XT-IDE + CompactFlash

Discrete and period-correct (uses 74HCT on hand):
- **XT-IDE rev 2 / "Chuck-mod"** 8-bit interface: a **74HCT573/652 high-byte latch** makes
  the 16-bit IDE data register two 8-bit transfers. **I/O base 0x300, hardwired** (the 0x320
  re-strap went with the other base straps, 2026-07-14 later; the block match arrives as
  ~IDE_CS from `addr_decode`); **addr_decode JP4** disables the port outright (forces
  ~IDE_CS inactive — every select, latch clock
  and buffer goes inert, the IRQ stays released), so an external XT-IDE on the sidecar
  chain can coexist or take over. **The IRQ is hardwired to IRQ14** (the AT primary-IDE
  convention, collected on the Bus MCU's '165 D7; a motherboard-internal line, not on
  the 60-pin header) — the soft PIC is AT-style anyway, so there's nothing to strap.
- **40-pin IDE header + CompactFlash** (True-IDE). 8-bit-capable CF can skip the latch; keep
  it for general IDE drives.
- Boot ROM = **XTIDE Universal BIOS**, shadow-loaded @0xC8000. Polled or interrupt-driven
  is purely an XTIDE UB per-controller config choice — the line is wired either way, and
  the tri-state driver is silent unless the drive asserts INTRQ.
- *(Alternative not taken: an SD-card-backed virtual IDE on a small MCU. Discrete XT-IDE+CF
  is simpler and rock-solid.)*

### 10.1 Floppy — all-firmware (no controller hardware)

**Decision: no physical FDC.** Floppy support is emulated entirely in the Bus MCU,
because every piece rides infrastructure the board already has — the marginal
hardware cost is exactly zero:

- **Registers:** the Bus MCU is already a full 8-bit ISA slave (it serves the
  emulated PIT/KBC/COM3 today); a virtual floppy just claims I/O ports and
  answers them in firmware.
- **IRQ6** is raised inside the soft PIC the same way virtual COM3 raises IRQ4 —
  a firmware event, no physical line. (The collector's IRQ6 input stays free
  for a sidecar card.)
- **"DMA":** the emulated 8237 lives in the same chip, and sector transfers into
  conventional memory use the existing bus-master machinery (HOLD/HLDA + the
  §5.1 counter chain) — the same path every other emulated DMA transfer takes.
- **Media:** disk images live in the Core2350B module's flash; selection/swap is
  a page in the Supervisor's pre-BIOS setup menu (§12), and images arrive over
  the existing USB/console paths.
- **BIOS:** the shadow-loaded BIOS fork hooks INT 13h for the floppy exactly as
  XTIDE UB hooks it for the disk.

Two firmware tiers, both zero-hardware — ship tier 1, add tier 2 only if real
software demands it:

1. **INT 13h hook** (ship this): BIOS floppy services call a private Bus MCU
   port; sectors appear. DOS and anything well-behaved works.
2. **Register-level µPD765 emulation @ 0x3F0–0x3F7** (only if needed): the 765
   command state machine as bus-visible registers, for software that bangs the
   controller directly (copy-protected boot loaders, imaging tools).

*(Path not taken: a real socketed WD37C65/FDC37C78 + 34-pin header. It would
also need DMA ch2, which the Bus MCU doesn't service — either non-DMA-mode
BIOS floppy code or the '165/'595 GPIO expansion (§5.2). Only worth the board
space if a physical drive or Gotek must plug in; nothing else requires it.)*

---

## 11. Serial / parallel / RTC / input

### 11.1 Serial (2× COM)
- **2× TL16C550CPFBR** (TQFP-48, soldered directly at 3.3V — 2026-07-14 update: replaces the
  socketed PLCC-44 16C550; the LQFP PT revisions are dead at JLC, the active PFB is
  **thin stock, C882798**, see `hardware/notes/jlcpcb-sourcing.md`) (ONE `com_port` sheet
  carrying both ports — merged 2026-07-14 from the instanced-×2 layout; both chip selects
  now arrive from the **central `addr_decode` sheet** (below), so the only shared glue left
  on the COM sheet is one 74LVC125A gating both IRQs): **COM1 0x3F8/IRQ4**,
  **COM2 0x2F8/IRQ3** — base addresses and IRQs are **hardwired** (the PC convention; no
  strap to misconfigure — the old J2 base strap existed only because one generic sheet was
  instanced at both addresses). On-board only — no standalone COM card — the per-port
  disable jumpers are **addr_decode JP1/JP2** (enabled by default; a fitted jumper forces
  the port's ~CS inactive so it never decodes, MCR stays 0, and the central IRQ driver
  stays tri-state — a disabled port is silent on every line, which is how you free its
  IRQ).
- **MAX3241** per port (3.3V — Task-10 moved it onto the 3.3V rail so its receiver
  outputs no longer swing 5V into U1's non-5V-tolerant inputs; caps resized to the
  datasheet 3.0–3.6V column) — 3 drivers + 5 receivers = a **full DB9**
  (TXD/RTS/DTR out; RXD/CTS/DSR/DCD/RI in), internal charge pump (single-supply, no ±12 V).
- **TTL console header** jumpered onto COM1 (ahead of the MAX3241) for headless bring-up.
- (TL16C554 quad rejected: ~6× the cost for 4× ports; add COM3/4 on the expansion port
  later — note **COM3 0x3E8 is reserved for the emulated serial mouse**, §11.4.) The 60-pin
  expansion-port header carries only the standard 8-bit ISA IRQ lines (IRQ2–7; IRQ8 has no
  header pin at all — the RTC that once justified it is now firmware-emulated off-bus,
  §11.3), so an expansion COM4 cannot use IRQ10+ — and the bus IRQ2 line is now hardwired to
  the on-board NE2000 NIC (§9.1): **an expansion COM4 (0x2E8) needs a freed line — disable
  COM2 (addr_decode JP2) for IRQ3, or the NIC (addr_decode JP5) to reclaim IRQ2→9** — still avoiding the ISA
  edge-triggered IRQ-sharing problem. The virtual COM3 mouse keeps
  **IRQ4** (the convention mouse drivers expect), so it *does* share IRQ4 with COM1; in
  practice you use one or the other (most mouse use implies COM1 is free).

### 11.2 Parallel (LPT)
Discrete **74HC/74LVC** ('574 data/control latches + '244/'245 status & read-back, now
3.3V-powered) — on-board only: base address **0x378, hardwired** (the 0x278
strap went with the other base straps, 2026-07-14 later; the block match arrives as
~LPT_CS from `addr_decode`); disable via **addr_decode JP3** (forces ~LPT_CS inactive: no
register can be read, written or latched — and frees the line). **IRQ7 is hardwired** (LPT1 convention). The IRQ driver
is tri-state (asserted only for an enabled ACK̄ pulse), so the line stays
shareable.

### 11.3 RTC
**2026-07-14 update — RTC moved off-bus entirely; the DS12C887 and its ISA glue are
deleted.** Ports **0x70/0x71 are emulated in the Bus MCU** (same as the PIC/PIT/KBC), so
there is no longer an on-board `rtc` ISA sheet at all. Battery-backed timekeeping lives on
the **Supervisor**: a **PCF8563 I2C RTC + CR2032 coin cell**, diode-ORed onto its own
`VDD_RTC` rail so the coin cell only carries the load while the board is powered off. At
boot the Supervisor reads the PCF8563 and sends the time to the Bus MCU over the existing
UART link, which then answers 0x70/0x71 reads from its in-firmware CMOS-byte emulation
(persisted in **Supervisor flash**, not battery-backed NVRAM). Holds CMOS config; pairs with
Xi 8088's CMOS setup the same as before — only the hardware backing it changed.

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
- **Module-USB flashing is safe**: the Core2350B has *no* on-module diode between its USB
  connector and its VBUS pin (vendor schematic), so each module site feeds VBUS through a
  **Schottky (SS34), Pico-style** — a PC plugged into the Bus-MCU or video module for
  firmware update powers only that module, never the +5 V rail, and a powered board never
  back-drives the PC port. The modules' level-shifter enables/directions carry park
  resistors, so an MCU in BOOTSEL (all GPIO Hi-Z) leaves every bus-facing buffer disabled.
- **One programming port for both bare RP2040s**: a USB-C device port (J6, Supervisor
  sheet) reaches either the Supervisor or the PicoGUS RP2040 via a **DPDT slide selector
  (SW2)**; each chip has its own **BOOTSEL button**. The port's **VBUS is deliberately
  unconnected** — the board must be powered to flash, which removes every back-power path
  by construction. Flashing the Supervisor: unplug the keyboard (the host jack shares the
  PHY). The PicoGUS's BUSOE latch keeps its bus switches off until firmware runs, so
  flashing it never disturbs the ISA bus.

---

## 13. Power
- Single **5 V input** (USB-C) → on-board **3.3 V buck** now carrying **nearly the whole
  board** (2026-07-14 update): all four MCUs, USB, the SRAM, both UARTs, and essentially
  every logic package except the V20, one 74HCT04 (V20 CLK buffer), and the expansion
  port's far side. Re-budgeted (`hardware/notes/3v3-verification.md` check 5): worst-case
  estimated load ≈486 mA, ~16% of the existing TPS563200's 3A rating — **no buck upsize
  needed**, even doubling every estimate lands at ~33% of budget.
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
- The RTC's **CR2032 coin cell** (on the Supervisor) is the board's only battery — the
  DS12C887's integral battery is gone along with the chip (§11.3).

---

## 14. I/O map, IRQ, DMA

### I/O map
| Range | Device |
|---|---|
| 0x000–0x00F | 8237 DMA (Bus MCU, **functional**) |
| 0x020–0x021 / 0x0A0–0x0A1 | 8259 PIC master / slave (Bus MCU) |
| 0x040–0x043 | 8254 PIT (Bus MCU) |
| 0x060–0x064 | keyboard controller (Bus MCU; 8255 or 8042 mode); **0x061 bit 4 = refresh toggle** |
| 0x070–0x071 | **RTC, emulated in the Bus MCU** (PCF8563-backed, synced from the Supervisor); **0x070 bit 7 = NMI mask** (AT-style) |
| 0x080–0x083 | DMA page regs; **0x080 POST latch** (snooped → hex display) |
| 0x201 | (unused — no gameport; HID via the Supervisor, §11.4) |
| 0x220.../0x240.../0x330/0x388 | PicoGUS (SB / GUS / MPU / OPL) |
| 0x2F8 / 0x3F8 | COM2 / COM1 (TL16C550CPFBR) |
| 0x3E8 | **COM3 — emulated serial mouse** (Bus MCU, IRQ4) |
| 0x3F0–0x3F7 | (reserved) **firmware floppy** tier-2 registers, §10.1 (Bus MCU) |
| 0x2E8 | COM4 (expansion port; needs a freed IRQ — see §11.1) |
| 0x300–0x31F | XT-IDE (base hardwired; addr_decode JP4 disables) |
| 0x340–0x35F | NE2000 NIC (RTL8019AS, §9.1; IRQ2→9; addr_decode JP5 disables) |
| 0x378 | LPT1 (base hardwired; addr_decode JP3 disables) |
| 0x3B0–0x3BF / 0x3D0–0x3DF | MDA-Hercules / CGA (video MCU) |

### IRQ (AT-style, 15 lines via cascaded soft-PIC)
| IRQ | Use | | IRQ | Use |
|---|---|---|---|---|
| 0 | Timer | | 8 | RTC — **firmware-internal only** (Bus MCU soft-PIC event; no expansion-port pin) |
| 1 | Keyboard (USB-HID) | | 9 | IRQ2 redirect (on-board NE2000 NIC) |
| 2 | cascade → slave | | 10 | spare (no line on 8-bit header) |
| 3 | COM2 | | 11 | spare (no line on 8-bit header) |
| 4 | COM1 (+ COM3 mouse, shared) | | 12 | PS/2 mouse (if used) |
| 5 | **PicoGUS (hardwired, sole driver)** | | 13 | (FPU — unused) |
| 6 | firmware floppy (virtual, §10.1) / expansion-port spare | | 14 | **XT-IDE (hardwired)** — internal line |
| 7 | LPT1 (hardwired) | | 15 | spare (no line on 8-bit header) |

### DMA
| Ch | Use | | Ch | Use |
|---|---|---|---|---|
| 0 | (refresh — unused, SRAM) | | 2 | (firmware floppy needs none, §10.1) |
| 1 | **PicoGUS (SB/GUS)** | | 3 | expansion port / spare |

---

## 15. BOM — period part vs. this build

> Concrete JLCPCB/LCSC part numbers for everything below live in
> `hardware/tools/parts.py` (applied to the schematics as `LCSC Part Num`
> properties); sourcing decisions and stock-forced substitutions are in
> `hardware/notes/jlcpcb-sourcing.md`. **2026-07-14 update:** the board's internal
> bus moved to 3.3V (below); the TL16C550CPFBR UART (C882798) is thin JLC stock — verify.

| Function | Period part | This build |
|---|---|---|
| CPU | 8088 | **NEC V20 (µPD70108, 9 MHz grade, on hand)** — min mode; ≥8 MHz part required for the 7.16 MHz default |
| Clock gen | 8284A + 14.318 xtal | **14.318 osc (3.3V) + 74LVC74A (÷2) + 74LVC161 (÷3) + 74HC157 sel** — LVC-grade for 3.3V fmax margin |
| Bus controller | 8288 | **(none — min mode)** |
| Math | 8087 | **(none — software FP)** |
| Address latch / xceiver | 8282 / 8286 | **74LVC573A ×3 / 74LVC245A** (3.3V, 5V-tolerant inputs) — the board's one 5V↔3.3V boundary |
| Decoder | 74LS138 | 74HC138 + 74HC00 inverter (single-SRAM `/CE = NOT(Y5)`) |
| PIC / PIT / KBC / DMA / RTC | 8259 / 8253 / 8042 / 8237 / MC146818 | **Bus MCU: RP2350B (soft-emulated)**, GPIOs direct on the 3.3V bus (no local transceivers) |
| Chipset Supervisor | (part of the chipset) | **RP2040** — USB host, setup UI, config + BIOS-image flash, console, POST, battery-backed RTC |
| Bus-master address | (8237 internal + 74LS612 page) | **5× 74HC161** loadable counter + 3× 74HC244 tri-state (Bus MCU drives load/count) |
| IRQ collector | (8259 internal) | **74HCT165** shift register (IRQ2–8, 14 → 3 pins) |
| Chipset link | — | **2-wire UART** (Bus MCU ↔ Supervisor) |
| RAM | 9× 4164 + parity | **1× IS62WV51216BLL-55TLI** (512K×16, 3.3V) wired 1M×8 via the byte-lane trick |
| ROM / BIOS | mask ROM / 2764 | **none — shadow-loaded into SRAM by the Bus MCU (image from Supervisor flash)** |
| Video | MC6845 + discrete + RGBI | **RP2350B (soft CGA/MDA/Herc) → VGA + HDMI**; 4× 74LVC245A PIO-mux (GPIO budget, not level-shift) |
| FM / digital audio | AdLib / Sound Blaster | **on-board PicoGUS (RP2040, stock fw)** |
| Network | (none, period) | **on-board RTL8019AS NE2000 NIC** — 5V island, isolated behind gated 74LVC245 + 74HC138 |
| Game port | discrete 558 | **(none — USB HID on the Supervisor)** |
| UART | 8250 | **2× TL16C550CPFBR** (TQFP-48, 3.3V, soldered — thin JLC stock, C882798) |
| RS-232 | 1488/1489 | **MAX3241 (full DB9, 3.3V)** |
| LPT | discrete TTL | 74HC/74LVC '574 + '244 (3.3V) |
| RTC | MC146818 | **Emulated in the Bus MCU** (ports 0x70/71) + **PCF8563 I2C RTC + CR2032** on the Supervisor for battery-backed time |
| Storage | ST-506 + WD ctrl | **XT-IDE + CompactFlash** |
| Keyboard | 8048 + 8255 + 74LS322 | **USB-HID host on the Supervisor MCU** |

**Out-of-production ICs eliminated vs. the period build:** 8284, 8288, 8087, 8259, 8253,
8237, 8255/8042, MC6845, YM3812/YM3014, MC146818/DS12C887, and the BIOS ROM.
**Remaining vintage part: the V20.**

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
- ~~**Level-shifter selection**~~ — **resolved by the 2026-07-14 3.3V redesign**: the
  boundary collapsed to the V20's own demux stage plus one buffer bank at the expansion
  port (§4.2/§4.3); the Bus MCU no longer carries any level shifters at all.
- **Setup menu** — define the stored settings (CPU speed, kbd mode, mouse mode, boot order)
  and the **Supervisor-flash** format.
- ~~**Power budget**~~ — **resolved by the 2026-07-14 3.3V redesign's verification pass**:
  worst-case estimate ≈486 mA against the existing 3A buck (~16%, 6× headroom); no upsize
  needed (`hardware/notes/3v3-verification.md` check 5). USB-C CC-pulldown-only vs.
  CH224K/HUSB238 PD sink remains a build-time choice, not a sizing risk.
```

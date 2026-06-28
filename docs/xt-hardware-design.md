# XT-Class SBC — Hardware Design Notes

A working design reference for a DOS-compatible, XT-class single-board computer built
from **distinct period-style ICs** (no "one microcontroller emulates everything").
Goal is **education**, not emulation. Modern parts are used where they simplify
sourcing/assembly without hiding how the machine actually works.

See companion docs: `early-pc-cpus.md` (the CPUs) and `memory-management.md`
(segmentation / banking / EMS / XMS / DOS extenders).

---

## 1. Design summary / decisions locked

| Area | Decision |
|---|---|
| CPU | NEC **V20** (8088 pin-compatible, faster; 8088 also fine), **max mode** |
| Clock | **Single 28.63636 MHz oscillator**, divided → 7.16 CPU/ISA, 14.318 OSC, 1.193 PIT, 28.636 video |
| CPU speed | **~7.16 MHz** (28.636 ÷ 4); 4.77 MHz turbo-switchable |
| Reset | **TL7705A power-good supervisor** + 74HC74 sync (8284A does NOT do power-good) |
| RAM | **2× AS6C4008-55** (512K×8 SRAM each → 1 MB raw, ~640 KB usable conventional) |
| ROM | **1× SST39SF010** (128K×8 flash, in-circuit reprogrammable) |
| Video | **CGA + MDA + Hercules** via real **MC6845**, shared SRAM, **VGA out via scan-doubler** |
| Storage | **On-board XT-IDE-compatible** interface → CompactFlash |
| Bus | **One 8-bit ISA slot** |
| Audio | **PC speaker + OPL2 (YM3812)** mixed to line-out |
| I/O | Multiple COM (16C550), **TTL serial console header**, parallel port, **joystick port**, RTC |
| Debug | **POST-code display** (port 0x80), config DIP switches |

---

## 2. Block diagram

```
   28.63636 MHz oscillator (8× NTSC colorburst — single master clock)
        │
   ┌────┴─────────────── 74HC393 / 161 divider ───────────────┐
   │ ÷4 = 7.15909 MHz     ÷2 = 14.31818 MHz     ÷12 of 14.318  │  28.636 →
   │  → CPU CLK, ISA CLK   → ISA OSC (B30)        = 1.193 MHz   │  video/VGA
   └───┬──────────────────────┬──────────────────────┬────────┘  dot clock
       │ CLK                   │ OSC                   │ → PIT
  ┌────┴────┐  status     ┌────┴───┐
  │  V20    │────────────►│ 8288   │ MEMR/MEMW/IOR/IOW/INTA
  │(max md) │  S0-S2      │ bus ctl│
  └────┬────┘             └────────┘      TL7705A ──► 74HC74 ──► RESET (synced)
 AD bus│ multiplexed                      (power-good + reset btn)
   ┌───┴────────────┐
   │ 573 latches +  │  →  A0-A19 (system address bus)
   │ 245 transceiver│  ↔  D0-D7  (system data bus)
   └───┬────────────┘
  ┌────┼──────────┬──────────┬──────────┬───────────┬──────────┐
┌─┴─┐┌─┴──┐    ┌──┴───┐  ┌────┴───┐ ┌────┴─────┐ ┌───┴──┐
│SR1││SR2 │    │FLASH │  │ Core   │ │ Video    │ │ ISA  │
│512││512 │    │128K  │  │ support│ │ MC6845 + │ │ slot │
│K  ││+vid│    │BIOS+ │  │82C59/  │ │ font ROM │ └──────┘
│   ││+UMB│    │VBIOS+│  │82C37/  │ │ + CPLD + │
└───┘└─┬──┘    │XTIDE │  │82C54/  │ │ scandblr │ I/O: XT-IDE/CF · 16C550 ·
   shared      └──────┘  │82C55   │ │ → VGA    │ LPT · RTC · KB · speaker ·
   video                 └────────┘ └──────────┘ OPL2 · joystick · POST LEDs
```

---

## 3. Clock, reset, and bus control

### 3.1 Single-oscillator clock tree (the key simplification)
A single **28.63636 MHz** canned oscillator (8× the 3.579545 MHz NTSC colorburst — a
stock, cheap part) is the only timing source. A 74HC393/74HC161 divider chain produces
everything:

```
28.63636 MHz ─┬─ ÷2 → 14.31818 MHz → ISA OSC (B30)  ─┬─ ÷12 → 1.193182 MHz → PIT
              │                                       │
              ├─ ÷4 → 7.15909 MHz → CPU CLK + ISA CLK (B20)
              │
              └─ ×1 → 28.636 MHz → VGA scan-doubler output dot clock
```

**Why not just one 14.318 crystal for everything?** The 8284A divides its input by 3
(no ÷2 option), so a 14.318 crystal yields the stock **4.77 MHz** CPU — not faster. And
you can't run the CPU *at* 14.318 (beyond the V20's rating). Starting from **28.636**
and dividing gives a clean **7.159 MHz** CPU **and** the required **14.318 OSC** from
one part — and conveniently the same 28.636 is the VGA output dot clock (§6).

**Consequence:** the CPU clock comes from the **divider**, fed straight to the V20
(CMOS, accepts a standard ~50% clock at 7.16 MHz — verify against the V20 CLK spec; if
you ever drop in a real NMOS 8088 you'd want the 8284A's 33%-duty clock instead, which
is another reason to stick with the V20). This **demotes the 8284A out of its clock
role**, so it's no longer needed — reset and READY synchronization move to discrete
74HC74 flip-flops (§3.3), which is cleaner and more instructive.

### 3.2 Turbo switch
Provide a **7.16 / 4.77 MHz switch** (mux the CPU-clock divider tap: ÷4 vs ÷6, or gate
in a 14.318-derived 4.77). Old games that time with CPU loops need slow mode. Expose a
status bit so software can read the current speed. **Keep PIT at 1.193 MHz and ISA OSC
at 14.318 in both modes.**

### 3.3 Reset / power-good (must add — the 8284A doesn't do this)
The 8284A only *synchronizes* an incoming reset; it does **not** detect power-good. So:
- **TL7705A** supervisor (or MAX809 / DS1813) asserts reset until Vcc is stable and
  debounces the **reset button**.
- A **74HC74** synchronizes that reset to the 7.16 MHz CLK before it reaches the CPU
  (the CPU needs RESET meeting setup time relative to CLK).

### 3.4 Bus interface and wait states
- **74AHCT573** latches demux A0–A19 (gated by ALE); **74AHCT245** buffers D0–D7
  (DIR = DT/R̄, OĒ = DEN̄).
- **8288** decodes status S0̄–S2̄ → MEMR̄/MEMW̄/IOR̄/IOW̄/INTĀ (max mode; also enables the
  optional 8087).
- **READY synchronizer:** a 74HC74 samples the async wait/IOCHRDY/peripheral-ready
  signals to CLK.
- **Wait states:** SRAM (55 ns) runs **0 wait states** at 7.16 MHz. Add **1–2 waits**
  for flash, peripheral chips, and the ISA slot via a small shift-register/counter.

---

## 4. Memory subsystem

### 4.1 Capacity reality
The XT map reserves the top 384 KB; **max conventional RAM is 640 KB**
(`0x00000–0x9FFFF`). Of the 1 MB of SRAM:
- **SRAM #1** → all of `0x00000–0x7FFFF` (conventional).
- **SRAM #2** → top 128 KB of conventional (`0x80000–0x9FFFF`), the **video
  framebuffer** windows, and an optional **UMB**. Remainder spare.

### 4.2 Memory map

```
0xFFFFF ┌───────────────────────────┐
        │ System BIOS (64K)         │ FLASH bank 0  → reset vector @ 0xFFFF0
0xF0000 ├───────────────────────────┤
        │ reserved                  │
0xE0000 ├───────────────────────────┤
        │ (optional UMB 64K)        │ SRAM #2  → LOADHIGH TSRs (XT UMB driver)
0xD0000 ├───────────────────────────┤
        │ XT-IDE BIOS (32K) @C800   │ FLASH bank 1 (hi)
0xC8000 ├───────────────────────────┤
        │ Video BIOS  (32K) @C000   │ FLASH bank 1 (lo)
0xC0000 ├───────────────────────────┤
        │ CGA framebuffer  @B8000   │ SRAM #2  ← shared, arbitrated
0xB8000 ├───────────────────────────┤
        │ MDA/Hercules fb  @B0000   │ SRAM #2  ← shared, arbitrated
0xB0000 ├───────────────────────────┤
        │ (graphics window A000)    │ optional, SRAM #2
0xA0000 ├───────────────────────────┤
        │ Conventional RAM 80000-9F │ SRAM #2 (128K)
0x80000 ├───────────────────────────┤
        │ Conventional RAM 00000-7F │ SRAM #1 (512K)
0x00000 └───────────────────────────┘
```

### 4.3 Decode (74HC138 on A17–A19 → eight 128 KB blocks)

| 138 out | Range | Device |
|---|---|---|
| Y0–Y3 | 0x00000–0x7FFFF | **SRAM #1** (use `~A19` directly) |
| Y4 | 0x80000–0x9FFFF | **SRAM #2** (conventional top) |
| Y5 | 0xA0000–0xBFFFF | **SRAM #2** (video windows) + 6845 video decode |
| Y6 | 0xC0000–0xDFFFF | **FLASH bank 1** (video BIOS + XT-IDE BIOS) |
| Y7 | 0xE0000–0xFFFFF | **FLASH bank 0** (BIOS) + optional UMB in E-seg |

```
SRAM1_CS̄ = ~A19                                  ; 0x00000–0x7FFFF
SRAM2_CS̄ = Y4 | (video window) | (E-seg UMB, opt.)
FLASH_CS̄ = (A19 & A18 & A17 & A16)               ; 0xF0000–0xFFFFF  (bank 0)
         | (A19 & A18 & ~A17)                     ; 0xC0000–0xDFFFF  (bank 1)
FLASH_A16 = 1 in 0xC0000–0xDFFFF, else 0          ; selects flash bank
```

- One 128 KB flash serves **BIOS (64K) + video BIOS (32K) + XT-IDE BIOS (32K)**.
- ROM/flash enables on **read only** → stray writes ignored. Route WĒ for in-system
  programming only; protect with the chip's **software data protection** and/or a
  **program-enable jumper**.
- **No parity** (SRAM) — ensure BIOS does not enable the parity-check NMI path.

### 4.4 Shared SRAM for video — bus arbitration
The MC6845 streams addresses continuously during active display; the framebuffer lives
in **SRAM #2**, so CPU and video contend for that chip. Resolution:

- **Video-priority interleave with CPU wait on collision.** Give the 6845 fetch its
  SRAM slot each character clock; if the CPU wants SRAM #2's video window in the same
  slot, drop CPU READY for that cycle. With 55 ns SRAM and a 140 ns CPU cycle there's
  ample bandwidth, and giving video priority **eliminates CGA "snow"** (unlike the real
  CGA, which let the CPU win and corrupt the display).
- Only the **video window** needs arbitration; `0x80000–0x9FFFF` is CPU-only.
- Implement the arbiter (address/CE mux + READY gating) in the video **CPLD** — it's a
  deliberately-designed peripheral, not a chip-emulator stand-in.

---

## 5. Core support chips (the "it's a PC" set)

Use **CMOS 82Cxx** variants for headroom at 7.16 MHz.

| Chip | Function | I/O ports | Notes |
|---|---|---|---|
| **82C59A** | Interrupt controller (PIC) | 0x20–0x21 | single PIC (XT) |
| **82C37A** | DMA controller | 0x00–0x0F | **largely vestigial** (see below) |
| **82C54** | Timer (PIT) | 0x40–0x43 | clock **1.193 MHz** from 14.318÷12 |
| **82C55A** | Peripheral interface (PPI) | 0x60–0x63 | keyboard, DIP switches, speaker gate |
| **74LS670** | DMA page registers | 0x80–0x83 | upper address bits per DMA channel |

**DMA is nearly idle:** SRAM needs no refresh (the original used DMA ch0 for that) and
XT-IDE is PIO. Include the 82C37 for software/BIOS compatibility (and any DMA-using ISA
card / optional floppy); clock it at **CLK÷2 (~3.58 MHz)** to stay within floppy DMA
timing. The **82C54 must stay at 1.193 MHz.**

### 5.1 Optional: second 82C59A for 15 IRQs
The expanded IRQ range is a **support-chip feature, not a CPU feature** — a second
cascaded 82C59A works fine on the 8-bit V20/8088 board (no 286 or 16-bit bus needed).
**But existing software won't use the extra lines automatically** (XT software is written
for 8 IRQs, and an XT BIOS only inits one PIC). The benefit is **having enough IRQ lines
to give each device its own**, avoiding sharing — most useful here for **COM3/COM4**,
which otherwise share IRQ4/IRQ3 with COM1/COM2.

To make configurable drivers' "high IRQ" options (sound/net/serial cards) actually work,
wire it **AT-compatible**:

| Item | Requirement |
|---|---|
| Slave ports | **0xA0/0xA1** |
| Slave vector base | **INT 70h–77h** (IRQ8–15) |
| Cascade | slave INT → **master IR2**; CAS0–2 between the two PICs |
| IRQ2 redirect | bus IRQ2 → **IRQ9**, with an **INT 71h → INT 0Ah** BIOS stub for compat |
| BIOS | must initialize the **slave** (ICW1–4, cascade mode, unmask) — add to the XT BIOS |

Caveats:
- Cascading **consumes IRQ2** (it becomes the cascade input) — replicate the IRQ2→IRQ9
  redirect or you break anything expecting IRQ2.
- Software that uses high IRQs is mostly AT-era; *pure* driver code (program PIC + hook
  vector) runs fine on the V20, but anything that checks the machine ID byte or needs
  286/protected-mode features won't.
- Suggested use of the new lines: dedicate IRQs to **COM3/COM4** and the **ISA slot**,
  freeing the low IRQs and ending serial sharing conflicts.

---

## 6. Video controller — CGA + MDA + Hercules, VGA output

**Goal:** "just works" with stock BIOS/DOS — crisp **80×25 text in 16 colors**, plus
CGA color graphics and Hercules mono graphics, displayed on a **VGA** monitor.

### 6.1 Architecture (period core + modern output stage)
- **MC6845 CRTC** — the genuine timing chip CGA/MDA/Hercules all used. Programmed at the
  standard register addresses so the BIOS and software see a real card. Generates
  display memory addresses (MA), row address (RA), HSYNC/VSYNC, display-enable, cursor.
- **Character generator ROM** — CGA 8×8 and MDA 9×14 fonts (in a small EPROM or carved
  from the flash).
- **Serializer / attribute / mode logic in a CPLD** (e.g. ATF1504AS / XC9572XL) — pixel
  shift register, attribute→16-color mapping, blink/underline, mode register, and the
  **SRAM arbiter** (§4.4). Pure-74-series is possible but impractical for all three
  adapters; a CPLD here is the sane choice and keeps the 6845 as the recognizable heart.
- **Shared SRAM** framebuffer via the arbiter.
- **Scan-doubler → VGA**: a line-buffer SRAM captures each native line (~15.7 kHz CGA /
  ~18.4 kHz MDA) and outputs it at **~31.5 kHz** using the **28.636 MHz** dot clock →
  standard **VGA** RGBHV via a resistor-ladder DAC (RGBI→RGB for 16 colors).

### 6.2 Compatibility specifics
- **CGA:** registers `0x3D4/0x3D5` (6845), `0x3D8` mode, `0x3D9` color, `0x3DA` status;
  framebuffer `0xB8000`. Text 80×25 / 40×25 (16 colors); graphics 320×200×4, 640×200×2.
- **MDA:** registers `0x3B4/0x3B5`, `0x3B8` mode, `0x3BA` status; framebuffer `0xB0000`;
  crisp 9×14 mono text.
- **Hercules (HGC):** MDA superset — `0x3BF` config + 720×348 mono graphics in the
  `0xB0000–0xB7FFF` pages.
- Select primary adapter via config DIP (BIOS reads it). The mono (`B0000`) and color
  (`B8000`) windows don't overlap, so both register sets can coexist; the VGA output
  shows the selected one.

### 6.3 Notes / scope
- Because the output is **re-timed through the scan-doubler/line-buffer**, the *internal*
  pixel clock need not be the exact period analog rates (CGA 14.318 / MDA 16.257 MHz) —
  we keep the correct **register interface, memory layout, and active pixel counts** for
  software compatibility and let the doubler produce clean VGA. This sidesteps needing a
  16.257 MHz source for true MDA timing.
- **16-color *graphics*** (EGA/VGA planar modes) is **out of scope for v1** — CGA text
  is 16-color, CGA graphics is 4-color. For real VGA software modes (mode 13h, etc.),
  drop a **period ISA VGA card** in the slot; a native VGA core is a v2 project.

---

## 7. Storage — on-board XT-IDE / CompactFlash
- Replicate the **XT-IDE rev 2 / "Chuck-mod"** 8-bit IDE port with a **high-byte latch
  (74F573 / 74LS652)** so the 16-bit IDE data register is accessed as two 8-bit
  transfers.
- **CompactFlash in True IDE mode.** Many CF cards support **8-bit transfer mode** (ATA
  `Set Features 0x01`), which the **XTIDE Universal BIOS** can use — letting you skip the
  high-byte latch for CF-only builds. Keep the latch for general IDE drive support.
- **I/O base 0x300** (jumperable), boot ROM = **XTIDE Universal BIOS** in flash @
  `0xC8000`. Poll, or wire **IRQ5**.

---

## 8. Serial / parallel / RTC

### 8.1 Serial (multiple COM + TTL console)
- **16C550** UARTs (16-byte FIFO). For several ports use a **dual TL16C552** or quad
  **TL16C554**.
- **COM1 0x3F8/IRQ4, COM2 0x2F8/IRQ3** (more at 0x3E8/0x2E8 if desired).
- **RS-232** via MAX232-class level shifters on COM1/COM2.
- **TTL serial console header (included):** break out **COM1** (or a dedicated UART) at
  5V/3.3V-TTL on a 0.1″ header for headless bring-up before video works — jumper to
  select RS-232 vs TTL.

### 8.2 Parallel (LPT)
- **Discrete** period-style port: **74LS374** data latch + **74LS244/240** status/control
  buffers, decoded at **0x378 (LPT1)**, IRQ7 (usually polled).

### 8.3 RTC
- **DS12885 / DS12C887** (MC146818-compatible) at **0x70/0x71** (DS12C887 integrates
  crystal + battery).
- XT BIOS/DOS doesn't natively use the 70/71 RTC (AT feature) — include a small **RTC
  driver / BIOS hook** to set the DOS clock at boot.

---

## 9. Keyboard, speaker, and audio

### 9.1 Keyboard (XT-style)
- Motherboard side period-correct: **82C55 port A** + **74LS322 (or 164) shift register**
  deserializes the keyboard's serial stream; assert **IRQ1** on a complete scancode.
- Keyboard: a vintage **XT keyboard**, or a **PS/2→XT converter** dongle (the converter's
  micro stands in for the 8048 that always lived inside the keyboard; the motherboard
  stays discrete). Note XT vs AT/PS-2 use **different protocols/scancode sets**.

### 9.2 PC speaker (included)
- **PIT channel 2** tone ANDed with an **82C55 port-B gate bit** → transistor → speaker.

### 9.3 OPL2 FM synth (included)
- **YM3812 (OPL2)** + **YM3014B** DAC at **0x388/0x389** (AdLib standard) — huge DOS
  game/music support.
- **Mix** the OPL2 line output with the PC-speaker signal into a simple op-amp summer →
  **line-out jack** (and/or a small LM386 amp + speaker).

---

## 10. Game / joystick port (included)
- Standard analog **game port at 0x201**: a quad timer (**558/559**) reads the 2-axis
  pots as charge times; two buttons via a **74LS244**. Trivial and period-correct.

---

## 11. Expansion — single ISA slot
- One **8-bit ISA (PC/XT) slot**: buffered A0–A19, D0–D7, 8288 command lines, `ALE`,
  `CLK` (7.16), `OSC` (14.318), `RESET`, routed IRQs, DRQ/DACK, `IOCHRDY`, `IOCHCK̄`,
  `AEN`, power.
- 7.16 MHz `CLK` is in ISA spec (≤8.33). Expose `IOCHRDY` so slow cards can stretch
  cycles; optionally force **4.77 mode** when the slot is in use.
- A period **ISA VGA card** here is the path to true VGA software compatibility (§6.3).

---

## 12. I/O map, IRQ, DMA

### I/O map
| Range | Device |
|---|---|
| 0x000–0x00F | 82C37 DMA |
| 0x020–0x021 | 82C59 PIC |
| 0x040–0x043 | 82C54 PIT |
| 0x060–0x063 | 82C55 PPI (kbd / switches / speaker) |
| 0x070–0x071 | RTC (146818) |
| 0x080–0x083 | DMA page regs |
| 0x080 | **POST code latch** (write) → hex LEDs |
| 0x0A0 | NMI mask |
| 0x201 | Game/joystick port |
| 0x278/0x378 | LPT |
| 0x2E8/0x2F8/0x3E8/0x3F8 | COM4/COM2/COM3/COM1 |
| 0x300–0x31F | XT-IDE |
| 0x388/0x389 | OPL2 (YM3812) |
| 0x3B0–0x3BF | MDA / Hercules |
| 0x3D0–0x3DF | CGA |

### IRQ
| IRQ | Use | | IRQ | Use |
|---|---|---|---|---|
| 0 | Timer | | 4 | COM1 |
| 1 | Keyboard | | 5 | XT-IDE (or polled) |
| 2 | ISA / spare | | 6 | Floppy (opt) / spare |
| 3 | COM2 | | 7 | LPT1 |

### DMA (mostly spare)
| Ch | Use | | Ch | Use |
|---|---|---|---|---|
| 0 | (refresh — unused) | | 2 | Floppy (opt) |
| 1 | ISA / spare | | 3 | spare |

---

## 13. Bring-up aids (build these first!)
- **POST code display (included):** latch port **0x80** writes to a **2-digit hex /
  7-segment** display. The single most valuable homebrew debug tool.
- **TTL serial console header (included):** see §8.1 — get a console before video works.
- **Reset / power-good:** TL7705A + button + 74HC74 sync (§3.3).
- **Config DIP switches** (installed memory, video type) read via 82C55.
- **Logic-analyzer header** on the demuxed bus.

---

## 14. Optional / future
- **8087 math coprocessor socket** — max mode is already in place; socket it, leave empty.
- **Floppy controller** — 82077AA / 8272 + DMA ch2 + IRQ6, if you want period diskettes.
  Skippable (CF boots DOS), and skipping keeps DMA fully vestigial.
- **PSG sound** (SN76489 / AY-3-8910) in addition to OPL2, for chiptune.
- **Network** — 8-bit NE1000-class card in the ISA slot, or just XMODEM over serial.
- **Native VGA** core — v2; for now use an ISA VGA card.

---

## 15. BOM — period part vs. this build

| Function | Period part | This build |
|---|---|---|
| CPU | 8088 | **NEC V20** (or 8088-2) |
| Clock | 8284A + 14.318 xtal | **28.636 MHz osc + 74HC393/161 divider** |
| Reset/power-good | (PSU power-good) | **TL7705A + 74HC74** |
| Bus controller | 8288 | 8288 |
| Address latch | 8282 | 74AHCT573 ×3 |
| Data transceiver | 8286 | 74AHCT245 |
| Decoder | 74LS138 | 74HCT138 |
| PIC / DMA / PIT / PPI | 8259A / 8237A / 8253 / 8255 | **82C59A / 82C37A / 82C54 / 82C55A** |
| DMA page | 74LS670 | 74LS670 |
| RAM | 9× 4164 DRAM + parity | **2× AS6C4008-55 SRAM** |
| ROM | mask ROM / 2764 | **SST39SF010 flash** |
| Video timing | MC6845 | **MC6845** |
| Video logic | discrete 74-series | **CPLD** (serializer + arbiter + scan-doubler) |
| Font | character ROM | EPROM / flash |
| Video output | RGBI to CGA monitor | **scan-doubler → VGA** (resistor DAC) |
| UART | 8250 | **16C550 / TL16C552/554** |
| LPT | discrete TTL | 74LS374 + 244 |
| RTC | (card) MC146818 | **DS12885 / DS12C887** |
| FM audio | (Sound Blaster/AdLib) | **YM3812 + YM3014B** |
| Game port | discrete | 558 + 74LS244 |
| Storage | ST-506 + WD ctrl | **XT-IDE + CompactFlash** |
| Keyboard | 8255 + 74LS322 | same (+ PS/2→XT converter) |

---

## 16. Open decisions / next steps
- **CPU clock duty cycle:** confirm the V20 accepts the ~50% ÷4 clock at 7.16 MHz; shape
  to ~33% if marginal.
- **Arbiter & scan-doubler:** detail the CPLD design (interleave slots vs the 7.16 MHz
  bus; line-buffer sizing; RGBI→VGA timing).
- **Turbo implementation:** clock-mux details and the software-readable speed bit.
- **BIOS:** primary = **Sergey Kiselev's "8088 BIOS"** (GPL) — purpose-built for
  Micro/Xi-8088-class boards and the only mainstream option with **native RTC + CMOS
  setup** (DS12885/DS12C887), which suits the on-board RTC. Fallback = **GLaBIOS** (MIT,
  ultra-compact, max compatibility) — XT-centric, so it'd use **DIP-switch config + an
  RTC TSR** for the clock. (**Super PC/XT BIOS** is a third, turbo-XT option, also
  driver-based for RTC.) Avoid the copyrighted IBM/Phoenix/Award/AMI BIOSes.
  - **Config method:** CMOS-based setup (Sergey's BIOS, AT-style) vs. DIP switches
    (GLaBIOS/Super + RTC driver). Going with the RTC favors the CMOS path.
  - **Storage:** boot via the **XTIDE Universal BIOS (XUB)** as a separate option ROM at
    flash bank 1 @ `0xC8000` (Sergey's BIOS can integrate XUB into one image).
  - **Video BIOS:** custom, flash bank 1 @ `0xC0000`, for non-CGA/MDA modes. CGA/MDA
    register compatibility means the stock system-BIOS video init works as-is.
- **Flash protection:** software data protection + program-enable jumper.
```

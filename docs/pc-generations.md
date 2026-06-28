# PC Generations — XT → AT → 386 (Hardware Evolution)

How the PC motherboard changed across the first three generations of the IBM-compatible
line. The focus is **board-level hardware**: the CPU, the support chips, the bus, and
the memory subsystem — not software.

See companion docs: `early-pc-cpus.md` (the CPUs in depth), `memory-management.md`
(segmentation / banking / EMS / XMS / A20 / DOS extenders), and `xt-hardware-design.md`
(the homebrew XT-class build).

**One-line summary of the arc:**
- **XT → AT** is *widening* — 16-bit everything, two of each controller.
- **AT → 386** is *restructuring* — the support chips vanish into a chipset and the
  memory subsystem splits onto a fast local bus.
- **XT is the last generation you can faithfully build from discrete, cataloged ICs.**

---

## Generation overview

| | PC/XT (5160) | PC/AT (5170) | 386 board |
|---|---|---|---|
| Year | 1983 | 1984 | 1986 (Compaq DeskPro 386) |
| CPU | 8088 | 80286 | 80386DX |
| Data bus | 8-bit | 16-bit | **32-bit** |
| Address space | 1 MB (20-bit) | 16 MB (24-bit) | **4 GB (32-bit)** |
| Clock | 4.77 MHz | 6 / 8 MHz | 16–33 MHz |
| Support logic | discrete LSI | discrete LSI (more of it) | **integrated chipset** |
| Defining trait | the original | protected mode + 16-bit | 32-bit + chipset + local bus |

---

## Release timeline

The **CPU chip** ships first; the **machines** built around it follow — sometimes by a
year or more. Note the chronological order is **XT → AT → 386 → 486** (the XT predates
the AT); the original PC is included as the anchor since the XT descends from it.

| Date | Event | CPU |
|---|---|---|
| Aug 1981 | IBM PC (5150) — the original | 8088 |
| Feb 1982 | **80286 chip** introduced | — |
| **Mar 1983** | **IBM PC/XT (5160)** | 8088 |
| **Aug 1984** | **IBM PC/AT (5170)** | 80286 |
| Oct 1985 | **80386DX chip** introduced | — |
| Sep 1986 | **Compaq DeskPro 386** — first 386 PC | 386DX |
| Apr 1987 | IBM PS/2 Model 80 (IBM's first 386) | 386DX |
| Jun 1988 | 80386SX chip (cost-reduced) | — |
| Apr 1989 | **80486DX chip** introduced | — |
| Nov 1989 | **Compaq SystemPro** — early 486 system (EISA) | 486DX |
| 1990 | 486 machines go mainstream | 486DX |
| 1991–92 | 486SX (1991), 486DX2 clock-doubled (1992) | — |

Notes on the cadence:
- **XT → AT was fast (~17 months).** The 286 chip had shipped in 1982, so IBM moved
  quickly to build a machine around it.
- **The 286 era was long.** The AT shipped Aug 1984; the first 386 PC didn't appear until
  Sep 1986 and stayed premium into 1988–89, so the 286 was the volume PC for years.
- **The 386 chip-to-machine gap, and who shipped first.** The 386DX chip came Oct 1985,
  but the first 386 PC was **Compaq's DeskPro 386 (Sep 1986)** — not IBM, which didn't
  ship one until the PS/2 Model 80 (Apr 1987). This is the moment IBM lost control of the
  standard (see "The standard fragments" below).
- **486 chip vs. machines.** The 80486DX launched Apr 1989, but systems were mainstream
  only in 1990, with a long life via the **DX2 (1992)** and cheaper **SX**.
- **Spacing widened each generation:** PC→XT ~19 mo, XT→AT ~17 mo, AT→386 machines
  ~25 mo, 386→486 machines ~36 mo — each architectural jump took longer as systems grew
  more complex.

---

## XT → AT changes

Almost every AT change traces back to one root cause: the **80286** and its protected
mode.

### CPU: 8088 → 80286
- 16-bit external data bus; 24-bit address → **16 MB**.
- **Protected mode** and access to **extended memory** above 1 MB (basis of XMS).
- 6 MHz, later 8 MHz. Runs in **real mode** for DOS, which forces several compat hacks.

### Bus: 8-bit ISA → 16-bit ISA ("AT bus")
- A **second edge connector**: D8–D15, LA17–LA23 (24-bit), more IRQ/DMA lines, plus
  `MEMCS16̄`, `IOCS16̄`, `SBHĒ`, `MASTER̄`.
- **Backward compatible** — 8-bit cards use only the front connector. This slot survived
  into the 1990s.

### Interrupts: one 8259A → two cascaded 8259As
- Master `0x20/0x21`, slave `0xA0/0xA1`; slave cascades into master **IRQ2** → **15
  usable IRQs**.
- New: **IRQ8 = RTC, IRQ13 = FPU, IRQ14 = hard disk**. Old IRQ2 cards redirected to
  **IRQ9**.

### DMA: one 8237A → two cascaded 8237As
- Master (ch 0–3, 8-bit) `0x00–0x1F`; slave (ch 4–7, 16-bit) `0xC0–0xDF`.
- **Channel 4** consumed by the cascade → **7 usable channels**; ch 5–7 do 16-bit
  transfers. Page registers extended for 16 MB.

### Keyboard: 8255 PPI → 8042 microcontroller
- Ports `0x60` (data) / `0x64` (command). Far more than a keyboard reader:
  - **Bidirectional** comms (scancode **set 2**).
  - **Controls the A20 gate** (see below).
  - **Pulses CPU reset** — the mechanism to get the 286 from protected back to real mode
    (BIOS uses a **shutdown status byte in CMOS** to resume).
- Leftover 8255 functions (speaker gate, parity enables) move to **port `0x61`**.

### Configuration: DIP switches → battery-backed CMOS + RTC
- **MC146818 RTC + 64 bytes CMOS** at `0x70` (index) / `0x71` (data); **IRQ8**.
- The XT read config from **DIP switches via the 8255**; the AT stores it in **CMOS**,
  edited by a **SETUP** program — the ancestor of "BIOS setup." First on-board RTC.
- (`0x70` bit 7 doubles as the **NMI mask**.)

### A20 gate (new) — protected-mode compatibility
- The 8088 wrapped at `FFFF:FFFF` (only 20 address lines); some software depended on it.
- The 286 doesn't wrap (it reaches the **HMA**), so the AT adds an **8042-controlled gate
  on A20** to force it low (emulate the wrap) or enable it (reach extended memory/HMA).
- Origin of every "enable A20" dance in later DOS/Windows memory managers.

### Math coprocessor: 8087 → 80287
- Reports exceptions via **IRQ13** (the 8087 used **NMI**).

### Storage: birth of ATA/IDE
- AT **fixed-disk task-file registers at `0x1F0–0x1F7` + `0x3F6`, IRQ14** — the direct
  **ancestor of ATA/IDE** (and the standard XT-IDE back-ports to the 8-bit bus).
- **1.2 MB HD 5.25″ floppy**; drive geometry stored as a **type in CMOS**.

---

## AT → 386 changes

Less "bigger CPU + more controllers," more a **reorganization of the whole board** — and
the end of the discrete-support-chip era.

### CPU: 80286 → 80386DX
- **Full 32-bit** (registers, ALU, **32-bit data bus**); 32-bit address → **4 GB**.
- **Paging / virtual memory** (MMU) and **virtual 8086 mode**.
- **Clean protected↔real switching** (clear the PE bit) — the AT's **8042 reset hack is
  no longer needed** for mode changes.
- 16 / 20 / 25 / 33 MHz. The **80386SX** keeps the 32-bit core on a 16-bit bus / 16 MB
  (cost-reduced — same bus-narrowing trick as 8088-vs-8086).

### Support chips collapse into a *chipset* (the defining change)
- The 8259s, 8237s, 8254, 8042, 146818, and bus/memory control get **integrated into a
  few VLSI parts** by C&T (NEAT/CS8221), OPTi, Headland, SiS, UMC, etc.
- **This is where building a PC from individual cataloged chips ends.** XT-class is the
  last era you can do faithfully with discrete ICs.

### Memory subsystem: fast 32-bit local bus, decoupled from ISA
- A **wide, fast local memory bus** (32-bit, at/near CPU speed) connects CPU↔DRAM via
  the chipset's **memory controller**.
- The **ISA bus becomes a peripheral-only expansion bus**, running async at ~8 MHz
  regardless of CPU speed. This CPU/memory ↔ I/O decoupling is permanent from here.
- Packaging: DIP DRAM → **SIMMs** — **30-pin** (8/9-bit, so a **bank of four** for
  32-bit), later **72-pin** (32-bit, one per bank).

### New memory-controller features (chipset + 386 MMU)
- **Shadow RAM** — copy slow ROM BIOS / video BIOS into fast 32-bit RAM over the same
  `F000`/`C000` addresses, then write-protect.
- **Memory remapping** — recover RAM under the `A0000–FFFFF` hole by mapping it above
  1 MB.
- **EMS / UMBs** — the 386's paging lets **EMM386** synthesize EMS and create UMBs (the
  mechanism from `memory-management.md`; why UMBs need a 386). Some chipsets had hardware
  EMS.
- **Page-mode / interleaved DRAM**, programmable **wait states**.

### Cache appears (faster boards)
- DRAM can't keep up at 25/33 MHz → **external SRAM cache** via the **82385 controller**
  (or chipset-integrated) + **fast SRAM + tag RAM**, ~32–256 KB.
- **First CPU cache on PC motherboards** (the 386 has none on-chip; the 486 pulls it in).

### Clock and A20/reset
- **82384 clock generator** drives the 386 with **CLK2** (2× internal clock); ISA `BCLK`
  divided down to ~8 MHz independently.
- **Fast A20 + fast reset via port `0x92`** (PS/2 System Control Port A): bit 1 = A20,
  bit 0 = fast reset — bypassing the slow 8042 round-trip the AT used.

### Coprocessor and high-end buses
- **80387** FPU (proper IEEE 80-bit), still **IRQ13**; some boards added a **Weitek**
  socket.
- 32-bit expansion for workstations/servers: **EISA** (1988, backward-compatible 32-bit
  ISA) and IBM's **MCA / Micro Channel** (1987, 32-bit, proprietary, not compatible).
  Mainstream 386 boards still used **16-bit ISA**; VESA **VL-Bus** came in the 486 era.

### The standard fragments
- The 386 era is when **IBM stopped defining the standard**. **Compaq's DeskPro 386
  (1986)** became the de-facto reference; IBM diverged into **PS/2 + MCA**. "386 board"
  means the **Compaq/clone, chipset-based, ISA/EISA** architecture.

---

## Master comparison table

| Subsystem | XT | AT | 386 board |
|---|---|---|---|
| CPU | 8088, 8-bit, 1 MB | 80286, 16-bit, 16 MB | **80386DX, 32-bit, 4 GB** |
| Modes | real | real + protected (1-way exit) | real + protected + **V86**, clean exit |
| Bus | 8-bit ISA | 16-bit ISA | ISA + **EISA/MCA**; **32-bit local mem bus** |
| Support logic | discrete LSI | discrete LSI ×2 | **integrated chipset** |
| PIC | one 8259A (8 IRQ) | two cascaded (15 IRQ) | chipset (15 IRQ) |
| DMA | one 8237A (4 ch) | two cascaded (7 ch, 16-bit) | chipset |
| Timer | 8253 | 8254 | chipset |
| Keyboard | 8255 + shift reg | **8042 µC** (+A20+reset) | 8042-style, often in chipset |
| Config | DIP switches | **CMOS + 146818 RTC** | CMOS/RTC in chipset |
| A20 | n/a (wraps) | 8042 gate (slow) | **fast A20 (port 0x92)** |
| FPU | 8087 (NMI) | 80287 (IRQ13) | 80387 (IRQ13) |
| Disk | XT/ST-506; XT-IDE | **AT task-file (1F0/IRQ14)** = ATA root | ATA/IDE |
| Memory | DRAM, banks of 9 | DRAM | **32-bit, SIMMs, shadow/remap/cache** |
| Clock | 4.77 MHz | 6/8 MHz, async bus | 16–33 MHz, CLK2, async ISA |

---

## The through-line

- **XT → AT: widening.** Everything doubles to 16-bit; one-of-each controller becomes
  two; the **8042**, **A20 gate**, and **CMOS reset/shutdown** all appear to reconcile the
  286's protected mode with real-mode DOS; the **RTC/CMOS** and **ATA disk interface**
  become permanent fixtures.
- **AT → 386: restructuring.** The CPU goes 32-bit, but the bigger board change is that
  **support chips disappear into a chipset** and the **memory subsystem moves to a fast
  local bus** with a real memory controller (shadow RAM, remapping, cache, EMM386-style
  EMS/UMBs). The memory-management cleverness from `memory-management.md` becomes fast and
  routine here because the 386's paging + a dedicated controller finally make it cheap.

**Build implication:** XT-class is the right — and arguably only — generation for a
faithful discrete-IC machine. The AT roughly doubles the discrete chip count but is still
buildable from individual parts; a 386 board is fundamentally *chipset + CPU + memory
array*, where the interesting logic is sealed inside proprietary VLSI and the
"wire up each function from its own chip" approach no longer maps.

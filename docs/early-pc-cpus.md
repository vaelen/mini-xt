# Early PC CPUs

A summary of the early microprocessors that shaped the personal computer, from the
8-bit CP/M era through the 32-bit chips that defined modern x86. There are really
**two lineages** here, both originating at Intel:

- **Intel 8080 → Intel 8086 → 80286 → 80386** — Intel's own evolution into x86
- **Intel 8080 → Zilog Z80 → Zilog Z180** — Zilog's branch (founded by ex-Intel
  engineers, including 8080 lead Federico Faggin)

The single most important distinction in the early story: **the Z80 is the 8080's
*compatible* successor; the 8086 is its *incompatible* successor.**

---

## Intel 8080 (1974)

The grandfather of the line.

- **8-bit** data bus, **16-bit** address bus → **64 KB** address space
- ~2 MHz typical; ~6,000 transistors
- Required **three power supplies** (+5V, -5V, +12V) plus external clock generator
  (8224) and system controller (8228) — not a single-chip solution in practice
- Accumulator-based; registers A, B, C, D, E, H, L
- Powered the MITS Altair 8800 and the early CP/M ecosystem

## Zilog Z80 (1976)

Zilog's "8080 done right" and a huge commercial success.

- **Binary compatible** with the 8080 — ran 8080 machine code, then *added* to it
- **Single +5V supply**, built-in clock and DRAM refresh → much cheaper systems
- **Extra registers**: alternate register set (A'/F', B'/C', …), index registers
  IX/IY, plus I and R registers
- More instructions: bit manipulation, block moves, relative jumps
- Powered the TRS-80, ZX Spectrum, MSX, Game Boy (custom variant); dominant CP/M chip
- Manufactured for decades; only recently discontinued

## Zilog Z180 (~1985)

A modernized, integrated Z80 — essentially a Z80 system-on-a-chip.

- **Z80-compatible core** (runs Z80 code) plus a few new instructions
- On-chip **MMU** extends physical memory to **1 MB** via banking, while each
  logical address remains 16-bit / 64 KB
- **On-chip peripherals**: DMA, serial ports (ASCI), timers, wait-state generator
- Higher clocks and fewer clocks-per-instruction than the original Z80
- Used in embedded systems and some later CP/M-compatible machines

## Intel 8086 (1978)

Intel's leap to 16-bit — ancestor of every modern x86 PC.

- **16-bit** internal architecture and data bus, **20-bit** address bus →
  **1 MB** via **segmentation** (segment:offset)
- **NOT binary compatible** with the 8080, but designed so 8080 *assembly* could be
  mechanically translated to 8086 assembly
- Richer instruction set, hardware multiply/divide, 16-bit registers
- 6-byte instruction prefetch queue

## Intel 8088 (1979)

The 8086 with a narrower "straw" for moving data.

- **Same 16-bit core** and instruction set as the 8086; runs identical machine code
- **8-bit external data bus** (vs. the 8086's 16-bit) — fetches a 16-bit word in two
  bus cycles, so slightly slower for 16-bit memory access
- Smaller 4-byte prefetch queue (vs. 6 bytes)
- **Chosen for the original IBM PC (1981)** because the 8-bit bus allowed cheaper,
  widely-available 8-bit support chips and memory — cost, not performance, won. This
  is why all of x86 software traces back to the 8088.

## NEC V20 / V30 (1982–84)

Pin-compatible, faster clones of the 8088/8086 — the classic enthusiast upgrade.

- **V20 (µPD70108)** is pin-compatible with the **8088** (8-bit bus); **V30
  (µPD70116)** is pin-compatible with the **8086** (16-bit bus)
- Fully 8088/8086 software compatible; **~5–30% faster at the same clock** thanks to
  faster microcode, better multiply/divide, and more efficient address calculation
- **Hardware 8080 emulation mode** (`BRKEM`) — could execute Intel 8080 code
  directly, letting CP/M-80 software run on a PC (via tools like 22NICE)
- Added some instructions that overlapped with the later 80186/80286
- NEC-unique features were not Intel-compatible, so mainstream DOS software never
  relied on them. Subject of a landmark Intel-vs-NEC microcode-copyright lawsuit,
  which NEC ultimately won on the key question.

## Intel 80286 (1982)

Brain of the IBM PC/AT (1984). Introduced **memory protection**.

- **24-bit address bus → 16 MB** physical memory
- **Protected mode**: memory protection via segment **descriptors** (base + limit +
  access rights) in tables (GDT/LDT), a 4-level **privilege ring** system (0–3), and
  hardware multitasking support
- Still **16-bit** internally; segments capped at **64 KB** — no flat memory model
- **Two infamous flaws**: still stuck in 16-bit/64 KB segments, and **no clean way to
  switch back from protected mode to real mode** (the IBM PC/AT reset the CPU via the
  keyboard controller to get back). This made running real-mode DOS under a
  protected-mode OS very awkward.

## Intel 80386 (1985)

Arguably the most important x86 chip ever — defined IA-32, the model that lasted ~20
years and that 64-bit chips still extend.

- **Full 32-bit** architecture: 32-bit registers (EAX, EBX, …), ALU, data bus
- **32-bit address bus → 4 GB** physical, and **4 GB segments** → enables a **flat
  memory model** (segmentation becomes ignorable)
- **Paging / virtual memory** (4 KB pages, page tables) — hardware MMU giving each
  process its own virtual address space and demand paging; the basis of all modern
  PC OS memory management
- **Virtual 8086 mode (V86)** — run real-mode DOS programs inside a protected, paged
  environment, each isolated (made Windows 386 Enhanced Mode, DESQview, etc. work)
- **Fixed** the 286's one-way mode-switch problem
- Variants: **386DX** (full 32-bit bus) and **386SX** (cheaper, 16-bit external data
  bus, 24-bit address bus / 16 MB) — the same bus-narrowing cost trick as 8088-vs-8086

---

## Comparison table

| Feature | 8080 | Z80 | Z180 | 8086 | 8088 | 80286 | 80386 |
|---|---|---|---|---|---|---|---|
| Vendor | Intel | Zilog | Zilog | Intel | Intel | Intel | Intel |
| Year | 1974 | 1976 | ~1985 | 1978 | 1979 | 1982 | 1985 |
| Internal width | 8-bit | 8-bit | 8-bit | 16-bit | 16-bit | 16-bit | **32-bit** |
| External data bus | 8-bit | 8-bit | 8-bit | 16-bit | **8-bit** | 16-bit | 32-bit |
| Address space | 64 KB | 64 KB | 1 MB (banked) | 1 MB | 1 MB | 16 MB | **4 GB** |
| Max segment | — | — | — | 64 KB | 64 KB | 64 KB | **4 GB (flat)** |
| Runs 8080 code? | — | ✅ | ✅ | ❌ (src only) | ❌ (src only) | ❌ | ❌ |
| Protected mode | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (first) | ✅ improved |
| Paging / virtual memory | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Power supplies | 3 | 1 | 1 | 1 | 1 | 1 | 1 |

---

## The big picture

What each generation *fundamentally* added in the "address more memory" story:

- **8080 / Z80 / Z180** — 8-bit era; reached beyond 64 KB only via **bank switching**
- **8086 / 8088** — 16-bit core; 1 MB via simple **segmentation**
- **80286** — **memory protection** + 16 MB, but trapped in 16-bit/64 KB segments and
  couldn't gracefully run DOS
- **80386** — **32-bit + paging + virtual memory + V86 mode**: the complete modern
  model (flat memory, real virtual memory, safe legacy DOS execution)

Two inventions to remember: **the 286 introduced protection; the 386 introduced
32-bit computing and paging.** The 386 did it so well the architecture remained the
model until AMD's x86-64 (2003), and essentially every protected, multitasking PC OS
(Windows, Linux) assumes a 386-class machine as its floor.

See `memory-management.md` for the companion summary of how these chips addressed
memory (segmentation, banking, EMS/XMS, and DOS extenders).

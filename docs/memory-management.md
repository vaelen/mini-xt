# Memory Management on Early PCs

A summary of how early PCs addressed more memory than their registers could naturally
reach. Every technique here is an answer to the same question:
**"how do I address more memory than my registers natively allow?"** The arc runs:

> **banking (8-bit) → segmentation (8086) → protected mode + paging (286/386) →
> EMS/XMS bolt-ons → DOS extenders → native 32-bit OS**

Each step made the previous trick less necessary, marching toward one goal: *"just
give me a big, flat, automatically-managed block of memory and let me use a pointer."*

See `early-pc-cpus.md` for the companion summary of the CPUs themselves.

---

## 1. Bank switching (the 8-bit-era trick)

Used by the 8080, Z80, 6502 worlds, and later the Z180's MMU and PC EMS.

The CPU's address space stays small (e.g., 64 KB). You install **more physical memory
than that**, then use a **hardware register (latch or MMU)** to select *which* chunk
of physical RAM is visible through a fixed **window** in the address space.

```
CPU address space                          Physical RAM (much larger)
┌───────────────────────┐                  ┌──────────┐ Bank 0
│  fixed region         │                  ├──────────┤ Bank 1
├───────────────────────┤  bank reg = 2    ├──────────┤ Bank 2 ←── visible
│  switchable WINDOW    │ ───────────────► ├──────────┤ Bank 3
└───────────────────────┘                  └──────────┘  ...
```

- Write a bank number to an I/O port / control register; hardware remaps the window.
- **Only the currently-banked window is visible** — the rest of memory is hidden until
  you switch. (Analogy: one picture frame on the wall, a stack of photos you swap in.)
- Examples: Z180 MMU (64 KB logical → 1 MB physical), PC EMS, ZX Spectrum 128K, MSX,
  bank-switched ROM cartridges.

---

## 2. 8086 segmentation (an addressing scheme)

The 8086 has **16-bit registers** (max 64 KB per address) but a **20-bit address bus**
(1 MB). Segmentation bridges the 4-bit gap. Every address is formed from two 16-bit
values:

```
physical address = (segment << 4) + offset      (segment × 16 + offset)
```

Worked example:

```
segment = 0x1234  →  0x12340   (shifted left 4 bits)
offset  = 0x5678  →  0x05678
                     ─────────
                     0x179B8    physical address   (written 1234:5678)
```

### Four segment registers (each a movable 64 KB window)

| Register | Purpose |
|---|---|
| **CS** | Code Segment — instruction fetch |
| **DS** | Data Segment — default data |
| **SS** | Stack Segment — stack (SP/BP) |
| **ES** | Extra Segment — string ops / extra data |

### Quirks

- **Overlapping segments / non-unique addresses**: segments start every **16 bytes**
  (a "paragraph"), so the same physical byte has many `segment:offset` forms
  (e.g. `1000:0000`, `0FFF:0010`, `0F00:1000` all = `0x10000`). Made pointer
  comparison tricky — pointers had to be "normalized."
- **Wraparound and the A20 line**: `FFFF:FFFF` = `0x10FFEF`, ~64 KB past 1 MB. The
  8086 (20 address lines) wrapped to the bottom of memory; later chips didn't, so the
  **A20 gate** hack emulated the wrap for compatibility. That region above 1 MB later
  became the **High Memory Area (HMA)**.
- **Memory models** in C compilers: **near** pointers (16-bit, offset only, within one
  64 KB segment) vs. **far** pointers (32-bit segment:offset, reach all 1 MB). Models
  named tiny / small / medium / compact / large / huge — origin of all the
  `near`/`far`/`huge` baggage in old DOS C.

### Segmentation vs. banking — the core difference

- **Segmentation is an *addressing scheme*.** All 1 MB is *always* addressable; the
  segment register just picks which 64 KB slice the offset measures from. Nothing is
  hidden — you choose a vantage point within fully-visible memory. *(Analogy: a huge
  wall map with a sliding frame — the whole map is right there.)*
- **Banking is a *memory-visibility trick*.** The CPU genuinely can't address the
  extra memory, so hardware swaps physical RAM into the same range. Most memory is
  invisible at any moment. *(Analogy: swapping photos into one frame.)*

| Aspect | Segmentation | Banking |
|---|---|---|
| Where the math happens | In the CPU, every access | External hardware, on request |
| Reach more memory by | Computing segment:offset | Writing a bank number, then accessing window |
| All memory addressable at once? | **Yes** (via some segment:offset) | **No** (only current window) |
| Transparency | Fairly transparent | Intrusive — must switch consciously |

---

## 3. The 640 KB barrier

The IBM PC divided the 8088's 1 MB like this:

```
0x00000 ┌────────────────────────┐
        │  Conventional memory   │  640 KB — DOS + your programs
0x9FFFF │                        │
0xA0000 ├────────────────────────┤
        │  Upper Memory Area     │  384 KB — reserved:
        │  (UMA)                 │   video RAM, BIOS ROM, adapters
0xFFFFF └────────────────────────┘
```

Apps got **640 KB**. Real-mode DOS couldn't address past 1 MB at all. Two different
solutions emerged: **EMS** (banking) and **XMS** (flat memory above 1 MB).

---

## 4. EMS — Expanded Memory (the banking solution)

**LIM EMS** (Lotus / Intel / Microsoft, 1985), born so Lotus 1-2-3 could hold bigger
spreadsheets. It is literally bank switching, sidestepping the 1 MB limit:

1. Extra memory lives on an add-on board (or, later, is emulated by EMM386 on a 386).
2. A **64 KB page frame** is carved from the UMA, divided into four **16 KB pages**.
3. Programs ask the EMS driver to **map** a 16 KB page of board RAM into a window slot.
4. To reach other data, **map a different page** into the window.

```
Upper Memory Area                  Expanded memory board (e.g. 4 MB)
┌──────────────────┐               ┌──────┐ page 0
│ 64 KB page frame │   map req      ├──────┤ page 1
│ ┌──┬──┬──┬──┐    │ ────────────►  ├──────┤ page 2 ← mapped into a window slot
│ │0 │1 │2 │3 │    │                ├──────┤ page 3
│ └──┴──┴──┴──┘    │                └──────┘  ...
└──────────────────┘
```

- Works on **any PC, even an 8088 XT** — it's external hardware, not a CPU feature.
- Access is awkward: map pages one at a time; you can't see all of it at once.
- On 386 machines, **EMM386** could *emulate* EMS from real extended memory using the
  386's paging — no special board needed.
- **LIM EMS 4.0 (1987)** expanded it: >64 KB mappable regions, up to 32 MB, and
  multitasking features (DESQview leaned on this) — but more complex to program.

### EMS was opt-in — apps had to be written for it

An application got **zero benefit** unless its programmers explicitly coded to the EMS
API (`INT 67h`, driver named `EMMXXXX0`). The lifecycle:

| Step | Call | Purpose |
|---|---|---|
| Detect driver | open device `EMMXXXX0` | confirm EMS present |
| Status / version | `INT 67h AH=40h / 46h` | manager healthy? |
| Get page frame | `INT 67h AH=41h` | segment of the 64 KB window |
| Count pages | `INT 67h AH=42h` | how many 16 KB pages free |
| **Allocate** | `INT 67h AH=43h` | returns an **EMM handle** |
| **Map page** | `INT 67h AH=44h` | logical page → physical window slot |
| Save/restore map | `INT 67h AH=47h / 48h` | don't corrupt others' windows |
| **Free** | `INT 67h AH=45h` | release the handle |

The core operation (`AH=44h`) is the banking tax: the **window address never changes**,
but **what's behind it changes** every re-map. To stride through >64 KB you map,
process, re-map, process — constantly. You designed your data structures around 16 KB
pages (Lotus 1-2-3, dBASE, FoxPro, CAD, some games). Software boxes advertised
"supports EMS / LIM 4.0" because it was real engineering, not a free ride. EMS
allocations weren't auto-reclaimed on crash, so a program that didn't deallocate could
leak expanded memory until reboot.

---

## 5. XMS — Extended Memory (the flat-addressing solution)

**XMS** (Microsoft et al., 1988). A totally different beast. On a 286/386, the
physical RAM **above 1 MB** is "extended memory" — plain, linearly-addressed RAM, not
banked. The catch: reaching it requires **protected mode**, which real-mode DOS lacks.

```
            ┌────────────────────────┐
            │   Extended memory      │  ← flat RAM above 1 MB
            │   (1 MB → 16 MB / 4 GB)│     needs 286+ protected mode
0x100000 1MB├────────────────────────┤
            │   UMA (384 KB)         │
0x0A0000    ├────────────────────────┤
            │   Conventional 640 KB  │  ← real mode lives here
0x000000    └────────────────────────┘
```

`HIMEM.SYS` is the XMS driver. It doesn't bank — it offers an **API** to use flat
extended memory, handling protected-mode mechanics (allocate/free blocks; **copy**
data between conventional and extended memory by briefly entering protected mode).
Still **explicit** — apps had to be written for it, just less fiddly than EMS.

Two bonuses HIMEM enabled:

- **HMA (High Memory Area):** with the A20 line on, real-mode code using segment
  `FFFF` reaches ~64 KB just above 1 MB *without* protected mode. `DOS=HIGH` loaded
  most of DOS into the HMA — the biggest everyday reason HIMEM mattered.
- **UMBs (Upper Memory Blocks):** on a 386, `EMM386` mapped real RAM into unused gaps
  of the UMA. With `DOS=UMB` and `LOADHIGH`/`DEVICEHIGH`, TSRs and drivers loaded
  above 640 KB, freeing conventional memory — the point of all that CONFIG.SYS tuning.

### EMS vs. XMS

| | EMS (Expanded) | XMS (Extended) |
|---|---|---|
| Mechanism | **Bank switching** through 64 KB window | **Flat memory** above 1 MB via protected mode |
| Where the memory is | Add-on board (or 386-emulated) | RAM above the 1 MB line |
| Minimum hardware | Any PC, even 8088 XT | 286 (real use needs 386) |
| How a program uses it | Map 16 KB pages into the window | Allocate a block, copy data in/out |
| Driver | `EMM386.EXE` / board drivers | `HIMEM.SYS` (+ `EMM386` for UMBs/EMS-emul.) |
| Model | Projector swapping slides | One big linear sheet |

On a 386 with both: `HIMEM.SYS` provides XMS; `EMM386.EXE` then takes some of that
extended RAM and **simulates EMS** (banking via 386 paging) *and* creates UMBs. One
physical pool served as either XMS or emulated EMS. Typical `CONFIG.SYS`:

```
DEVICE=C:\DOS\HIMEM.SYS
DEVICE=C:\DOS\EMM386.EXE RAM        (RAM = provide EMS + UMBs; NOEMS = UMBs/XMS only)
DOS=HIGH,UMB
```

---

## 6. DOS extenders (flat 32-bit on top of DOS)

By 1990 the 386 had 32-bit flat addressing, paging, and protected mode — but DOS still
ran in real mode. A **DOS extender** is code bundled into your application that flips
the CPU into **32-bit protected mode** at startup, then acts as a tiny runtime beneath
your program so you get **flat 4 GB memory and a normal pointer** while still being
able to call DOS.

```
┌─────────────────────────────────────┐
│  Your 32-bit app (flat memory, 4 GB) │  ← protected mode
├─────────────────────────────────────┤
│  DOS EXTENDER (DOS/4GW, etc.)        │  ← switches modes, thunks INT calls,
│                                      │     sets up descriptors & paging
├─────────────────────────────────────┤
│  Real-mode DOS + BIOS (INT 21h …)    │  ← still 16-bit underneath
└─────────────────────────────────────┘
```

How it works:

1. **Switch to protected mode** — set up GDT/LDT descriptors, create **flat 4 GB
   code/data segments** (base 0, limit 4 GB) so a 32-bit offset alone reaches
   anywhere. Optionally enable paging.
2. **Thunk DOS calls** — DOS/BIOS are real-mode. When the app calls `INT 21h`, the
   extender switches to real (or V86) mode, copies parameters into low (<1 MB) memory
   DOS can see (via a **transfer buffer**, since DOS can't read extended memory),
   runs the real interrupt, switches back, and copies results up to the flat buffers.
3. **Memory management** — the extender's `malloc` hands out flat extended memory, and
   with paging on can provide virtual memory larger than RAM.

### The cooperation problem: who owns protected mode?

An extender, **Windows 3.x (386 Enhanced)**, and **EMM386** all want to control
protected mode / the MMU. Two referee protocols emerged:

- **VCPI (1989)** — let extenders coexist with EMM386-style EMS managers, but didn't
  play nicely inside Windows.
- **DPMI (1990)** — the winner. The app/extender calls a **DPMI host** (via `INT 31h`)
  to allocate descriptors and memory and to safely call real-mode code. The **host
  owns** the CPU's privileged state; the extender is a well-behaved **client**. Under
  Windows, Windows is the host; under plain DOS, the extender ships its own (e.g.
  `CWSDPMI`). This is why a DOS/4GW game ran both at a raw DOS prompt and in a Windows
  DOS box.

### Famous extenders

| Extender | Notable for |
|---|---|
| **DOS/4GW** (Rational/Tenberry) | Bundled free with Watcom C/C++ → Doom, Duke Nukem 3D, Descent, Warcraft, Rise of the Triad. Iconic startup banner. |
| **Phar Lap 286\|/386\|DOS-Extender** | The pioneer; business/CAD (AutoCAD) |
| **DJGPP / CWSDPMI** | GCC port to DOS; freeware/demoscene |
| **PMODE/W, DOS/32A** | Lean DOS/4GW replacements, demoscene |

The payoff: a programmer went from juggling segments, EMS page-mapping, and XMS
copying to simply `malloc`-ing 16 MB as one flat pointer and calling `fopen` —
the extender handling protected mode and DOS thunking invisibly.

---

## 7. How it all ended

DOS extenders were a bridge (~1990–1997), made unnecessary once the OS itself was
natively 32-bit protected mode:

- **Windows 95** ran 32-bit apps natively (Win32)
- **Windows NT / 2000 / XP** dropped the DOS underpinning entirely

A native 32-bit OS *is*, in effect, a permanent DOS extender with a real kernel — flat
memory, paging, and virtual memory built in and shared safely between processes. That
closes the long arc from bank switching to "just use a pointer."

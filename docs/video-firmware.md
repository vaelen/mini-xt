# Video firmware specification (RP2350B soft CGA/MDA/Hercules card)

Standalone contract for the video-card firmware, written so a separate firmware
repo needs no access to this hardware repo. Sources of truth it condenses:
`docs/xt-mcu-sbc-design.md` §8 (architecture), `hardware/sheets/video.py`
(wiring, the authority on GPIO assignments), and
`hardware/notes/questions-video.md` (decisions #2, #3, #8, #10). If this file
and the schematic ever disagree, the schematic wins — update this file.

## 1. What the card is

A "snoop-and-mirror" soft video card on a **Core2350B module (RP2350B, 48
GPIO, 8 MB onboard QSPI PSRAM)** sitting on a 3.3 V-native 8-bit ISA bus. It
emulates CGA, MDA, and Hercules (later VGA — see §8) and renders to VGA and/or
HDMI. Key properties:

- **It owns its video memory.** The host's writes are mirrored into the MCU's
  RAM; host reads are served back by the MCU. No motherboard RAM is involved.
- **It self-decodes.** There is no hardware chip-select. Firmware decodes the
  memory window (0xA0000–0xBFFFF) and the CRTC/mode ports from the snooped
  (already motherboard-latched) address lines. It uses only standard ISA
  signals + power, so the design lifts unchanged onto a standalone ISA card.
- **Writes are the hot path** and complete at 0 wait states (latch into a PIO
  FIFO, let the cycle finish). Reads are rare and wait-stated via IOCHRDY.
- **Output timing is free-running**, decoupled from the bus — which is why
  status-register coherence (§7) is a hard requirement, not a nicety.

## 2. GPIO map

The bus side is 3.3 V; all levels are 3.3 V except HDMI_HPD (5 V from the
sink; RP2350 IO is 5 V-tolerant).

| GPIO      | Net        | Dir (MCU view)  | Purpose                                                     |
|-----------|------------|-----------------|-------------------------------------------------------------|
| GPIO0-7   | SB0-SB7    | Bidir           | 8-bit snoop bus, time-shared through U2-U5 (see §3)         |
| GPIO8     | ~MEMR      | In              | ISA memory read strobe, active low (direct)                 |
| GPIO9     | ~MEMW      | In              | ISA memory write strobe, active low (direct)                |
| GPIO10    | ~IOR       | In              | ISA I/O read strobe, active low (direct)                    |
| GPIO11    | ~IOW       | In              | ISA I/O write strobe, active low (direct)                   |
| GPIO12    | TMDS_D0M   | Out (HSTX)      | HDMI data lane 0, negative                                  |
| GPIO13    | TMDS_D0P   | Out (HSTX)      | HDMI data lane 0, positive                                  |
| GPIO14    | TMDS_CKM   | Out (HSTX)      | HDMI clock, negative                                        |
| GPIO15    | TMDS_CKP   | Out (HSTX)      | HDMI clock, positive                                        |
| GPIO16    | TMDS_D1M   | Out (HSTX)      | HDMI data lane 1, negative                                  |
| GPIO17    | TMDS_D1P   | Out (HSTX)      | HDMI data lane 1, positive                                  |
| GPIO18    | TMDS_D2M   | Out (HSTX)      | HDMI data lane 2, negative                                  |
| GPIO19    | TMDS_D2P   | Out (HSTX)      | HDMI data lane 2, positive                                  |
| GPIO20    | BALE       | In              | Address latch enable (addresses already latched on mobo)    |
| GPIO21    | AEN        | In              | DMA address enable — IGNORE I/O cycles while high           |
| GPIO22    | AOE_LO     | Out, active-low | U3 output enable: A0-A7 onto snoop bus                      |
| GPIO23    | AOE_MID    | Out, active-low | U4 output enable: A8-A15 onto snoop bus                     |
| GPIO24    | AOE_HI     | Out, active-low | U5 output enable: A16-A19 onto snoop bus (4 channels)       |
| GPIO25    | DOE        | Out, active-low | U2 data transceiver output enable                           |
| GPIO26    | DDIR       | Out             | U2 direction: LOW = bus→MCU (default), HIGH = MCU→bus       |
| GPIO27    | IOCHRDY    | Out, open-drain | Wait-state request: drive LOW to stall, else INPUT (Hi-Z)   |
| GPIO28    | VR0        | Out             | VGA red bit 0 (2k ladder resistor)                          |
| GPIO29    | VR1        | Out             | VGA red bit 1 (1k)                                          |
| GPIO30    | VR2        | Out             | VGA red bit 2 (510)                                         |
| GPIO31    | VG0        | Out             | VGA green bit 0 (2k)                                        |
| GPIO32    | VG1        | Out             | VGA green bit 1 (1k)                                        |
| GPIO33    | VG2        | Out             | VGA green bit 2 (510)                                       |
| GPIO34    | VB0        | Out             | VGA blue bit 0 (820)                                        |
| GPIO35    | VB1        | Out             | VGA blue bit 1 (470)                                        |
| GPIO36    | HSYNC      | Out             | VGA horizontal sync (100R series to connector)              |
| GPIO37    | VSYNC      | Out             | VGA vertical sync (100R series)                             |
| GPIO38    | CLK        | In              | ISA bus clock                                               |
| GPIO39    | RESET_DRV  | In              | ISA reset, active HIGH (shares the module user LED)         |
| GPIO40    | —          | —               | Unused (free)                                               |
| GPIO41    | HDMI_HPD   | In              | HDMI hot-plug detect from sink (5 V level)                  |
| GPIO42    | DIS_VID    | In (boot strap) | HIGH = card DISABLED (from motherboard addr_decode JP1.5)   |
| GPIO43    | VID_BASE   | In (boot strap) | LOW = CGA personality, HIGH = MDA/Hercules                  |
| GPIO44-46 | —          | —               | Unused (free)                                               |
| GPIO47    | PSRAM CS   | Out             | Module's onboard QSPI PSRAM chip select (Pico 2 convention) |

Non-GPIO: module powers itself from bus +5V through a Schottky (module-USB
flashing is safe and cannot back-power the board); SWD and module-USB are
available for development.

## 3. The snoop-bus multiplexer (the central hardware quirk)

The RP2350B does not have enough pins for A0-A19 + D0-D7 dedicated (28 GPIO).
Instead, four 74LVC245A transceivers time-share the 8-bit snoop bus SB0-SB7:

| Chip | B side (ISA)    | Enable  | Direction                                  |
|------|-----------------|---------|--------------------------------------------|
| U2   | D0-D7           | DOE     | DDIR-controlled (bidirectional)            |
| U3   | A0-A7           | AOE_LO  | Fixed bus→MCU                              |
| U4   | A8-A15          | AOE_MID | Fixed bus→MCU                              |
| U5   | A16-A19 (SB0-3) | AOE_HI  | Fixed bus→MCU (upper 4 channels unused)    |

Rules the firmware must obey:

- **Exactly one enable low at a time.** All four share SB0-SB7; overlapping
  enables (or DOE low with DDIR high during another chip's window) is a bus
  fight. Sequencing belongs in PIO, not interrupt handlers.
- **Enables are active-low** and parked high (disabled) by pull-ups whenever
  the MCU is Hi-Z (BOOTSEL, pre-init). DDIR is parked low (bus→MCU). Firmware
  must reproduce this safe state (all enables high, DDIR low, IOCHRDY as
  input) as its FIRST act, before clocks and PLLs are even final.
- ISA addresses are already latched by the motherboard for the whole cycle, so
  the mux phases (AOE_LO → sample → AOE_MID → sample → AOE_HI → sample →
  DOE → sample data) can walk through them any time the relevant strobe is
  low. At the slow ISA bus rates, an RP2350 sysclk PIO program has dozens of
  cycles per phase; a full 4-phase capture fits comfortably inside one write
  strobe. Settle time per phase is one '245 tpd + PIO input sync (a few
  sysclk cycles) — budget ~4-5 sysclk per phase minimum.

## 4. Bus-cycle handling

**Cycle detection.** Watch ~MEMW / ~MEMR / ~IOW / ~IOR falling edges (PIO
`wait` on the dedicated GPIOs). Ignore I/O cycles while AEN is high (DMA owns
the bus). 8-bit cycles only — there is no 16-bit anything on this bus.

**Writes (hot path, 0 wait).** On ~MEMW or ~IOW low: walk the mux, capture
A0-A19 + D0-D7, push one word into the RX FIFO, done — the bus cycle was never
stalled. DMA drains the FIFO to a ring buffer; core software filters (is it in
my window? which window?) and applies the write to the mirror + register
state. Only if the FIFO backs up may IOCHRDY be pulled to catch up. Depth of
that buffer is a firmware choice; a mode-13h game blit is a sustained
every-cycle write stream, size for that.

**Reads (rare, wait-stated).** On ~MEMR or ~IOR low with an address that
decodes to us: immediately drive IOCHRDY low (the decode-then-stall latency is
the tightest timing on the card — do the "is it mine" test on A19-A17/port
range in PIO or with a first-stage address capture before deciding), fetch the
byte (VRAM read or emulated register read — planar-VGA reads have side
effects, see §8), set DDIR high, enable DOE, present the byte on SB0-SB7,
release IOCHRDY, and hold the data until the strobe rises; then DOE off, DDIR
back low. IOCHRDY is wire-OR'd: only ever drive it LOW or float it — never
drive high.

**Reset.** RESET_DRV high = ISA reset: return to power-on video state (mode,
registers), but do NOT re-read the straps or drop the display output.

## 5. Boot straps and startup order

1. Safe-park the bus interface (§3) — first thing in boot, before anything
   else can accidentally enable a '245.
2. Read **DIS_VID (GPIO42)**. HIGH = disabled: never enable any bus-facing
   output (no DOE, never drive IOCHRDY); rendering/USB may still run. This is
   how the on-board video yields to a card on the expansion port. NOTE the
   polarity: the strap is on the motherboard's addr_decode jumper block and is
   pulled LOW by default (enabled); a fitted jumper makes it HIGH = disabled.
   (Inverted vs. the pre-2026-07-14 VID_EN strap — no legacy code exists, but
   don't copy that older convention from the design docs' history.)
3. Read **VID_BASE (GPIO43)**: LOW (jumper fitted) = CGA personality (ports
   0x3D4-3DF, window 0xB8000-0xBBFFF), HIGH (open, 10k pull-up) = MDA/Hercules
   (0x3B4-3BF, 0xB0000-0xB7FFF). This is the period MDA/CGA switch equivalent;
   it selects the DEFAULT personality — software mode changes can still do
   whatever the emulated hardware allows.
4. Straps are read ONCE at boot. Both are firmware-honored conventions, not
   hardware gates.

## 6. Address decode (firmware)

| Range               | What                                        | Personality |
|---------------------|---------------------------------------------|-------------|
| 0xB0000-0xB7FFF     | MDA/Hercules VRAM (Herc: 64K, 2 pages)      | MDA         |
| 0xB8000-0xBBFFF     | CGA VRAM (16K; mirror to 0xBFFFF)           | CGA         |
| 0xA0000-0xAFFFF     | EGA/VGA planar aperture                     | later (§8)  |
| 0x3B4,0x3B5         | CRTC index/data                             | MDA         |
| 0x3B8               | Mode control (incl. Hercules gfx enable)    | MDA         |
| 0x3BA               | Status register                             | MDA         |
| 0x3BF               | Hercules configuration switch               | MDA         |
| 0x3D4,0x3D5         | CRTC index/data                             | CGA         |
| 0x3D8               | Mode control                                | CGA         |
| 0x3D9               | Color select                                | CGA         |
| 0x3DA               | Status register                             | CGA         |

Memory window test is A19-A17 (+finer bits for the sub-window); I/O test is
A0-A9 (ISA 10-bit I/O decode). Respond only to the active personality's
ranges — the other window must stay untouched so a second video card can own
it.

## 7. Status-register coherence (hard requirement)

Games and demos poll 0x3DA/0x3BA bit 0 (display enable) and bit 3 (vertical
retrace) for tear-free updates and timing loops. Because the card's output
timing free-runs from the bus, the emulated status bits MUST track the
**actual scan position of the frame being displayed** — derive them from the
real output raster state (scanline counter of the active VGA/HDMI timing,
mapped onto the emulated mode's geometry), never from a free-running timer.
Served through the normal wait-stated read path. CGA quirk to preserve: 0x3DA
reads also reset the 0x3D8 flip-flop behaviors that period software expects
(match documented CGA semantics, not just the bits).

## 8. Emulation scope (staged — the board never changes)

- **v1: CGA + MDA + Hercules**, text and native graphics. Low risk; ship this.
- **Early add: VGA mode 13h** (320×200×256 linear at 0xA0000): flat byte
  writes, easy, unlocks many games.
- **Later: EGA / VGA planar 16-color** (modes 10h/12h). The hard tier: every
  0xA0000 access goes through plane latches / write modes / bit-map masks, so
  writes stop being blind mirrors (read-modify-write inside the cycle) and
  reads have latch and color-compare **side effects**. Extra wait states via
  IOCHRDY are acceptable. The 256 KB aperture lives in the module's PSRAM
  (GPIO47 CS); text/CGA mirrors fit in the 520 KB SRAM.

## 9. Rendering and outputs

- Render the emulated screen once into a framebuffer; **config selects the
  active output** (strap-free: setup choice / HDMI hot-plug on GPIO41).
  Simultaneous dual output is a stretch goal, not a requirement.
- **HDMI**: RP2350 HSTX serializes TMDS directly on GPIO12-19 (fixed HSTX-
  capable bank; pairing per the GPIO table — note D0 and CK sit between D1/D2,
  don't assume the usual lane order). DVI-style signaling (e.g. 640×480@60,
  252 MHz bit clock) is the proven RP2350 path. HPD on GPIO41 tells you a sink
  is present; no DDC/CEC (pins NC on the connector).
- **VGA**: PIO-driven 3R-3G-2B resistor DAC on GPIO28-35 (weights in the GPIO
  table, full scale ≈ 0.7 V into the monitor's 75R) + HSYNC/VSYNC on
  GPIO36/37. Sync polarity is mode-dependent — program per emulated mode.
- Suggested split (convention, not contract): core 0 owns the bus engine
  (FIFO drain, decode, register emulation), core 1 owns rendering; sysclk
  overclocked as needed for the HSTX/pixel clock (PicoDVI-class, ~250-300 MHz,
  is known-good on RP2350).

## 10. Constraints and gotchas summary

- Never enable two snoop-bus '245s at once; never leave DOE enabled with DDIR
  high past the read strobe.
- IOCHRDY: low or Hi-Z only. Also: it has NO local pull-up (the idle-high
  pull-up lives on the motherboard's Bus MCU sheet) — on a future standalone
  card, the wrapper must re-add one.
- DIS_VID high = fully bus-silent (rendering may still run).
- AEN high = ignore I/O strobes (DMA cycles).
- GPIO39 (RESET_DRV) doubles as the module's user LED — treat it as input
  only; don't use the "blink the LED" examples.
- GPIO40, 44-46 are the only free pins. Budget accordingly.
- 8-bit bus, no IRQ line, no DMA use by this card — it is purely a snooping
  target.

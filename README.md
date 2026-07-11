# mini-xt

A from-scratch, IBM XT-compatible single-board computer, built as a set of small
PCBs around a real **NEC V20** CPU with modern **Raspberry Pi RP2350B / RP2040**
microcontrollers standing in for the out-of-production Intel 8000-series support
chips. After the substitutions, the only irreplaceable vintage silicon left on
the board is the V20 itself.

## The idea

The buffered **8-bit XT/ISA bus is the integration contract**. The V20 plus
minimal 74HCT glue creates a real XT bus; every other function hangs off it
either as a real chip (16C550 UARTs, DS12C887 RTC, XT-IDE + CompactFlash) or as
an MCU **"soft card"** that talks the bus exactly as a period ISA card would —
each with its own local level shifters, PicoGUS-style. Soft cards may use *only*
signals that exist on the ISA bus, which keeps each one independently
developable and liftable onto a standalone ISA card unchanged.

The "motherboard" itself is a **two-MCU chipset** split by timing domain:

| Node                    | Part    | Role                                                        |
|-------------------------|---------|-------------------------------------------------------------|
| Bus MCU ("fast hands")  | RP2350B | Soft PIC/PIT/KBC/DMA/NMI/POST; bus slave *and* bus master   |
| Supervisor ("slow brain")| RP2040 | USB HID host, setup UI, config, BIOS image storage, console |
| Video                   | RP2350B | Soft CGA/MDA/Hercules, snoop-and-mirror → VGA + HDMI        |
| Audio                   | RP2040  | On-board PicoGUS (stock firmware): AdLib/SB/GUS/MPU + joystick |

There is no BIOS ROM: the Bus MCU shadow-loads the BIOS (Xi 8088, forked) into
SRAM at boot from images the Supervisor holds in flash, then releases the V20's
reset. RAM is 2× AS6C4008 SRAM (640 KB conventional + UMB); video RAM lives
inside the video MCU.

## Repository layout

| Path                              | Contents                                                       |
|-----------------------------------|----------------------------------------------------------------|
| `docs/xt-mcu-sbc-design.md`       | **The main design doc** — the MCU-hybrid build implemented here |
| `docs/xt-hardware-design.md`      | Companion design: the same machine from period chips (82Cxx, MC6845, CPLD) |
| `docs/early-pc-cpus.md`           | Background: 8080→Z80→8086/8088→V20→286→386 lineage             |
| `docs/memory-management.md`       | Background: segmentation, the 640 KB barrier, EMS/XMS          |
| `docs/pc-generations.md`          | Background: XT→AT→386 board evolution; why XT-class is the target |
| `hardware/`                       | KiCad 9 schematics (generated — see below) + `README.md`      |
| `hardware/sheets/*.py`            | Declarative per-sheet schematic builders (the real sources)   |
| `hardware/tools/`                 | The Python schematic generator (`mxsch.py`), signal contract (`mxbus.py`), build harness |
| `hardware/cards/`                 | Standalone, chainable dev PCBs (video, ISA tester)            |
| `hardware/notes/`                 | Design decisions + open questions logged during generation    |

## The schematics

The `.kicad_sch` files are **generated** by a small purpose-built Python
generator from the builders in `hardware/sheets/` — edit the `.py` files, not
the KiCad files. They are interface-focused: real component symbols, every
inter-module signal exposed as a hierarchical pin, key supporting parts and
decoupling — optimized for seeing module boundaries and how cleanly the
subsystems isolate, not (yet) for a finished PCB.

```sh
kicad hardware/mini-xt.kicad_pro          # browse: root sheet = the ISA backplane
python3 hardware/tools/build.py           # regenerate all sheets + root, run ERC + netlist
```

The video sheet exists in both forms — on the motherboard *and* as a standalone
PCB in `hardware/cards/`, with two chainable 60-pin ISA headers (standard 8-bit
ISA pinout) so it can be fabbed and daisy-chained against the ISA tester before
the motherboard exists.
The other peripherals (COM ×2, LPT, RTC, storage) live on the motherboard only —
still one isolated sheet each, jumper-configured like real cards (enable, base
address, IRQ), so any of them can still be lifted onto a separate PCB later by
re-adding a small `card_*` wrapper.

See `hardware/README.md` for the sheet list and
`hardware/tools/SHEET_AUTHORING_GUIDE.md` for how to author a sheet.

## The sub-boards

Every sub-board obeys the same contract: it talks **only standard 8-bit ISA
signals plus +5 V/GND**, self-decodes its own addresses, enters the bus on
`J_IN` and passes it through unchanged to `J_OUT` (60-pin headers, standard
8-bit ISA pinout), and fits the ≤100 × 100 mm SMD fab tier. Any card can
therefore be developed against the `card_isatest` board alone, chained with
the others in any order, and later lifted unchanged onto a real ISA card or
into the combined board.

- **`card_video`** — soft CGA/MDA/Hercules on an RP2350B (Core2350B module,
  8 MB PSRAM variant for the future VGA aperture). Snoop-and-mirror design:
  it owns its video RAM, captures bus writes to `0xA0000–0xBFFFF` and the
  CRTC/mode ports at 0 wait through a PIO FIFO, and serves the (rare) reads
  itself, wait-stated via IOCHRDY — so there is no shared-framebuffer
  arbitration and no CGA snow. Renders once to internal RAM, outputs VGA
  (resistor-ladder DAC) or HDMI (RP2350 HSTX on GP12–19, no transmitter
  chip); graphics scope (CGA → mode 13h → planar VGA) is purely a firmware
  milestone. Its own 74LVC245A shifters and the module's LDO keep it a
  self-contained 3.3 V island on the 5 V bus. Two boot-read straps stand in
  for a period card's switches (decode is firmware, so there's no hardware
  chip-select to jumper): JP1 open = card disabled — firmware keeps every
  bus-facing OE off, and all its drivers are MCU-gated tri-states; JP2
  picks the default window set, closed = CGA (0x3D4/0xB8000), open =
  MDA/Hercules (0x3B4/0xB0000).

- **`card_isatest`** — the development jig: a Raspberry Pi Pico acting as
  the *motherboard* side of the bus (the opposite role from every other
  card) so any card — or a real ISA card in its edge-connector slot — can
  be exercised over USB serial with no mini-xt hardware present. Pin-count
  arithmetic drives its design: address/control go out through split 74HC595
  shift chains (address updates don't disturb the control byte), IRQ/DRQ/
  IOCHCK# come back through a 74HC165 chain, and only the hot data path
  D0–D7 gets direct GPIO. It generates the real 14.318 MHz clock tree
  (÷2/÷3, PIO override), and the DUT's 5 V rail is switched by a
  default-off P-FET fed from USB or a barrel jack, so a shorted
  device-under-test can't take the tester down.

The **motherboard** proper (V20 + SRAM + the two-MCU chipset + power/audio,
the `hardware/sheets/` hierarchy) is the third board: the one node allowed
private side-channels, since it *is* the machine the cards plug into. Its
on-board peripherals keep the same soft-card discipline (own sheet, ISA
signals + power only) and are jumper-configured like the period cards they
replace:

- **COM1/COM2** — one `com_port` sheet instanced twice: 16C550 (SMD PLCC-44
  socket taking new TI silicon or period NS16550AFN pulls) + MAX3241 for a
  full DB9 DTE, 1.8432 MHz crystal baud reference. Per port: J2 base address
  (0x3F8/0x2F8), JP2 IRQ (4/3, open = polled), JP3 enable (open parks the
  16550's CS1 — the port simply never decodes), JP1 RX source (DB9 vs 5 V
  TTL console header, COM1).
- **LPT** — period-correct SPP at JP1-strapped 0x378/0x278 in discrete 74HCT
  ('574 latches, '244 buffers, AND-tree decode); Busy inverted on-card into
  status bit 7, IRQ7/IRQ5 strap (JP3, tri-state driver, open = polled), JP2
  enable gates the register-select '138. DB25 out.
- **RTC** — DS12C887 (integral battery + crystal, machined DIP-24 socket) at
  the PC-standard 0x70/0x71: Intel bus mode, discrete exact 10-bit decode
  synthesizing the multiplexed AS/DS/R~W cycle from ~IOW/~IOR, open-drain
  ~IRQ inverted onto IRQ8.
- **PicoGUS** — a faithful on-board copy of polpo's PicoGUS 2.0 "chip-down"
  design (CERN-OHL-P): a bare RP2040 running **stock PicoGUS firmware**
  (AdLib/SB/GUS/MPU-401/CMS/Tandy), with the reference's ADS-muxed shared
  AD bus through CB3T FET switches, BUSOE power-up latch, APS6404L sample
  PSRAM, PCM5102A I²S DAC, and the IRQ/DMA jumper block (jumper DMA to
  **channel 1** — the only MCU-serviced channel; IRQ5 is free now that
  storage defaults to IRQ14). Deviations, all logged: no gameport (USB HID
  instead), no wavetable header or MIDI-out jack (build simplification —
  the volume chip and mix node went with them; the firmware's volume/MIDI
  GPIOs are documented no-connects), audio feeds the board's one line-out
  jack via the summer, and programming arrives over the Supervisor's shared
  USB-C port (SW2 selector) instead of a local connector.
- **Storage** — a true XT-IDE rev 2 ("Chuck-mod"): the A0↔A3 address-line
  swap puts the data register at 0x300 and the '573 high-byte latch at
  0x301, exactly the layout XTIDE Universal BIOS's "XT-IDE rev 2" type
  boots fastest; the latch pair turns the 16-bit IDE data register into
  two 8-bit transfers. A 40-pin IDE header and a CompactFlash socket
  (True-IDE) hang off the same bus. Straps: JP1 base 0x300/0x320, JP2
  enable (lifts the decode '138 — every select, latch clock and buffer
  goes inert), JP3 IRQ — **IRQ14 default** (AT primary-IDE convention,
  collected by the Bus MCU's cascaded second '165; motherboard-internal
  line), IRQ5 alternate, open = polled. No boot ROM on the interface: the
  Bus MCU shadow-loads XTIDE Universal BIOS into SRAM at boot.

The on-board video instance carries the same straps as its standalone card
(VID_EN + CGA/MDA window strap). Disabling an on-board port (or re-strapping
its address/IRQ) frees the slot for the same peripheral on the sidecar chain —
the drivers are tri-state, so an on-board port and a card can coexist as long
as they don't claim the same address or IRQ: run the on-board XT-IDE at 0x300
beside a real 8-bit ISA IDE card at 0x320, or on-board video as CGA beside an
MDA-strapped `card_video`.

## Fabrication

Boards are fabricated and assembled at **JLCPCB**: SMD construction so each
sub-board fits the cheap ≤100 × 100 mm tier, with through-hole only for
connectors/headers and for the fab-installed **sockets** that carry the
irreplaceable parts (the V20, the 5 V SRAMs, the DS12C887, and the MCU
modules). Every schematic component carries an `LCSC Part Num` property —
generated from the sourcing map in `hardware/tools/parts.py` — so the BOM
export drives JLCPCB assembly directly. Sourcing decisions, verified pinouts,
and stock-forced substitutions are logged in
`hardware/notes/jlcpcb-sourcing.md`.

## Status

Schematic capture / architecture-validation stage. Firmware (Bus MCU chipset
emulation, video, Supervisor) and PCB layout have not been started. Open items
are tracked in `hardware/notes/open-questions.md` and
`docs/xt-mcu-sbc-design.md` §16.

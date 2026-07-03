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
| `hardware/cards/`                 | Standalone, chainable soft-card dev PCBs (video, COM, LPT, RTC, storage, ISA tester) |
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

Each soft card also builds as its own standalone PCB in `hardware/cards/`, with
two chainable 60-pin ISA headers (standard 8-bit ISA pinout) so cards can be
fabbed and daisy-chained for development before the motherboard exists.

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
  self-contained 3.3 V island on the 5 V bus.

- **`card_com`** — one full RS-232 port: 16C550 UART + MAX3241 (3 drivers /
  5 receivers = a complete DB9 DTE with all modem lines, no ±12 V thanks to
  the charge pump). The UART sits in an SMD PLCC-44 socket that accepts new
  TI silicon, NOS tubes, or period NS16550AFN pulls alike. Strap-configured,
  not hard-wired: J2 picks the base address (0x3F8/0x2F8), JP2 picks the
  matching IRQ (4/3), JP1 switches the UART's RX between the DB9 and a 5 V
  TTL console header. Baud reference is a 1.8432 MHz crystal on the 16C550's
  own oscillator, so the card needs nothing but the 5 V rail.

- **`card_lpt`** — a period-correct SPP/Centronics printer port at 0x378
  built from nothing but 74HCT logic: '574 latches for the data and control
  registers, '244 buffers for status and read-back, discrete AND-tree
  address decode. Register semantics match a real LPT card bit-for-bit
  (Busy inverted on-card into status bit 7; Strobe/AutoFd/SelectIn inverted
  on the way out) and IRQ7 is driven tri-state, only during an enabled ~Ack
  pulse, so the line stays shareable. DB25 out.

- **`card_rtc`** — the machine's clock and CMOS: a DS12C887 (integral
  battery + crystal, in a machined DIP-24 socket) at the PC-standard
  0x70/0x71. Strapped to Intel bus mode and glued to the demultiplexed ISA
  bus by a discrete exact 10-bit decode ('138 + NOR/AND tree) that
  synthesizes the multiplexed AS/DS/R~W cycle from ~IOW/~IOR; its
  open-drain ~IRQ is pulled up and inverted to the bus's active-high IRQ8.

- **`card_storage`** — mass storage as a true XT-IDE rev 2 ("Chuck-mod"):
  the A0↔A3 address-line swap puts the data register at 0x300 and the
  '573 high-byte latch at 0x301, exactly the layout XTIDE Universal BIOS's
  "XT-IDE rev 2" type boots fastest, and the latch pair turns the 16-bit
  IDE data register into two 8-bit transfers. Both a 40-pin IDE header and
  a CompactFlash socket (True-IDE) hang off the same bus; IRQ5 out,
  parked low so an empty card can't interrupt-storm.

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
the `hardware/sheets/` hierarchy) is the seventh board: the one node allowed
private side-channels, since it *is* the machine the cards plug into.

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

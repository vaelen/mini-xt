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
fabbed and daisy-chained for development before the motherboard exists. The
`card_isatest` board is a Pico-based ISA bus master for exercising any card
over USB serial.

See `hardware/README.md` for the sheet list and
`hardware/tools/SHEET_AUTHORING_GUIDE.md` for how to author a sheet.

## Status

Schematic capture / architecture-validation stage. Firmware (Bus MCU chipset
emulation, video, Supervisor) and PCB layout have not been started. Open items
are tracked in `hardware/notes/open-questions.md` and
`docs/xt-mcu-sbc-design.md` §16.

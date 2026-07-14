# mini-xt — KiCad schematics

Hierarchical KiCad 9 schematics for the XT-class MCU-SBC described in
`../docs/xt-mcu-sbc-design.md`. Interface-focused: real component symbols, every
inter-module signal exposed as a hierarchical pin, key supporting parts and
decoupling — optimized for seeing the module boundaries and how cleanly the
subsystems isolate, not for a finished PCB.

## Open it

```
kicad mini-xt.kicad_pro      # then open mini-xt.kicad_sch (the root sheet)
```

The root sheet is the buffered ISA backplane; double-click any sheet symbol to
descend into a subsystem.

## Layout

| File | Subsystem |
|---------------------------|--------------------------------------------------|
| `mini-xt.kicad_sch`       | root — 3.3V ISA backplane + sheet instances + power |
| `sheets/cpu_core`         | V20 CPU, SRAM, clock tree, reset, the board's one 5V↔3.3V boundary |
| `sheets/bus_mcu`          | Bus-master RP2350B: soft chipset (incl. RTC ports 0x70/71) + addr counter + IRQ collector, GPIOs direct on the 3.3V bus (no local level shifters) |
| `sheets/supervisor`       | RP2040: USB host, setup UI, POST, console, link, battery-backed PCF8563 RTC |
| `sheets/video`            | RP2350B soft CGA/MDA/Herc → HDMI + VGA; 4× 74LVC245A PIO time-share mux |
| `sheets/com_port`         | 2× TL16C550CPFBR + MAX3241 + DB9 (COM1+COM2)      |
| `sheets/addr_decode`      | central I/O decode + IRQ mapping + the 2×5 disable-jumper block JP1 (bases hardwired) |
| `sheets/parallel`         | discrete 74HC/74LVC LPT @ 0x378 + DB25            |
| `sheets/power`            | USB-C 5 V in → 3.3 V buck                         |
| `sheets/storage`          | XT-IDE (Chuck-mod) + CompactFlash                |
| `sheets/audio`            | PC-speaker + op-amp summer → line-out            |
| `sheets/sidecar`          | buffered 5V-compatible ISA expansion port: 50-pin (2×25) header + ~7-package isolation bank, incl. one DMA channel (EXT_DRQ / EXT_DACK̄) |
| `sheets/picogus`          | PicoGUS chip-down copy: RP2040 AdLib/SB/GUS/MPU  |
| `mini-xt.kicad_sym`       | custom symbols (V20, MAX3241, IS62WV51216, TL16C550PT, PCF8563, flat 74xx)|

There is no `sheets/rtc` any more — the RTC is emulated in the Bus MCU
(ports 0x70/0x71) with battery-backed timekeeping on the Supervisor
(PCF8563 + CR2032); see `notes/open-questions.md`'s 2026-07-14 entry.
There is no `sheets/network` any more either — the RTL8019AS NE2000 NIC was
removed 2026-07-14 (git tag `full-board-with-nic` has the last design that
carried it); a real NE2000 card on the expansion port fills the role.
The standalone dev cards (`sheets/card_video`, `sheets/card_isatest`) and
`hardware/cards/` were deleted 2026-07-14 too — the long-term plan is an ISA
backplane expansion board on the sidecar port; git history has their last
versions.

## How these were generated

The `.kicad_sch` files are emitted by a small Python generator in `tools/`
(`mxsch.py`) from declarative per-sheet builders (`sheets/*.py`). To regenerate:

```
python3 tools/build.py                       # writes all sheets + root, runs ERC + netlist
python3 tools/validate_sheet.py <name>       # ERC one sheet in isolation
python3 tools/pins.py <Lib:Name>             # introspect a symbol's pins
```

To author or change a sheet, edit `sheets/<name>.py` and re-run `build.py`.
See `tools/SHEET_AUTHORING_GUIDE.md`.

## Fabrication (JLCPCB)

Every component carries an `LCSC Part Num` property, generated at build time
from the sourcing map in `tools/parts.py` (SMD parts; the motherboard is one
>100×100 mm board since the 2026-07-14 3.3V single-board redesign;
fab-installed sockets are down to the V20 + the Core2350B/Pico module
headers). The sheets
stay generic; the parts map is the single place where generic symbols bind to
purchasable parts. Decisions, verified pinouts, and stock-forced
substitutions: `notes/jlcpcb-sourcing.md`.

## Notes / decisions

`notes/open-questions.md` records the decisions made during generation and the
items to review; `notes/questions-<sheet>.md` hold per-sheet specifics.

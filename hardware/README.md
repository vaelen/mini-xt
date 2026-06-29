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
| `mini-xt.kicad_sch`       | root — ISA backplane + sheet instances + power   |
| `sheets/cpu_core`         | V20 CPU, SRAM, clock tree, reset, bus buffers    |
| `sheets/bus_mcu`          | Bus-master RP2350B: soft chipset + level shifters + addr counter + IRQ collector |
| `sheets/supervisor`       | RP2040: USB host, setup UI, POST, console, link  |
| `sheets/video`            | RP2350B soft CGA/MDA/Herc → HDMI + VGA           |
| `sheets/com_port` (×2)    | 16C550 + MAX3241 + DB9 (COM1/COM2)               |
| `sheets/parallel`         | discrete 74HC LPT @ 0x378 + DB25                 |
| `sheets/rtc`              | DS12C887 @ 0x70/0x71                              |
| `sheets/power`            | USB-C 5 V in → 3.3 V buck                         |
| `sheets/storage`          | XT-IDE (Chuck-mod) + CompactFlash                |
| `sheets/audio`            | PC-speaker + op-amp summer → line-out            |
| `sheets/sidecar`          | 2×32 IDC ISA expansion header                    |
| `mini-xt.kicad_sym`       | custom symbols (V20, MAX3241, DS12C887, flat 74xx)|

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

## Notes / decisions

`notes/open-questions.md` records the decisions made during generation and the
items to review; `notes/questions-<sheet>.md` hold per-sheet specifics.

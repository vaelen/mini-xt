# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An IBM XT-compatible single-board computer built around a real NEC V20 CPU with
RP2350B/RP2040 MCUs replacing the vintage Intel support chips. This repo is
currently **hardware only** (KiCad 9 schematics + design docs); there is no
firmware yet.

- `docs/xt-mcu-sbc-design.md` is the authoritative design doc for what
  `hardware/` implements. (`docs/xt-hardware-design.md` is a *different*,
  period-chip variant of the design — don't conflate them. The other docs/ files
  are background research.)
- `hardware/notes/open-questions.md` logs design decisions already made and
  items flagged for review; `hardware/notes/questions-<sheet>.md` hold per-sheet
  decisions.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` hold feature specs and
  implementation plans (e.g. the ISA test card).

## Generated files — edit the Python, not the KiCad files

All `.kicad_sch` files (plus `mini-xt.net`, `*.kicad_pro`, `sym-lib-table`,
`erc.rpt`, `*.rpt`) are **build outputs** of a purpose-built generator. The real
sources are:

- `hardware/sheets/<name>.py` — one declarative builder per hierarchical sheet
- `hardware/tools/mxbus.py` — the canonical signal-name contract
- `hardware/tools/mxsch.py` — the S-expression schematic generator
- `hardware/tools/build.py` — assembles the root sheet, ties sheets together,
  assigns per-instance reference banks (U1 in bank 3 → U301), runs ERC + netlist
- `hardware/sheets/isa_conn.py` — shared 60-pin ISA header (standard 8-bit ISA
  pinout) used by the sidecar sheet and every standalone card
- `hardware/tools/parts.py` — the JLCPCB/LCSC sourcing map: (lib_id, value) →
  LCSC part number, applied at build time as an `LCSC Part Num` property on
  every component (that property is what drives the JLCPCB assembly BOM)

UUIDs are generated deterministically (uuid5 seeded by sheet title +
counter), so a rebuild from unchanged sources is byte-identical — a large
`.kicad_sch` diff always means a real change.

## Commands

Requires KiCad 9. The tools find it via `$KICAD_CLI` / `$KICAD_SYMBOL_DIR`,
then `kicad-cli` on PATH, then the snap install (`mxsch.kicad_cli()` /
`kicad_symdir()`).

```sh
python3 hardware/tools/build.py                # regenerate motherboard: all sheets + root, ERC + netlist
python3 -c 'import sys;sys.path.insert(0,"hardware/tools");import build;build.build_cards()'
                                               # regenerate standalone dev cards -> hardware/cards/
python3 hardware/tools/validate_sheet.py <name>  # build + ERC ONE sheet in isolation (fast loop)
python3 hardware/tools/pins.py <Lib:Name>      # list a symbol's pins (e.g. mini-xt:V20, 74xx:74HCT573)
python3 hardware/tools/pins.py -s <substr>     # search symbol names
```

`build.py` exits nonzero if any **structural** ERC category
(`endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`) is
hit or the netlist export fails; the expected noise categories don't fail it.

## Fabrication constraints (JLCPCB)

Boards are fabbed and assembled at JLCPCB. Rules that shape every sheet:

- **Stay generic in the schematics** (74-series logic, Device:R/C/L, generic
  connectors); the binding to concrete purchasable parts lives ONLY in
  `tools/parts.py`. A part swap (or a future through-hole build) is a
  parts.py change, not a sheet change. When a sheet must deviate from the
  generic symbol (e.g. a value override like `74HC161` on the 74HCT163
  body), say why in a comment.
- **SMD construction** to keep each board within **100 × 100 mm** (the cheap
  JLC tier): 0603 passives, SOIC/TSSOP logic. Through-hole is reserved for
  connectors, headers, jumpers — and the socketed parts below.
- **Sockets, installed by the fab**, for expensive/irreplaceable chips: the
  V20 (DIP-40), the 2× AS6C4008 SRAMs (DIP-32; no 5 V 512K×8 SRAM exists at
  JLC), the DS12C887 (DIP-24 600 mil), and female headers for the
  Core2350B/Pico modules. For these the `LCSC Part Num` is the SOCKET.
- **Sub-boards stay standalone**: each card must remain buildable as its own
  ≤100×100 mm PCB that daisy-chains over the 60-pin ISA headers; a combined
  board comes later, after the separate boards are proven.
- **Voltage domains matter for substitutions**: 74HCT reads 3.3 V inputs at
  5 V; plain 74HC does NOT (Vih ≈ 3.5 V) and is only used where every input
  is 5 V-driven or the part itself runs at 3.3 V. When JLC stock forces an
  HC-grade part into a 3.3 V-driven position, buffer the input through a
  spare HCT gate. `hardware/notes/jlcpcb-sourcing.md` records all current
  substitutions, the socket policy, and the parts that must be sourced
  elsewhere (ISA edge slot, VGA DE15, the V20 itself).
- Custom-symbol pin numbers are verified against JLCPCB/EasyEDA data (the
  MAX3241 and DS12C887 were both wrong before 2026-07-03 — do the same
  check before trusting any new hand-authored symbol).

## Authoring a sheet

Read `hardware/tools/SHEET_AUTHORING_GUIDE.md` first — it is the authoritative
how-to. `hardware/sheets/cpu_core.py` is the worked reference example. Key rules:

- **Connectivity is by net name**, never by drawing long wires:
  `sch.net(comp, pin, "NETNAME", kind="label", dx=..., dy=...)` stubs a labeled
  wire; same name = same net, and names matching the sheet's `PINS` list become
  the cross-sheet interface via `mxbus.emit_interface`.
- **Use the exact canonical names from `mxbus`** (`A0..A19`, `D0..D7`,
  `IRQ2..IRQ15`, `~{MEMR}`, `BALE`, `IOCHRDY`, ...). A typo'd name silently
  fails to connect across sheets. Active-low = KiCad overbar `~{NAME}`.
- **Isolation rule (the point of the whole exercise):** soft-card sheets
  (video, com_port, parallel, rtc, storage, sidecar, audio, card_*) may use
  *only* ISA signals + power. Private nets (`PRIV_*` in mxbus: HOLD/HLDA, UART
  link, counter strobes, SPEED_SEL, Y5) are motherboard-only. Never leak one
  into a soft card — log a question instead.
- Place on the 2.54 mm grid; ~40–60 mm part spacing; one net = one name.
- When the design under-specifies something, do **not** stop: make a
  best-guess decision, log it in `hardware/notes/questions-<sheet>.md`
  (question / why / options / pick), and proceed.
- Custom symbols live in `hardware/mini-xt.kicad_sym` (`mini-xt:` prefix): V20,
  MAX3241, DS12C887, Core2350B, Pico, and flat single-body 74xx glue (KiCad's
  stock multi-unit 74xx symbols don't work with the generator). New flat
  symbols are generated via `tools/gensym.py`.

## Validation expectations

`validate_sheet.py <name>` must report **zero**: `endpoint_off_grid`,
`unconnected_wire_endpoint`, `multiple_net_names`, and "Failed to load".

Expected/ignorable at this fidelity (interface-focused schematic, not a
manufacturable board): large counts of `pin_not_connected`, `pin_not_driven`,
`label_dangling`, `pin_to_pin` (shared bus without modeled tri-state), and
`lib_symbol_issues` from the CLI. Don't try to drive these to zero, and don't
report them as findings.

The netlist (`hardware/mini-xt.net`) is the ground truth for connectivity —
after wiring changes, verify the affected net spans the sheets it should
(grep for the net name and check its node list).

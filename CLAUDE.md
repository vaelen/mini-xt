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
- `hardware/sheets/isa_conn.py` — shared 50-pin (2×25) ISA expansion header
  (project-private 8-bit ISA subset; OSC/REFRESH#/DRQ2-3/DACK0,2-3 omitted),
  used by the sidecar sheet — and by the planned ISA backplane board
- `hardware/tools/parts.py` — the JLCPCB/LCSC sourcing map: (lib_id, value) →
  LCSC part number, applied at build time as an `LCSC Part Num` property on
  every component (that property is what drives the JLCPCB assembly BOM)

UUIDs are generated deterministically (uuid5 seeded by sheet title +
counter), so a rebuild from unchanged sources is byte-identical — a large
`.kicad_sch` diff always means a real change.

## Commands

Requires KiCad 9 or 10. The tools find `kicad-cli` via `$KICAD_CLI`, then
PATH, then the snap install (`mxsch.kicad_cli()`); symbol libraries via
`$KICAD_SYMBOL_DIR`, then snap, then `~/.local/share/kicad/<ver>/symbols`
(where the KiCad 10 AppImage setup keeps them), then the system install
(`mxsch.kicad_symdir()`). Both monolithic `<Lib>.kicad_sym` files (KiCad ≤9,
and the project's own `mini-xt.kicad_sym`) and KiCad 10's sharded
`<Lib>.kicad_symdir/` per-symbol directories are supported
(`mxsch.lib_source()`).

```sh
python3 hardware/tools/build.py                # regenerate motherboard: all sheets + root, ERC + netlist
python3 hardware/tools/validate_sheet.py <name>  # build + ERC ONE sheet in isolation (fast loop)
python3 hardware/tools/pins.py <Lib:Name>      # list a symbol's pins (e.g. mini-xt:V20, 74xx:74HCT573)
python3 hardware/tools/pins.py -s <substr>     # search symbol names
python3 hardware/tools/bom_cost.py             # per-sheet component-cost breakdown (prices cached in tools/lcsc_prices.json)
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
- **SMD construction**: 0603 passives, SOIC/TSSOP logic. Through-hole is
  reserved for connectors, headers, jumpers — and the socketed parts below.
  **One large board** (>100×100 mm JLC tier, since the 2026-07-14 3.3V
  single-board redesign) — there are no more per-subsystem PCBs or inter-board
  60-pin daisy-chain headers on the motherboard; sheets stay separate
  *schematic* sheets only.
- **Sockets, installed by the fab**, are now down to the **V20 only**
  (DIP-40, the board's one vintage/irreplaceable/5 V chip) plus female headers
  for the Core2350B/Pico modules. (The AS6C4008 SRAM sockets and the DS12C887
  socket are gone with those parts, §RAM/RTC below; the COM UARTs are now
  soldered, not socketed.) For the V20 and the module headers the
  `LCSC Part Num` is the SOCKET.
- **External cards attach via the buffered expansion port** (`sidecar` sheet,
  50-pin 2×25 header — swapped from 60-pin 2026-07-14; 50-way IDC ribbons are
  much easier to source). The standalone dev cards (card_video, card_isatest)
  and `build_cards()` were deleted the same day: the long-term plan is an
  **ISA backplane expansion board** driven from this port, which re-creates
  locally anything the 50-pin header dropped (OSC, REFRESH#) for real period
  cards. Git history/tags hold the last card versions.
- **Voltage domains matter for substitutions**: 74HCT reads 3.3 V inputs at
  5 V; plain 74HC does NOT (Vih ≈ 3.5 V) and is only used where every input
  is 5 V-driven or the part itself runs at 3.3 V. The board is now 3.3V almost
  everywhere; the remaining 5 V presences are: the **V20**; `cpu_core` **U10**
  (74HCT32 strobe combiner, reads the raw 5 V V20 strobes); `cpu_core` **U13**
  (74HCT04 — V20 CLK buffer, and now also the READY/HOLD 5 V re-buffers);
  the fused **+5V_ISA** expansion-port feed; and the **audio MCP6002**
  op-amp (analog +5 V). The MAX3241 RS-232 transceivers are now genuinely 3.3 V.
  (The RTL8019AS NIC island was removed 2026-07-14 — tag `full-board-with-nic`.)
  When JLC
  stock forces an HC-grade part into a 3.3 V-driven position, buffer the
  input through a spare HCT gate, or use LVC-grade if fmax margin is tight
  (the clock dividers needed this — plain HC fails its 3.3V fmax spec at
  14.318 MHz). `hardware/notes/jlcpcb-sourcing.md` records all current
  substitutions, the socket policy, and the parts that must be sourced
  elsewhere (VGA DE15, the V20 itself; the UART is back
  at JLC as the TL16C550CPFBR, C882798, but thin — verify stock).
- **RAM is one IS62WV51216BLL-55TLI** (512K×16, 3.3V) wired 1M×8 via the
  byte-lane trick (both 8-bit halves tied to D0-7, A0 selects the lane) —
  not two discrete 8-bit SRAMs.
- **COM ports are TL16C550CPFBR** (TQFP-48, 3.3V, soldered directly — no
  socket; thin JLC stock, C882798 — verify before ordering).
- **RTC is emulated in the Bus MCU** (ports 0x70/0x71, like PIC/PIT); there
  is no on-board `rtc` ISA sheet. Battery-backed timekeeping is a PCF8563
  I2C RTC + CR2032 coin cell on the Supervisor, synced over the UART link.
- Custom-symbol pin numbers are verified against JLCPCB/EasyEDA data (the
  MAX3241 was wrong before 2026-07-03 — do the same check before trusting
  any new hand-authored symbol).

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
- **Isolation guideline** (downgraded from a hard rule by the 2026-07-14 3.3V
  redesign — the whole internal bus is one 3.3V net now, so this is firmware/
  architectural discipline, not an electrically-enforced boundary): soft-card
  sheets (video, com_port, parallel, storage, sidecar, audio, picogus,
  card_*) should still use *only* ISA signals + power, so they stay
  liftable to a standalone ISA card. Private nets (`PRIV_*` in mxbus: HOLD/HLDA,
  UART link, counter strobes, SPEED_SEL, Y5) remain motherboard-only by
  convention — avoid leaking one into a soft card, but this is a guideline to
  log a question against, not a build-breaking violation. **Standing pattern
  (2026-07-14):** com_port/parallel/storage take `mxbus.PRIV_CS` chip selects
  from, and send `mxbus.PRIV_IRQREQ` IRQ requests to, the central
  `addr_decode` sheet (which also owns the 2×5
  disable-jumper block JP1 — positions 1-5 = COM1/COM2/LPT/IDE/VID,
  written JP1.n, one fixed 2×5 header part — incl. the video
  `mxbus.PRIV_DIS` level; base addresses are hardwired). Shared logic factored out, NOT an isolation break — the
  nets are functionally equivalent to the gates they replaced, and a
  standalone-card wrapper simply re-adds decode + IRQ driver the same way it
  adds the edge connector (`hardware/notes/questions-addr_decode.md`). (There is no `rtc`
  sheet any more — the RTC is emulated in the Bus MCU + Supervisor, see above.)
- Place on the 2.54 mm grid; ~40–60 mm part spacing; one net = one name.
- When the design under-specifies something, do **not** stop: make a
  best-guess decision, log it in `hardware/notes/questions-<sheet>.md`
  (question / why / options / pick), and proceed.
- Custom symbols live in `hardware/mini-xt.kicad_sym` (`mini-xt:` prefix): V20,
  MAX3241, IS62WV51216, TL16C550PT, PCF8563, Core2350B, Pico, and
  flat single-body 74xx glue (KiCad's stock multi-unit 74xx symbols don't work
  with the generator). New flat symbols are generated via `tools/gensym.py`.
  (DS12C887 was removed from `gensym.py` 2026-07-14 — the RTC is emulated now;
  the RTL8019AS/AT93C46/RJ45/magnetics symbols went with the NIC the same day.)

## Validation expectations

`validate_sheet.py <name>` must report **zero**: `endpoint_off_grid`,
`unconnected_wire_endpoint`, `multiple_net_names`, and "Failed to load".

Expected/ignorable at this fidelity (interface-focused schematic, not a
manufacturable board): large counts of `pin_not_connected`, `pin_not_driven`,
`label_dangling`, `pin_to_pin` (shared bus without modeled tri-state), and
`lib_symbol_issues` from the CLI. Don't try to drive these to zero, and don't
report them as findings.

**The full-project ERC report (`hardware/erc.rpt`) is ZERO errors / zero
warnings as of 2026-07-14 and must stay there** — fix new violations rather
than rationalizing them (PWR_FLAG for passive-fed rails, retire genuinely
undrivable nets, etc.). The expected-noise list above applies only to
single-sheet `validate_sheet.py` runs, where hierarchical pins legitimately
dangle.

The netlist (`hardware/mini-xt.net`) is the ground truth for connectivity —
after wiring changes, verify the affected net spans the sheets it should
(grep for the net name and check its node list).

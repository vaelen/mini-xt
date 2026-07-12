# mini-xt sheet authoring guide

You are implementing **one** KiCad hierarchical sub-sheet for the mini-xt
XT-class MCU-SBC, by writing a Python builder in `hardware/sheets/<name>.py`.
The build harness turns it into a valid `.kicad_sch`. Read this whole file first,
then study `hardware/sheets/cpu_core.py` — it is the worked reference example.

## The design

The full design is `docs/xt-mcu-sbc-design.md`. Read the sections relevant to
your sheet. The organizing idea: the **buffered 8-bit XT/ISA bus is the
integration contract**; soft cards talk only standard ISA signals, motherboard
nodes may use private side channels. Your sheet exposes its interface as
hierarchical pins so the isolation is visible.

## How a sheet module looks

```python
import mxbus
from mxbus import pin

NAME  = "rtc"
TITLE = "Real-time clock -- DS12C887"
PINS  = [ ... list of mxbus.pin("NETNAME", "direction") ... ]   # the interface

def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))   # declares the hier pins
    U1 = sch.place("mini-xt:DS12C887", "U1", at=(101.6, 101.6))
    # ... place parts, wire them ...
```

`PINS` is the sheet's interface (becomes the sheet symbol's pins at the root, and
ties to identically-named pins on other sheets). `emit_interface` drops one
hierarchical label per pin. You then wire component pins to those nets **by
name** with local labels.

## The connectivity model (IMPORTANT)

Connectivity is **by net name**, never by drawing wires between far-apart pins.
The one call you use constantly:

```python
sch.net(comp, pin, "NETNAME", kind="label", dx=2.54, dy=0)
```

This stubs a short wire off `comp`'s pin `pin` and attaches a label "NETNAME".
Any other pin labeled "NETNAME" on this sheet joins the same net. Use:
- `kind="label"` for internal nets AND for interface signals (the matching name
  in `emit_interface` makes it cross-sheet). This is what you want ~always.
- `dx`/`dy` choose stub direction: `dx=-2.54` left, `dx=2.54` right (default),
  `dy=-2.54` up, `dy=2.54` down. Pick a direction that doesn't overlap the body.

`pin` may be the pin **number** ("13") or its **name** ("AD0", "~{IRQ}").
Use `python3 tools/pins.py <Lib:Name>` to list a symbol's pins.

Power: `sch.net(c, "VCC", "+5V", kind="label", dx=0, dy=-2.54)` and likewise
"+3V3"/"GND". Power nets are global; just label them.

Unused pins: `sch.no_connect(comp.pin_xy("PINNAME"))`.
Free text: `sch.text("note", (x, y))`.

## Rules that keep ERC clean

1. **Place every component on the 2.54 mm grid** (coords like 101.6, 152.4,
   76.2 ...). The harness snaps to 1.27 mm but stay on 2.54 to be safe.
2. **One net = one name.** Do not put two different labels on the same pin.
3. Active-low signals use overbar syntax: `"~{MEMR}"`, `"~{IOR}"`, `"~{CS}"`.
   A slash in a name is written literally: `"IO/~{M}"`, `"R/~{W}"`.
4. Use the **canonical names from `mxbus`** for every shared signal (see below).
   A typo'd name silently fails to connect across sheets.
5. Lay parts out with ~40-60 mm spacing so labels don't collide. A3 sheet is
   ~420x297 mm.

## Canonical signal names (from `mxbus`, use these EXACTLY)

- Address: `mxbus.ADDR` = `A0`..`A19`   (bus group `A[0..19]`)
- Data:    `mxbus.DATA` = `D0`..`D7`
- IRQ:     `mxbus.IRQ`  = `IRQ2`..`IRQ15`
- Control: `~{MEMR} ~{MEMW} ~{IOR} ~{IOW} BALE AEN IOCHRDY ~{IOCHCK}
  RESET_DRV CLK OSC TC DRQ1 DRQ2 DRQ3 ~{DACK1} ~{DACK2} ~{DACK3}`
- Power:   `+5V +3V3 GND`
- Private (motherboard-only): `mxbus.PRIV_CPU`, `PRIV_COUNTER`, `PRIV_LINK`
  (`LINK_B2S`,`LINK_S2B`), `PRIV_SUPER`, `PRIV_SPEED` (`SPEED_SEL`).

Only declare in `PINS` the signals your sheet actually uses. A soft card (video,
com, lpt, rtc, storage, sidecar, audio, picogus, network) must use **only ISA
signals + power** —
no private names (that would be an isolation leak; if you think you need one,
log a question instead).

## Finding symbols

`python3 tools/pins.py -s <substr>` searches names; `python3 tools/pins.py
<Lib:Name>` lists pins. Custom parts live in `mini-xt:` (V20, MAX3241, DS12C887,
and flat glue 74HC573/245/138/00/02/04/08/32/74/125/157/163/165/244/374/4017).
Standard KiCad libs available: Device, power, Connector, Connector_Generic, 74xx,
Interface_UART (16550), Interface_USB (CH224K, USB_C), Interface_LineDriver,
Memory_RAM (AS6C4008-55PCN), MCU_RaspberryPi (RP2040, RP2350B), Oscillator,
Regulator_Switching/Linear, Power_Supervisor, Audio (PCM5102), Amplifier_Operational,
Connector (HDMI_A, DE9_*, DB25_*, USB_C_Receptacle). If a part is missing, pick the
closest standard symbol and log a question.

## Validate your work (run repeatedly)

```
cd /home/andrew/repos/mini-xt
python3 hardware/tools/validate_sheet.py <name>
```

Must be **zero**: `endpoint_off_grid`, `unconnected_wire_endpoint`,
`multiple_net_names`, and any "Failed to load". EXPECTED (ignore): big counts of
`pin_not_connected` / `pin_not_driven` / `label_dangling` (hierarchical pins and
unused chip pins look unconnected in isolation — they resolve at the root), and
`lib_symbol_issues` (just "lib not in config" for the CLI).

## Logging questions

When the design under-specifies something, do NOT stop. Write your best-guess
decision to `hardware/notes/questions-<name>.md` (question, why, options,
your pick) and proceed with your pick. One file per sheet (avoids write races).

## Scope / fidelity

Interface-focused: place the real ICs and the key supporting parts, wire the
important nets and every interface signal, add representative decoupling. You do
NOT need every passive or perfect pin-level completeness — clarity of the
module's interface and internal structure is the goal. Aim for ~10-30 components.

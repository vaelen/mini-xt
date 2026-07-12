# NE2000 Network Card (`network` sheet) — Design

**Date:** 2026-07-12
**Status:** Approved design; ready for implementation planning
**Scope:** A new motherboard soft-card sheet transcribing Manawyrm's ISA8019
(RTL8019AS, NE2000-compatible, CERN-open-hardware; source at `../ISA8019`) into
the mini-xt generator, with all configuration jumpers replaced by hardwired
straps and the boot ROM deleted. Hardware only; the Bus MCU firmware note in
§6 is informational.

---

## 1. Purpose & role

Add 10BaseT Ethernet as another ISA soft card. Like every soft card it uses
**only ISA signals + power** (isolation rule holds — no private nets). It is
the simplest soft-card sheet in the design: the RTL8019AS is a single-chip
5 V NE2000 that needs no MCU, no level shifting, and no glue beyond one
74HCT125 for the disable jumper.

NE2000 compatibility means every DOS packet driver, mTCP, and any period OS
just works. The upstream card is a proven, JLCPCB-assembled design; the
analog front end is transcribed verbatim, not redesigned.

### Non-goals

- No boot ROM (PXE/RPL): the flash + DIP-32 socket and its straps are
  deleted. The Bus MCU already shadow-loads option ROMs (XTIDE at 0xC8000);
  if network boot code is ever wanted it loads the same way.
- No PNP mode, no jumper-configurable resources, no AUI/10Base2 — hardwired
  (§3).
- No standalone `card_*` variant for now; this is a motherboard sheet like
  `picogus`. A sidecar NE2000 can be a real ISA8019.

## 2. Interface (`PINS`)

| Signal                          | Dir    | Notes                                          |
|---------------------------------|--------|------------------------------------------------|
| `A0..A19`                       | input  | full SA bus (CMOS inputs must not float)       |
| `D0..D7`                        | bidir  | SD8–15 no-connect (8-bit slot)                 |
| `~{IOR}` `~{IOW}`               | input  | command strobes                                |
| `~{MEMR}` `~{MEMW}`             | input  | → SMEMRB/SMEMWB (inert with boot ROM disabled) |
| `AEN`                           | input  | via disable gate (§4)                          |
| `RESET_DRV`                     | input  | → RSTDRV                                       |
| `IOCHRDY`                       | output | RTL8019AS wait-state request                   |
| `IRQ2`                          | output | via 74HCT125 tri-state gate (§4)               |

## 3. Hardwired configuration (replaces jumpers J4–J9)

All straps are 10 k to +5V or GND, sampled by the RTL8019AS at reset.
**Every strap-pin polarity must be re-verified against the RTL8019AS
datasheet during implementation** (the config pins 64–85 are shared
BD/EE/BS/IOS/IRQS functions; same rule as any hand-authored symbol).

| Function   | Strap                 | Value hardwired                                  |
|------------|-----------------------|--------------------------------------------------|
| Mode       | JP = 1                | jumper (strap) mode, not jumperless/PNP           |
| PNP        | PNP = 0               | PNP disabled                                      |
| I/O base   | IOS[3:0] = 0010       | **0x340–0x35F** (0x300/0x320 = XT-IDE, 0x360 hits LPT 0x378, 0x2E0 hits COM window) |
| IRQ        | IRQS[2:0] = 000       | INT0 pin → **IRQ2** (delivered as IRQ9 by the soft PIC's AT redirect) |
| Medium     | PL[1:0] = 01          | 10BaseT with link test                            |
| Boot ROM   | BS[4:0] = 00000       | disabled                                          |
| Slot width | IOCS16B: 27 k to GND  | 8-bit slot (SLOT16 strap, as upstream)            |
| AUI        | AUI: 10 k to GND      | twisted pair                                      |

## 4. Disable jumper (JP1 — the only jumper)

2-pin header, same idiom as LPT's JP2: **closed = enabled**, open = 10 k
pulls `~{NET_EN}` high. One 74HCT125:

- **Gate 1:** INT0 → IRQ2, OE = `~{NET_EN}`. Open jumper tri-states the
  IRQ line so a sidecar card can drive IRQ2 (the RTL8019AS INT pin is
  totem-pole and would otherwise park the line low even when idle).
- **Gate 2:** bus AEN → chip AEN, OE = `~{NET_EN}`, 10 k pull-up on the
  chip side. Open jumper floats the gate high → chip sees AEN=1 → ignores
  every I/O cycle.
- Gates 3/4: inputs grounded, outputs no-connect.

The COM ports and LPT already free their IRQs when disabled (16C550 OUT2
convention / LPT IRQ_EN through their own '125 gates) — verified, no
changes needed there.

## 5. Transcribed verbatim from ISA8019 Rev A

- RTL8019AS core: 20 MHz crystal + 2×20 pF + 1 M feedback, 100 n decoupling
  per rail pin + 47 µ bulk.
- **93C46 EEPROM kept** (SOIC-8, JLC-assembled, no socket): the chip reads
  its MAC from it even in strap mode. Ships blank — program once with
  `RSET8019.EXE`/`pg8019` from DOS (documented in the questions file).
- Ethernet front end: 13F-39MNL magnetics, 200 Ω RX termination, 1 nF
  center-tap caps, ferrite-bead chassis ground, RJ45 with link/activity
  LEDs via 2×1 k from +5V (LED0/LED1).
- Unused: INT1–7, SD8–15, LED2/LEDBNC no-connect.

## 6. Firmware note (informational)

The Bus MCU needs no NIC-specific support: the card is a plain I/O device
at 0x340 on physical IRQ2 (the '165 collector already samples IRQ2). DOS
drivers configure themselves for 0x340/IRQ2(9). No option ROM is loaded.

## 7. Sourcing (parts.py + jlcpcb-sourcing.md)

| Part               | LCSC       | Note                                              |
|--------------------|------------|---------------------------------------------------|
| RTL8019AS          | C22465363  | ~$19.5, 202 in stock; C10016 is ~$11 but 4 left — record both, bind whichever is in stock at order time |
| 13F-39MNL          | C115949    | as upstream                                       |
| AT93C46DN          | C6499      | as upstream                                       |
| RJ45 w/ LEDs       | C386757    | upstream's C133529 is EOL; same-vendor successor (Ckmtw, right-angle, shielded, LEDs). New `mini-xt:` symbol, pin numbers verified against EasyEDA data |
| 74HCT125, R, C, FB | (existing) | already in parts.py                               |

## 8. Files touched

- `hardware/sheets/network.py` — new sheet
- `hardware/tools/build.py` — root wiring
- `hardware/tools/parts.py` — new bindings (§7)
- `hardware/mini-xt.kicad_sym` — RJ45-with-LEDs symbol (via `gensym.py`)
- `hardware/notes/questions-network.md` — decisions log (MAC programming
  procedure, strap-polarity verification results)
- `hardware/notes/jlcpcb-sourcing.md` — RTL8019AS stock situation
- `docs/irq-io-map.md` — IRQ2 → NIC (the future-COM4-on-IRQ2 reservation
  is dropped; a future COM4 must borrow a freed COM/LPT IRQ instead);
  I/O row 0x340–0x35F; JP1 disable note
- `docs/xt-mcu-sbc-design.md` — add the network card to the soft-card list

## 9. Validation

`validate_sheet.py network` zero structural errors; full `build.py` ERC +
netlist; grep the netlist to confirm IRQ2, IOCHRDY, and the D-bus span the
sheets they should.

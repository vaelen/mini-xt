# ISA Card Tester (`card_isatest`) — Design

**Date:** 2026-07-01
**Status:** Approved design; ready for implementation planning
**Scope:** A standalone development/diagnostic board that acts as an ISA **host**
(bus master) to exercise a device-under-test (DUT) ISA card, driven entirely over
USB serial. Interface-focused KiCad schematic in the same style as the rest of the
repo (real symbols, every inter-block signal visible); **firmware is out of scope**.

---

## 1. Purpose & role

`card_isatest` is a small board whose centerpiece is a **stock Raspberry Pi Pico
module** (RP2040; a Pico 2 / RP2350A is pin-compatible and may be substituted). It
presents an ISA bus to a DUT and drives every bus signal itself, so it can:

- read/write a card's memory and I/O registers,
- generate the bus clocks (CLK, OSC), RESET_DRV, and REFRESH#,
- emulate DMA cycles (AEN / DACK / TC),
- sense the card's responses (data, IOCHRDY wait states, IOCHCK#, IRQ, DRQ),
- measure and report the actual bus clock frequency,

and report everything to the user over the Pico's **USB serial** — no GPIO is spent
on user interaction, programming, or display.

The tester is the **motherboard side** of the bus: it is always the bus master. This
is the opposite role from the mini-xt soft-cards (which are bus *slaves*). It is a
**complete standalone board** — the bus and power arrive through its own connectors,
so the schematic has no parent hierarchical interface (`PINS = []`), exactly like the
existing `card_*` soft-card PCBs.

### Non-goals

- No V20/CPU, no companion MCU — the single Pico is the whole brain.
- No ±12 V / −5 V analog rails (consistent with the rest of mini-xt, design S13).
- Not cycle-*accurate* by default: cycles run at the tester's own (slower) pace.
  Optional CLK-synchronous timing is available via `CLK_SENSE` (§7).
- No support for a **bus-mastering DUT** (a card that drives the address bus during
  its own DMA). Address is output-only. Adding readback is noted as future work (§13).
- Firmware is out of scope for this spec.

---

## 2. Key architectural decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Stock Pico module (RP2040; Pico 2 pin-compatible) | "Standard" module; ~26 GPIO forces the pin-saving shift-register approach the user asked for |
| D2 | Data bus D0–D7 driven **directly** by GPIO | Simplest & fastest data path (one masked SIO store/load per byte); fits the pin budget; deviates from "shift registers for data" intentionally, agreed after pin analysis |
| D3 | Address A0–A19 driven by a **shift register chain** (output-only) | 20 lines can't fit on direct GPIO; the host always drives the address (see §5) |
| D4 | Control outputs on the **same OUT chain**, but **split into a second latch** | Address updates (frequent) shift 24 bits without disturbing the static control byte; +1 pin buys ~25% shorter address-change cycles |
| D5 | Inputs (IRQ/DRQ/IOCHCK#) on a **unified IN chain** (2× `74HC165`), full-duplex with the OUT chain (shared `SRCLK`) | The IN chain is off the hot path (sampled occasionally), so it needs no split |
| D6 | All bus signals buffered 3.3↔5 V by **`74LVC245A`** transceivers | Same part/pattern as the other mini-xt cards; keeps everything the Pico touches at 3.3 V |
| D7 | `BUF_EN` (direct GPIO) gates **all** transceiver `OE`; defaults disabled via pull-up | Isolates the DUT until firmware initializes the bus to a safe idle state |
| D8 | Clock tree: **14.318 MHz can oscillator** + ÷2/÷3 divider + mux (default), with a **PIO override** input | Accurate OSC (matters for CGA color / timing-sensitive DUTs), mirrors `cpu_core`; PIO path allows firmware clock sweeps |
| D9 | `CLK_SENSE`: bus CLK routed back to a **direct** Pico input | Enables PIO edge-sync for cycle-accurate timing **and** frequency measurement/reporting; a shift register can't do either |
| D10 | Power: **USB 5 V** for logic + a **switchable, protected external barrel jack** for the bus/DUT | USB-independent current for power-hungry DUTs; small tests still run on USB alone |
| D11 | Two DUT connectors: a **real 8-bit ISA card-edge slot** (true pinout) **and** the **60-pin `isa_conn` sidecar header** | Test either a real ISA card or a mini-xt soft-card; both carry the same bus nets |

---

## 3. Block diagram

```
 USB (serial + power) ─ Pico (3V3) ─┬─ SPI/PIO ─▶ OUT chain: 3×74HC595 (A0-A19)
                                    │                       + 1×74HC595 (AEN,
                                    │              RESET_DRV, TC, DACK1-3, BALE)
                                    │              two latches: RCLK_ADDR / RCLK_CTRL
                                    │            ◀─ IN chain: 2×74HC165 ◀─ IRQ2-8,
                                    │                       DRQ1-3, IOCHCK#
                                    ├─ direct: D0-7, DATADIR, MEMR#/MEMW#/IOR#/IOW#,
                                    │          IOCHRDY, REFRESH#, BUF_EN, PIO_CLK,
                                    │          CLK_SENSE
                                    │
                          8× 74LVC245A (3V3◀▶5V, OE=BUF_EN) ──┬── ISA card-edge SLOT
                                    │                          └── 60-pin sidecar header
   14.318 can osc ─▶ ÷2 (74HCT74) ─┐                              (isa_conn)
                  └▶ ÷3 (74HCT163) ─┴ mux 74HCT157 ─ buf 74HCT04 ─▶ bus CLK
                           PIO_CLK ──┘   (SPEED_SEL, CLK_SRC selects)     └▶ CLK_SENSE
                            OSC ───────────────────────────────────────▶ bus OSC (14.318)
   ext 5V barrel jack ─ OR/protect ─▶ bus +5V ─ FET switch (DUT power enable)
```

---

## 4. Functional blocks & bill of materials (logic)

| Block            | Parts                                             | Role |
|------------------|---------------------------------------------------|------|
| Brain            | 1× stock Pico (RP2040; Pico 2 pin-compatible)     | Cycle engine, USB-serial console, PIO shift + PIO clock/measure |
| Bus buffers      | 8× `74LVC245A` @ 3V3 (`OE` = `BUF_EN`)            | data ×1, address ×3, control-out ×2, control-in ×2 |
| Address+ctrl OUT | 4× `74HC595` @ 3V3, two latches                    | A0–A19 (3 chips) + control byte (1 chip): AEN, RESET_DRV, TC, DACK1–3, BALE |
| Status IN        | 2× `74HC165` @ 3V3                                  | IRQ2–8, DRQ1–3, IOCHCK# (full-duplex with OUT, shared `SRCLK`) |
| Clock tree       | 14.318 MHz can osc + `74HCT74` (÷2) + `74HCT163` (÷3) + `74HCT157` (mux) + `74HCT04` (buffer) @ 5V | OSC (14.318) + CLK (7.16 / 4.77 via `SPEED_SEL`); `PIO_CLK` override via `CLK_SRC` |
| Power            | USB 5 V (logic) + ext barrel jack → OR/reverse-protect + P-FET switch | Bus/DUT 5 V, USB-independent; `DUT_PWR_EN` gate |
| DUT connectors   | 8-bit ISA card-edge socket + 60-pin `isa_conn` header | Real card or mini-xt soft-card |
| Idle network     | Pull-up on IOCHRDY; pull-downs on IRQ/DRQ; pull-up on `BUF_EN` `OE` line; pull on `DUT_PWR_EN` | Define safe bus/board idle (tester = motherboard) |
| Decoupling       | 100 nF per IC + bulk on 3V3 and 5 V rails           | Standard |

Notes:
- The shift registers run at **3.3 V** (on the `MA*`/`MD*` domain), so nothing the
  Pico touches sees 5 V. The `74LVC245A`s do all 3.3↔5 V translation at the bus edge.
- The clock tree runs at **5 V** (like `cpu_core`); CLK/OSC drive the bus directly at
  5 V. `CLK_SENSE` is brought back down to 3.3 V through one spare `74LVC245A` bit.
  `PIO_CLK` (3.3 V) drives the 5 V `74HCT157` input directly (HCT V_IH ≈ 2.0 V).

---

## 5. Bus direction model

The tester is always the bus master. There is **no combined R/W line on ISA** — the
four active-low command strobes carry both direction and space:

| Strobe        | Meaning       |
|---------------|---------------|
| `~{MEMR}`     | memory read   |
| `~{MEMW}`     | memory write  |
| `~{IOR}`      | I/O read      |
| `~{IOW}`      | I/O write     |

Because the tester *asserts* the strobe, its firmware already knows the direction, so
it sets the data-buffer direction (`DATADIR`) itself — it never senses an R/W line.

| Signal group | Direction | Why |
|--------------|-----------|-----|
| Address A0–A19 | host → DUT (output only) | The host always names the location, for both reads and writes. The card never drives address (except a bus-mastering DUT, out of scope). |
| Data D0–D7 | bidirectional | Read: card drives → tester. Write: tester drives → card. Handled by direct GPIO + `DATADIR` + `74LVC245A` direction flip. |
| Command strobes, BALE, AEN, RESET_DRV, TC, DACK, REFRESH# | host → DUT | Host-driven control. |
| IOCHRDY, IOCHCK#, IRQ, DRQ | DUT → host | Card responses / status. |

---

## 6. Shift-register subsystem

### 6.1 OUT chain — split (address latch + control latch)

A single daisy chain of 4× `74HC595`, address upstream (fed by `SER`), control byte
downstream, with an independent storage latch on each segment:

```
SER ─▶ [3×74HC595  A0-A19] ─QH'─▶ [1×74HC595  ctrl] ─(unused)
          ▲ RCLK_ADDR                 ▲ RCLK_CTRL
        SRCLK ─────────────────────────┘  (shared)
```

Control byte (1× `74HC595`): AEN, RESET_DRV, TC, `~{DACK1}`, `~{DACK2}`, `~{DACK3}`,
BALE (7 bits; 1 spare output available for a status LED or `DUT_PWR_EN`).

- **Address-only update (hot path):** shift **24 bits**, pulse `RCLK_ADDR`. Bits
  spilling into the control shift stage are harmless — its **outputs** don't change
  because `RCLK_CTRL` is not pulsed.
- **Control update (rare):** shift control byte then the 24 address bits (32 total),
  pulse **both** latches.

The control byte changes only at session boundaries (RESET_DRV) or DMA-operation
boundaries (AEN/DACK/TC together); BALE is held static. It is never touched during a
programmed-I/O or memory hot loop — so the split delivers its ~25% saving exactly on
the recurring inner loop.

### 6.2 IN chain — unified

2× `74HC165` PISO, sharing `SRCLK` with the OUT chain (full-duplex exchange):
IRQ2–8, DRQ1–3, IOCHCK# (11 bits; spare inputs available). Read = pulse `PL` (parallel
load), then clock out `QH`. The IN chain is off the hot path (sampled after triggering
an interrupt, during DMA, or on error checks), so no split is needed.

### 6.3 Shift engine

Drive `SER`/`SRCLK` from an SPI or PIO peripheral so a full 32-bit OUT load is a ~1 µs
burst rather than a bit-banged loop. Because OUT and IN share `SRCLK`, a single
PIO/SPI "exchange" both loads outputs and captures inputs.

---

## 7. Clock subsystem

Mirrors the `cpu_core` clock tree:

- `OSC` = **14.31818 MHz can oscillator** → bus OSC pin directly (5 V), and → the divider.
- CLK derived from OSC by **÷2 (`74HCT74`) → 7.16 MHz** and **÷3 (`74HCT163` preset-to-3)
  → ~4.77 MHz**, selected by `74HCT157` mux via **`SPEED_SEL`**, buffered by `74HCT04`
  to the bus CLK pin.
- **PIO override:** a second mux stage (or the spare `74HCT157` half) selects between the
  hardware CLK and **`PIO_CLK`** (Pico-generated) via **`CLK_SRC`**, so firmware can
  sweep/margin the clock. `SPEED_SEL` and `CLK_SRC` are slow selects → driven from the
  OUT chain spare / a spare GPIO.
- **`CLK_SENSE`** (direct Pico input, 5 V→3.3 V through one `74LVC245A` bit, tapped
  **after** the mux): a PIO state machine can `WAIT` on a CLK edge (cycle-accurate
  timing / wait-state counting) and **count edges over an interval to measure and report
  the actual bus frequency**. Works whether the source is the can osc or `PIO_CLK`.

The bus CLK/OSC free-run in hardware, decoupled from firmware. The tester paces bus
cycles at its own wall-clock speed via the (direct) command strobes and `IOCHRDY`
handshake; it never has to complete a transfer within one CLK period.

---

## 8. Power subsystem

- **USB 5 V (Pico VBUS)** powers the Pico and all logic (shift registers, transceivers,
  clock tree). USB serial is the user link — no GPIO cost.
- **External 5 V barrel jack** feeds the ISA bus/DUT through reverse-polarity and
  OR-ing protection (so USB and the jack don't back-feed each other) and a **P-FET
  switch** gated by `DUT_PWR_EN`, so DUT power is software-controllable and not limited
  by USB current.
- 3.3 V for the shift registers / transceivers comes from the Pico module's onboard
  regulator (3V3 OUT), consistent with how mini-xt modules self-power their local logic.

---

## 9. Power-up safe state

- `BUF_EN` line has a **pull-up** → all `74LVC245A`s default **disabled** (bus isolated)
  at power-up, before firmware runs. A `74HC595`'s shift contents are random at reset;
  gating at the transceiver boundary (not the 595) guarantees the DUT sees a clean bus.
- Firmware sequence at start: shift a **safe idle word** (AEN=0, RESET_DRV per intent,
  `~{DACK*}`=1, BALE static) and latch it → then assert `BUF_EN` to connect the bus.
- `DUT_PWR_EN` defaults **off** (DUT unpowered) until firmware enables it.
- Idle resistors define the bus as a motherboard would: pull-up on IOCHRDY (ready),
  pull-downs on IRQ/DRQ (inactive).

---

## 10. Pin budget (24 of ~26 GPIO; 2 spare)

| Function                                   | GPIO |
|--------------------------------------------|------|
| Data D0–D7 (direct, SIO byte)              |  8   |
| `DATADIR`                                  |  1   |
| `~{MEMR}` / `~{MEMW}` / `~{IOR}` / `~{IOW}` |  4   |
| IOCHRDY sense (direct, crisp wait states)  |  1   |
| REFRESH# (PIO/timer)                       |  1   |
| OUT chain `SER` / `SRCLK` / `RCLK_ADDR` / `RCLK_CTRL` | 4 |
| IN chain `PL` / `QH` (SRCLK shared)        |  2   |
| `BUF_EN`                                   |  1   |
| `PIO_CLK` (fallback clock out)             |  1   |
| `CLK_SENSE` (direct in: edge-sync + freq)  |  1   |
| **Total**                                  | **24** |

- BALE, AEN, RESET_DRV, TC, DACK1–3 ride the OUT control latch (0 GPIO).
- IOCHCK# rides the IN chain (0 GPIO).
- `SPEED_SEL` / `CLK_SRC` / `DUT_PWR_EN` use OUT-chain spare outputs (0 GPIO), or the
  2 spare GPIO.
- The onboard Pico LED (GP25) is available if not otherwise needed.

---

## 11. Firmware operation model (informative — not implemented here)

Illustrative cycle sequencing the hardware is designed to support:

```
# Programmed I/O / memory access (hot loop):
if address changed:  shift 24b address -> RCLK_ADDR       # ~0.8us, SPI/PIO
set DATADIR; if write: drive D0-7 (SIO)
pulse the direct command strobe (MEMR#/MEMW#/IOR#/IOW#)
poll IOCHRDY (direct); extend strobe while low            # wait states
if read: latch D0-7 (SIO); deassert strobe

# DMA emulation (occasional):
shift control {AEN=1, ~DACKn=0} + address -> both latches
per transfer: shift 24b address -> RCLK_ADDR; pulse strobe
on last transfer: shift control {…, TC=1} -> RCLK_CTRL
teardown: control {AEN=0, ~DACK*=1}

# Interrupt / status check (occasional):
pulse IN-chain PL; clock QH; inspect IRQ/DRQ/IOCHCK#

# Bus-speed report:
PIO counts CLK_SENSE edges over a known interval -> report MHz over USB serial
```

---

## 12. Deliverable & integration

Interface-focused schematic matching the repo:

- New `hardware/sheets/card_isatest.py` — a **standalone board** (`PINS = []`), placing:
  the Pico module, 8× `74LVC245A`, 4× `74HC595` (split OUT), 2× `74HC165` (IN), the clock
  tree, power/OR-ing + FET, idle/decoupling networks, the real ISA card-edge slot, and the
  60-pin `isa_conn` sidecar header.
- Register `card_isatest` in `CARD_SHEETS` in `hardware/tools/build.py`; it builds into
  `hardware/cards/` and runs ERC like the other cards.
- New symbols as needed: a Pico module (KiCad `MCU_Module:RaspberryPi_Pico` if suitable,
  else a `mini-xt:` symbol) and the ISA card-edge slot.
- New `hardware/sheets/isa_slot.py` (or an `isa_conn`-style map): the **true 62-pin
  8-bit ISA edge pinout** for the real slot — *not* the reclaimed `isa_conn` remap. The
  −5 V / ±12 V pins are left **NC** (or optional test points) so a stock 8-bit card sees
  a standard slot. Same bus net names, different physical pin map.
- The 60-pin sidecar header reuses `isa_conn.place_header` verbatim (soft-card compatible).
- New `hardware/notes/questions-isatest.md` recording per-sheet decisions/open items.
- Update `hardware/README.md` layout table.

Bus connectivity is by net name (mxbus contract), so both DUT connectors and the on-board
logic join the same bus rails automatically.

---

## 13. Open questions / future work

- **Bus-mastering DUT support:** to test a card that drives the address bus during its own
  DMA, add an input `74LVC245A` + a readback `74HC165` on the address lines and make the
  address transceivers direction-switchable. Out of scope now; the pin budget has only 1
  spare, so this would likely need a larger module (e.g. Pico-form RP2350B) or more shift
  logic.
- **Real ISA slot analog pins:** decide whether −5 V/±12 V edge pins are NC or brought to
  labeled test points/optional jumpers for the rare card that needs them.
- **16-bit ISA:** explicitly out of scope (8-bit XT bus only), matching the mini-xt sidecar.
- **Symbol sourcing:** confirm a suitable Pico module symbol and an ISA card-edge slot
  symbol (create `mini-xt:` symbols if the stock libraries don't fit).
- **PIO clock mux details:** exact second-stage mux wiring for `CLK_SRC` (spare `74HCT157`
  half vs. a small dedicated part).
```

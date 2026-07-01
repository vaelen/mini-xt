# ISA Card Tester (`card_isatest`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone Pico-based ISA host/bus-master test board (`card_isatest`) to the mini-xt KiCad generator, as an interface-focused schematic in the same style as the other cards.

**Architecture:** A stock Raspberry Pi Pico module drives the full 8-bit ISA bus through `74LVC245A` 3.3↔5 V transceivers. Address + slow control ride a split `74HC595` OUT chain; IRQ/DRQ/status ride a `74HC165` IN chain; data is direct GPIO. A 14.318 MHz can-oscillator clock tree (÷2/÷3 + PIO override) generates CLK/OSC. USB serial is the user link. A real 8-bit ISA card-edge slot and the 60-pin `isa_conn` sidecar header expose the bus to a DUT.

**Tech Stack:** Python schematic generator (`hardware/tools/mxsch.py`, `mxbus.py`, `isa_conn.py`, `gensym.py`), KiCad 9 symbols, `kicad-cli sch erc` validation.

## Global Constraints

- **Design spec:** `docs/superpowers/specs/2026-07-01-isa-test-card-design.md` — authoritative for all decisions.
- **Authoring rules:** follow `hardware/tools/SHEET_AUTHORING_GUIDE.md`. Place every component on the 2.54 mm grid. Connectivity is **by net name** via `sch.net(comp, pin, "NET", kind="label", dx=, dy=)`. One net = one name.
- **Canonical net names** (from `mxbus`, use EXACTLY): address `A0`..`A19`; data `D0`..`D7`; IRQ `IRQ2`..`IRQ15`; control `~{MEMR} ~{MEMW} ~{IOR} ~{IOW} BALE AEN IOCHRDY ~{IOCHCK} RESET_DRV CLK OSC TC DRQ1 DRQ2 DRQ3 ~{DACK1} ~{DACK2} ~{DACK3} ~{REFRESH}`; power `+5V +3V3 GND`. Active-low uses `~{...}`.
- **Internal (non-bus) net conventions:** Pico-side data `MD0..MD7`; shift-register address `MA0..MA19`; control-out (internal side of ctrl `'245`) `M_*`; sensed inputs (internal side of input `'245`) `*_S`.
- **Validation is the test.** `python3 hardware/tools/validate_sheet.py <name>` must report **zero** of: `endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`, any "Failed to load". EXPECTED/ignored: `pin_not_connected`, `pin_not_driven`, `label_dangling`, `lib_symbol_issues` (missing-lib note).
- **When validate reports `multiple_net_names` or `unconnected_wire_endpoint`:** two labels/stubs collided at one point — nudge the offending component's coordinate by ±2.54 mm and/or flip a stub `dx/dy` sign. This is the normal authoring loop; iterate until clean.
- **Commit** after each task with the exact `git add`/`git commit` shown.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- **Under-specified detail?** Do NOT stop. Record the question + your best-guess pick in `hardware/notes/questions-isatest.md` and proceed (Task 9 creates the file; append to it any time).

---

## File Structure

- **Create** `hardware/sheets/card_isatest.py` — the whole tester board (standalone card, `PINS=[]`). One `build(sch, lib)` grown across Tasks 2–8.
- **Modify** `hardware/tools/gensym.py` — add the `mini-xt:Pico` module symbol; add `pico` to the emitted library list.
- **Regenerate** `hardware/mini-xt.kicad_sym` (output of `gensym.py`).
- **Modify** `hardware/tools/build.py` — add `"card_isatest"` to `CARD_SHEETS`.
- **Create** `hardware/notes/questions-isatest.md` — per-sheet decisions/open items.
- **Modify** `hardware/README.md` — add `card_isatest` to the layout table.

**Reused symbols (no authoring needed):** `mini-xt:74LVC245A`, `74xx:74HC595`, `mini-xt:74HCT165`, `mini-xt:74HCT74`, `mini-xt:74HCT163`, `mini-xt:74HCT157`, `mini-xt:74HCT04`, `Oscillator:ACO-xxxMHz`, `Connector:Bus_ISA_8bit`, `Connector:Barrel_Jack`, `Device:D_Schottky`, `Device:Q_PMOS`, `Device:R`, `Device:C`. Sidecar via `isa_conn.place_header`.

---

### Task 1: Author the `mini-xt:Pico` module symbol

**Files:**
- Modify: `hardware/tools/gensym.py` (add symbol near the Core2350B block, ~line 231–252; extend the lib list at ~line 251)
- Regenerate: `hardware/mini-xt.kicad_sym`

**Interfaces:**
- Produces: `mini-xt:Pico` with pins `GP0`..`GP22`, `GP26`, `GP27`, `GP28` (bidirectional), `VBUS`/`VSYS` (power_in), `3V3` (power_out), `3V3_EN`/`RUN` (input), `ADC_VREF` (passive), `GND` (power_in). GPIO names are authoritative; pin numbers follow the physical 40-pin Pico pinout.

- [ ] **Step 1: Add the Pico symbol builder** — insert after the `core2350b = make_ic(...)` block in `hardware/tools/gensym.py`:

```python
# ---- Raspberry Pi Pico module (RP2040; Pico 2/RP2350A pin-compatible) ----
# Standard 40-pin castellated module. Exposes 26 usable GPIO (GP0-GP22, GP26-28;
# GP23/24/25 are module-internal) + power/control. GPIO NAMES are authoritative;
# pin NUMBERS follow the physical 40-pin Pico pinout (GND pins collapsed to two).
pico = make_ic(
    "Pico",
    left=[(str(n), "GP%d" % g, "bidirectional") for n, g in [
        (1, 0), (2, 1), (4, 2), (5, 3), (6, 4), (7, 5), (9, 6),
        (10, 7), (11, 8), (12, 9), (14, 10), (15, 11), (16, 12)]],
    right=[(str(n), "GP%d" % g, "bidirectional") for n, g in [
        (17, 13), (19, 14), (20, 15), (21, 16), (22, 17), (24, 18),
        (25, 19), (26, 20), (27, 21), (29, 22), (31, 26), (32, 27), (34, 28)]],
    top=[("40", "VBUS", "power_in"), ("39", "VSYS", "power_in"),
         ("37", "3V3_EN", "input")],
    bottom=[("3", "GND", "power_in"), ("38", "GND", "power_in"),
            ("36", "3V3", "power_out"), ("30", "RUN", "input"),
            ("35", "ADC_VREF", "passive")],
    ref="M",
    description="Raspberry Pi Pico module (RP2040; Pico 2/RP2350A pin-compatible): 26 usable GPIO, onboard 3V3 SMPS, USB",
    datasheet="https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf")
```

- [ ] **Step 2: Add `pico` to the emitted library list** — change the `lib = [...]` line (currently ending `..., core2350b] + glue_syms`):

```python
lib = ["kicad_symbol_lib", ["version", 20241209], ["generator", "mxsch"],
       ["generator_version", "9.0"], v20, max3241, ds12c887, core2350b, pico] + glue_syms
```

- [ ] **Step 3: Regenerate the symbol library**

Run: `cd /home/andrew/repos/mini-xt && python3 hardware/tools/gensym.py`
Expected: prints `wrote .../hardware/mini-xt.kicad_sym`

- [ ] **Step 4: Verify the symbol exists with the expected pins**

Run: `python3 hardware/tools/pins.py mini-xt:Pico`
Expected: lists `GP0`..`GP22`, `GP26`, `GP27`, `GP28`, `VBUS`, `VSYS`, `3V3`, `3V3_EN`, `RUN`, `ADC_VREF`, `GND`.

- [ ] **Step 5: Confirm existing sheets still generate** (gensym rewrites the whole lib)

Run: `python3 hardware/tools/validate_sheet.py cpu_core 2>&1 | tail -5`
Expected: histogram with zero `endpoint_off_grid` / `unconnected_wire_endpoint` / `multiple_net_names` (same as before this change).

- [ ] **Step 6: Commit**

```bash
git add hardware/tools/gensym.py hardware/mini-xt.kicad_sym
git commit -m "Add mini-xt:Pico module symbol for the ISA test card

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `card_isatest` skeleton — Pico, helpers, GPIO map, decoupling; register the card

**Files:**
- Create: `hardware/sheets/card_isatest.py`
- Modify: `hardware/tools/build.py:60` (`CARD_SHEETS` list)

**Interfaces:**
- Produces: module `card_isatest` with `NAME`, `TITLE`, `PAPER="A2"`, `PINS=[]`, `GPIO_NET` dict, `build(sch, lib)`; nested helpers `N`, `decouple`, `xcvr`, `s595`, `s165`, `pull` used by later tasks. Pico placed as `M1`; internal nets `MD0..MD7`, `DATADIR`, `M_MEMR/M_MEMW/M_IOR/M_IOW`, `IOCHRDY_S`, `M_REFRESH`, `SER`, `SRCLK`, `RCLK_ADDR`, `RCLK_CTRL`, `IN_PL`, `IN_QH`, `~{BUF_EN}`, `PIO_CLK`, `CLK_S` established on the Pico pins.

- [ ] **Step 1: Create `hardware/sheets/card_isatest.py`** with the skeleton (Pico + helpers + decoupling). Later tasks insert their blocks at the marked point:

```python
"""card_isatest -- standalone ISA card tester: a stock Raspberry Pi Pico acts as
the ISA host / bus master to exercise a device-under-test (DUT) card over USB
serial. See docs/superpowers/specs/2026-07-01-isa-test-card-design.md.

The Pico drives the full 8-bit ISA bus through 74LVC245A 3.3<->5V transceivers:
  * data D0-7   : direct Pico GPIO (MD0-7), dir = DATADIR
  * address A0-19: 74HC595 OUT chain (split address / control latches)
  * control out : strobes direct + AEN/RESET_DRV/TC/DACK/BALE on the OUT chain
  * status in   : IRQ/DRQ/IOCHCK# on a 74HC165 IN chain; IOCHRDY/CLK sensed direct
A 14.318 MHz can-oscillator clock tree (/2, /3, PIO override) makes CLK/OSC.
Standalone board: bus + power arrive via its own ISA slot + sidecar header, so
there is no parent interface (PINS = []), like the other card_* PCBs.
"""
import isa_conn
import mxbus  # noqa: F401  (canonical names spelled out below)

NAME = "card_isatest"
TITLE = "ISA Card Tester -- Pico host/bus-master"
PAPER = "A2"               # room for the Pico + 8x '245 + shift chains + slot
PINS = []                  # standalone PCB: bus + power come through the connectors

# Pico GPIO -> internal net (MCU side). 24 of 26 used; GP27/GP28 spare.
GPIO_NET = {
    0: "MD0", 1: "MD1", 2: "MD2", 3: "MD3", 4: "MD4", 5: "MD5", 6: "MD6", 7: "MD7",
    8: "DATADIR",
    9: "M_MEMR", 10: "M_MEMW", 11: "M_IOR", 12: "M_IOW",
    13: "IOCHRDY_S", 14: "M_REFRESH",
    15: "SER", 16: "SRCLK", 17: "RCLK_ADDR", 18: "RCLK_CTRL",
    19: "IN_PL", 20: "IN_QH", 21: "~{BUF_EN}", 22: "PIO_CLK",
    26: "CLK_S",
}
_HIER_SHAPE = {}  # standalone board: all nets are local labels


def build(sch, lib):
    # ---- shared helpers -------------------------------------------------
    def N(comp, key, name, dx=2.54, dy=0.0):
        return sch.net(comp, key, name, dx=dx, dy=dy, kind="label")

    def decouple(ref, at, hi="+3V3"):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", hi, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    def xcvr(ref, at, dir_net, vcc="+3V3"):
        """74LVC245A buffer. dir_net -> A->B pin; CE(~OE) -> ~{BUF_EN}."""
        u = sch.place("mini-xt:74LVC245A", ref, "74LVC245A", at=at)
        N(u, "VCC", vcc, dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "A->B", dir_net)
        N(u, "CE", "~{BUF_EN}")
        return u

    def s595(ref, at, rclk):
        """74HC595 SIPO @3V3. SRCLK shared; per-segment RCLK; OE tied on."""
        u = sch.place("74xx:74HC595", ref, "74HC595", at=at)
        N(u, "VCC", "+3V3", dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "SRCLK", "SRCLK")
        N(u, "RCLK", rclk)
        N(u, "~{OE}", "GND")        # internal side always driven; bus gated by '245
        N(u, "~{SRCLR}", "+3V3")
        return u

    def s165(ref, at):
        """74HCT165 PISO @3V3. CP shared with SRCLK; ~{PL}=IN_PL."""
        u = sch.place("mini-xt:74HCT165", ref, "74HCT165", at=at)
        N(u, "VCC", "+3V3", dx=0, dy=-2.54)
        N(u, "GND", "GND", dx=0, dy=2.54)
        N(u, "CP", "SRCLK")
        N(u, "~{PL}", "IN_PL")
        N(u, "~{CE}", "GND")
        return u

    def pull(ref, at, net, rail):
        r = sch.place("Device:R", ref, "10k", at=at)
        sch.net(r, "1", net, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", rail, kind="label", dx=0, dy=2.54)

    # ---- M1: Raspberry Pi Pico module -----------------------------------
    M1 = sch.place("mini-xt:Pico", "M1", "Pico (RP2040)", at=(101.6, 152.4))
    # Power: VBUS = USB 5V; VSYS from the board 5V rail (jack or USB); 3V3 OUT
    # powers all the 3V3 logic on this card. (Power block wired in Task 7.)
    N(M1, "VBUS", "+5V_USB", dx=0, dy=-2.54)
    N(M1, "VSYS", "V5RAW", dx=0, dy=-2.54)
    N(M1, "3V3", "+3V3", dx=0, dy=-2.54)
    N(M1, "GND", "GND", dx=0, dy=2.54)
    for nm in ("3V3_EN", "RUN", "ADC_VREF"):
        sch.no_connect(M1.pin_xy(nm))
    for idx, net in GPIO_NET.items():
        N(M1, "GP%d" % idx, net)
    for idx in (27, 28):
        sch.no_connect(M1.pin_xy("GP%d" % idx))   # spare GPIO
    sch.text("Pico host/bus-master: USB serial console; drives full 8-bit ISA bus "
             "via 74LVC245A buffers. 24/26 GPIO used.", (38.1, 96.52))

    # ==== BLOCKS BELOW ADDED BY LATER TASKS (keep this marker) ============
    # [transceivers] [out-chain] [in-chain] [clock] [power] [connectors]

    # ---- decoupling (representative) ------------------------------------
    decouple("C1", (40.64, 50.8), "+3V3")
    decouple("C2", (55.88, 50.8), "+3V3")

    sch.text("Standalone ISA card tester PCB (card_isatest). Bus + power via the "
             "on-board ISA slot (J1) and 60-pin sidecar header (J2).", (38.1, 12.7))
```

- [ ] **Step 2: Register the card** — in `hardware/tools/build.py` change the `CARD_SHEETS` line (line 60):

```python
CARD_SHEETS = ["card_video", "card_com", "card_lpt", "card_rtc", "card_storage", "card_isatest"]
```

- [ ] **Step 3: Validate the skeleton sheet**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: histogram printed; **zero** `endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`; ends with `components placed: 3` (M1 + C1 + C2). If a collision appears, nudge coords per Global Constraints.

- [ ] **Step 4: Build the standalone card**

Run: `python3 -c 'import sys;sys.path.insert(0,"hardware/tools");import build;build.build_cards()' 2>&1 | tail -3`
Expected: a line `card card_isatest   3 comps  ...` with no load error.

- [ ] **Step 5: Commit**

```bash
git add hardware/sheets/card_isatest.py hardware/tools/build.py
git commit -m "Add card_isatest skeleton (Pico + helpers) and register the card

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Bus transceivers (8× `74LVC245A`)

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert at the `BLOCKS BELOW` marker)

**Interfaces:**
- Consumes: `xcvr`, `N`, `GPIO_NET` data nets `MD0..MD7`.
- Produces: bus nets `D0..D7`, `A0..A19`, `~{MEMR} ~{MEMW} ~{IOR} ~{IOW} AEN RESET_DRV TC BALE ~{DACK1} ~{DACK2} ~{DACK3} ~{REFRESH}` driven from internal `M_*`; sensed bus inputs `IRQ2..IRQ8 DRQ1..DRQ3 ~{IOCHCK} IOCHRDY CLK` → internal `*_S` (`IOCHRDY_S`, `CLK_S` reach the Pico). Address `'245` internal side = `MA0..MA19`.

- [ ] **Step 1: Insert the transceiver block** at the marker in `build()`:

```python
    # ---- bus transceivers: 8x 74LVC245A (3V3<->5V), OE = ~{BUF_EN} -------
    # Data (bidirectional): dir = DATADIR. A = MD (Pico), B = D (bus).
    UD = xcvr("U1", (203.2, 76.2), "DATADIR")
    for i in range(8):
        N(UD, "A%d" % i, "MD%d" % i)
        N(UD, "B%d" % i, "D%d" % i)
    # Address (output only): dir tied high (+3V3 => A->B). A = MA, B = A(bus).
    UA0 = xcvr("U2", (203.2, 152.4), "+3V3")
    UA1 = xcvr("U3", (279.4, 152.4), "+3V3")
    UA2 = xcvr("U4", (355.6, 152.4), "+3V3")
    for i in range(8):
        N(UA0, "A%d" % i, "MA%d" % i);        N(UA0, "B%d" % i, "A%d" % i)
        N(UA1, "A%d" % i, "MA%d" % (8 + i));  N(UA1, "B%d" % i, "A%d" % (8 + i))
    for i in range(4):
        N(UA2, "A%d" % i, "MA%d" % (16 + i)); N(UA2, "B%d" % i, "A%d" % (16 + i))
    for i in range(4, 8):
        sch.no_connect(UA2.pin_xy("A%d" % i)); sch.no_connect(UA2.pin_xy("B%d" % i))
    # Control OUT (output only): dir tied high. A = M_* (internal), B = bus.
    UCO0 = xcvr("U5", (203.2, 228.6), "+3V3")
    co0 = [("M_MEMR", "~{MEMR}"), ("M_MEMW", "~{MEMW}"), ("M_IOR", "~{IOR}"),
           ("M_IOW", "~{IOW}"), ("M_AEN", "AEN"), ("M_RESETDRV", "RESET_DRV"),
           ("M_TC", "TC"), ("M_BALE", "BALE")]
    for i, (a, b) in enumerate(co0):
        N(UCO0, "A%d" % i, a); N(UCO0, "B%d" % i, b)
    UCO1 = xcvr("U6", (279.4, 228.6), "+3V3")
    co1 = [("M_DACK1", "~{DACK1}"), ("M_DACK2", "~{DACK2}"),
           ("M_DACK3", "~{DACK3}"), ("M_REFRESH", "~{REFRESH}")]
    for i, (a, b) in enumerate(co1):
        N(UCO1, "A%d" % i, a); N(UCO1, "B%d" % i, b)
    for i in range(4, 8):
        sch.no_connect(UCO1.pin_xy("A%d" % i)); sch.no_connect(UCO1.pin_xy("B%d" % i))
    # Control IN (input only): dir tied low (GND => B->A). B = bus, A = *_S.
    UCI0 = xcvr("U7", (355.6, 228.6), "GND")
    ci0 = ["IRQ2", "IRQ3", "IRQ4", "IRQ5", "IRQ6", "IRQ7", "IRQ8", "DRQ1"]
    for i, b in enumerate(ci0):
        N(UCI0, "B%d" % i, b); N(UCI0, "A%d" % i, b + "_S")
    UCI1 = xcvr("U8", (431.8, 228.6), "GND")
    ci1 = [("DRQ2", "DRQ2_S"), ("DRQ3", "DRQ3_S"), ("~{IOCHCK}", "IOCHCK_S"),
           ("IOCHRDY", "IOCHRDY_S"), ("CLK", "CLK_S")]
    for i, (b, a) in enumerate(ci1):
        N(UCI1, "B%d" % i, b); N(UCI1, "A%d" % i, a)
    for i in range(5, 8):
        sch.no_connect(UCI1.pin_xy("A%d" % i)); sch.no_connect(UCI1.pin_xy("B%d" % i))
    decouple("C3", (190.5, 40.64), "+3V3")   # transceiver bank
    decouple("C4", (355.6, 40.64), "+3V3")
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: zero `endpoint_off_grid` / `unconnected_wire_endpoint` / `multiple_net_names`; `components placed: 13`. Nudge coords if a collision appears.

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add 74LVC245A bus transceiver bank

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: OUT shift chain (4× `74HC595`, split address/control latches)

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert after the transceiver block)

**Interfaces:**
- Consumes: `s595`, `N`, nets `SER`, `SRCLK`, `RCLK_ADDR`, `RCLK_CTRL`, and the `MA0..MA19` / `M_AEN M_RESETDRV M_TC M_DACK1 M_DACK2 M_DACK3 M_BALE` nets (driven here, consumed by Task 3's `'245`s).
- Produces: `SPEED_SEL`, `CLK_SRC`, `DUT_PWR_EN` (config outputs on the address-latch spare bits; consumed by Tasks 6/7).

Chain order (address upstream, control downstream): `SER → U9 → U10 → U11 → U12`. Address regs latch on `RCLK_ADDR`; control reg latches on `RCLK_CTRL`.

- [ ] **Step 1: Insert the OUT-chain block**:

```python
    # ---- OUT shift chain: 4x 74HC595 @3V3, split latches ----------------
    # U9/U10/U11 = address (RCLK_ADDR); U12 = control byte (RCLK_CTRL).
    UO0 = s595("U9",  (60.96, 304.8), "RCLK_ADDR")
    N(UO0, "SER", "SER")
    for i, q in enumerate(["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]):
        N(UO0, q, "MA%d" % i)
    UO1 = s595("U10", (137.16, 304.8), "RCLK_ADDR")
    N(UO0, "QH'", "SER_A01"); N(UO1, "SER", "SER_A01")
    for i, q in enumerate(["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]):
        N(UO1, q, "MA%d" % (8 + i))
    UO2 = s595("U11", (213.36, 304.8), "RCLK_ADDR")
    N(UO1, "QH'", "SER_A12"); N(UO2, "SER", "SER_A12")
    for i, q in enumerate(["QA", "QB", "QC", "QD"]):
        N(UO2, q, "MA%d" % (16 + i))
    # address-latch spare outputs carry the STATIC config selects (set once)
    N(UO2, "QE", "SPEED_SEL")
    N(UO2, "QF", "CLK_SRC")
    N(UO2, "QG", "DUT_PWR_EN")
    sch.no_connect(UO2.pin_xy("QH"))
    UOC = s595("U12", (289.56, 304.8), "RCLK_CTRL")
    N(UO2, "QH'", "SER_A2C"); N(UOC, "SER", "SER_A2C")
    ctl = ["M_AEN", "M_RESETDRV", "M_TC", "M_DACK1", "M_DACK2", "M_DACK3", "M_BALE"]
    for q, net in zip(["QA", "QB", "QC", "QD", "QE", "QF", "QG"], ctl):
        N(UOC, q, net)
    sch.no_connect(UOC.pin_xy("QH"))
    sch.no_connect(UOC.pin_xy("QH'"))
    decouple("C5", (60.96, 274.32), "+3V3")
    sch.text("OUT chain: address (U9-U11, RCLK_ADDR) + control byte (U12, "
             "RCLK_CTRL). Address-only updates shift 24b; controls stay latched.",
             (60.96, 335.28))
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: zero of the critical classes; `components placed: 18`.

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add split 74HC595 OUT shift chain (address+control)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: IN shift chain (2× `74HCT165`)

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert after the OUT-chain block)

**Interfaces:**
- Consumes: `s165`, `N`, sensed nets `IRQ2_S..IRQ8_S`, `DRQ1_S..DRQ3_S`, `IOCHCK_S` (from Task 3's input `'245`s), `SRCLK`, `IN_PL`.
- Produces: `IN_QH` (to Pico), internal cascade net `IN_CASCADE`.

- [ ] **Step 1: Insert the IN-chain block**:

```python
    # ---- IN shift chain: 2x 74HCT165 @3V3 (full-duplex, shared SRCLK) ----
    # U13 nearest Pico (Q7 -> IN_QH); U14 cascades in via DS.
    UI0 = s165("U13", (365.76, 304.8))
    in0 = ["IRQ2_S", "IRQ3_S", "IRQ4_S", "IRQ5_S", "IRQ6_S", "IRQ7_S",
           "IRQ8_S", "DRQ1_S"]
    for i, d in enumerate(in0):
        N(UI0, "D%d" % i, d)
    N(UI0, "Q7", "IN_QH")
    N(UI0, "DS", "IN_CASCADE")
    sch.no_connect(UI0.pin_xy("~{Q7}"))
    UI1 = s165("U14", (441.96, 304.8))
    in1 = ["DRQ2_S", "DRQ3_S", "IOCHCK_S"]
    for i, d in enumerate(in1):
        N(UI1, "D%d" % i, d)
    for i in range(3, 8):
        N(UI1, "D%d" % i, "GND")          # unused parallel inputs tied low
    N(UI1, "Q7", "IN_CASCADE")
    N(UI1, "DS", "GND")                    # far end of the cascade
    sch.no_connect(UI1.pin_xy("~{Q7}"))
    decouple("C6", (365.76, 274.32), "+3V3")
    sch.text("IN chain: IRQ2-8 / DRQ1-3 / IOCHCK# -> IN_QH (U14 cascades into "
             "U13). Sampled occasionally; off the hot path.", (365.76, 335.28))
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: zero of the critical classes; `components placed: 21`.

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add 74HCT165 IN shift chain (IRQ/DRQ/IOCHCK#)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Clock tree (14.318 can-osc + ÷2/÷3 + PIO override + buffer)

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert after the IN-chain block)

**Interfaces:**
- Consumes: `N`, nets `SPEED_SEL`, `CLK_SRC` (Task 4), `PIO_CLK` (Pico).
- Produces: bus nets `OSC` (14.318) and `CLK` (buffered). `CLK` is sensed back to the Pico via Task 3's `UCI1` (`CLK`→`CLK_S`). Mirrors `cpu_core`'s clock tree.

- [ ] **Step 1: Insert the clock block**:

```python
    # ---- clock tree: 14.318 can osc -> /2, /3 -> speed mux -> src mux ----
    #      -> 5V buffer -> bus CLK.  OSC drives the bus OSC pin directly.
    osc = sch.place("Oscillator:ACO-xxxMHz", "OSC1", "14.31818MHz", at=(60.96, 45.72))
    N(osc, "Vcc", "+5V", dx=0, dy=-2.54)
    N(osc, "GND", "GND", dx=0, dy=2.54)
    N(osc, "OUT", "OSC")
    ff = sch.place("mini-xt:74HCT74", "U15", at=(137.16, 45.72))     # /2
    N(ff, "VCC", "+5V", dx=0, dy=-2.54); N(ff, "GND", "GND", dx=0, dy=2.54)
    N(ff, "C", "OSC"); N(ff, "D", "CLK_QN"); N(ff, "~{Q}", "CLK_QN"); N(ff, "Q", "CLK7")
    N(ff, "~{S}", "+5V"); N(ff, "~{R}", "+5V")
    d3 = sch.place("mini-xt:74HCT163", "U16", at=(213.36, 45.72))    # /3 (preset-to-3)
    N(d3, "VCC", "+5V", dx=0, dy=-2.54); N(d3, "GND", "GND", dx=0, dy=2.54)
    N(d3, "CP", "OSC")
    N(d3, "D0", "+5V"); N(d3, "D1", "GND"); N(d3, "D2", "+5V"); N(d3, "D3", "+5V")
    N(d3, "CEP", "+5V"); N(d3, "CET", "+5V"); N(d3, "~{MR}", "+5V")
    N(d3, "TC", "DIV3_TC"); N(d3, "~{PE}", "DIV3_LD")   # preset-to-3 per cpu_core
    N(d3, "Q0", "CLK4")
    m1 = sch.place("mini-xt:74HCT157", "U17", at=(60.96, 106.68))    # speed mux
    N(m1, "VCC", "+5V", dx=0, dy=-2.54); N(m1, "GND", "GND", dx=0, dy=2.54)
    N(m1, "I0a", "CLK7"); N(m1, "I1a", "CLK4"); N(m1, "S", "SPEED_SEL")
    N(m1, "E", "GND"); N(m1, "Za", "CLK_HW")
    m2 = sch.place("mini-xt:74HCT157", "U18", at=(137.16, 106.68))   # source mux
    N(m2, "VCC", "+5V", dx=0, dy=-2.54); N(m2, "GND", "GND", dx=0, dy=2.54)
    N(m2, "I0a", "CLK_HW"); N(m2, "I1a", "PIO_CLK"); N(m2, "S", "CLK_SRC")
    N(m2, "E", "GND"); N(m2, "Za", "CLK_PRE")
    buf = sch.place("mini-xt:74HCT04", "U19", at=(213.36, 106.68))   # 5V buffer
    N(buf, "VCC", "+5V", dx=0, dy=-2.54); N(buf, "GND", "GND", dx=0, dy=2.54)
    N(buf, "P1", "CLK_PRE"); N(buf, "P2", "CLK")
    for p in ("P3", "P5", "P7", "P9", "P11", "P13"):
        N(buf, p, "GND")                                # tie unused inverter inputs
    for p in ("P4", "P6", "P8", "P10", "P12"):
        sch.no_connect(buf.pin_xy(p))
    decouple("C7", (60.96, 76.2), "+5V")
    sch.text("Clock: 14.318 OSC -> /2 (U15) & /3 (U16) -> SPEED_SEL mux (U17) -> "
             "CLK_SRC mux (U18, PIO override) -> buffer (U19) -> bus CLK. CLK "
             "sensed back to Pico via U8 (CLK_S). /3 preset per cpu_core.",
             (60.96, 132.08))
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: zero of the critical classes; `components placed: 28`. `DIV3_TC`/`DIV3_LD` will show as `label_dangling` (expected — same as `cpu_core`).

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add 14.318 can-osc clock tree with /2,/3 + PIO override

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Power (barrel jack + OR-ing + P-FET) and idle pull resistors

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert after the clock block)

**Interfaces:**
- Consumes: `N`, `pull`, nets `+5V_USB` and `V5RAW` (Pico, Task 2), `DUT_PWR_EN` (Task 4), `~{BUF_EN}`, `IOCHRDY`.
- Produces: bus rail `+5V` (switched), board raw rail `V5RAW`, defines safe idle via pulls.

- [ ] **Step 1: Insert the power + idle block**:

```python
    # ---- power: USB 5V + external jack -> OR-ing -> P-FET -> bus +5V -----
    jack = sch.place("Connector:Barrel_Jack", "J3", "5V jack", at=(495.3, 60.96))
    N(jack, "1", "VEXT"); N(jack, "2", "GND")
    dext = sch.place("Device:D_Schottky", "D1", at=(520.7, 60.96))   # jack OR-ing
    N(dext, "2", "VEXT"); N(dext, "1", "V5RAW")                       # 2=A, 1=K
    dusb = sch.place("Device:D_Schottky", "D2", at=(520.7, 76.2))    # USB OR-ing
    N(dusb, "2", "+5V_USB"); N(dusb, "1", "V5RAW")
    q = sch.place("Device:Q_PMOS", "Q1", at=(546.1, 68.58))          # high-side switch
    N(q, "S", "V5RAW"); N(q, "D", "+5V"); N(q, "G", "DUT_PWR_EN")
    # idle network (tester = motherboard): buffers default OFF; ready idle high.
    pull("R1", (152.4, 96.52), "~{BUF_EN}", "+3V3")   # buffers default disabled
    pull("R2", (571.5, 45.72), "IOCHRDY", "+5V")      # IOCHRDY idle high (ready)
    pull("R3", (571.5, 76.2), "DUT_PWR_EN", "+3V3")   # FET off until firmware drives
    decouple("C8", (490.22, 91.44), "+5V")            # bus rail bulk/decoupling
    sch.text("Power: USB 5V (logic) + external jack (bus/DUT) OR-ed via D1/D2 to "
             "V5RAW; Q1 P-FET (DUT_PWR_EN) switches bus +5V. See questions doc for "
             "gate-drive/level detail.", (470.0, 30.48))
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -8`
Expected: zero of the critical classes; `components placed: 34`.

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add USB+jack OR-ing power switch and idle pulls

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: DUT connectors (ISA card-edge slot + sidecar header)

**Files:**
- Modify: `hardware/sheets/card_isatest.py` (insert after the power block)

**Interfaces:**
- Consumes: `sch`, `isa_conn.place_header`, all bus nets driven/sensed by earlier tasks.
- Produces: `J1` real 8-bit ISA slot (true pinout, analog rails NC) and `J2` 60-pin sidecar header, both joined to the bus by net name.

- [ ] **Step 1: Insert the connector block** (a local `sdir` stubs each slot pin away from the body by its angle):

```python
    # ---- DUT connectors -------------------------------------------------
    # J1: real 8-bit ISA card-edge slot (Connector:Bus_ISA_8bit, true pinout).
    #     -5V/-12V/+12V/UNUSED are left NC (we provide no analog rails).
    slot = sch.place("Connector:Bus_ISA_8bit", "J1", "ISA slot (8-bit)",
                     at=(508.0, 254.0))
    slot_map = {
        "GND": "GND", "VCC": "+5V", "RESET": "RESET_DRV",
        "~{SMEMW}": "~{MEMW}", "~{SMEMR}": "~{MEMR}", "~{IOW}": "~{IOW}",
        "~{IOR}": "~{IOR}", "~{DACK3}": "~{DACK3}", "DRQ3": "DRQ3",
        "~{DACK1}": "~{DACK1}", "DRQ1": "DRQ1", "~{DACK0}": "~{REFRESH}",
        "CLK": "CLK", "IRQ7": "IRQ7", "IRQ6": "IRQ6", "IRQ5": "IRQ5",
        "IRQ4": "IRQ4", "IRQ3": "IRQ3", "IRQ2": "IRQ2", "~{DACK2}": "~{DACK2}",
        "TC": "TC", "ALE": "BALE", "OSC": "OSC", "IO": "~{IOCHCK}",
        "IO_READY": "IOCHRDY", "AEN": "AEN", "DRQ2": "DRQ2",
    }
    for i in range(20):
        slot_map["BA%02d" % i] = "A%d" % i
    for i in range(8):
        slot_map["DB%d" % i] = "D%d" % i
    NC = {"-5V", "-12V", "+12V", "UNUSED"}

    def sdir(comp, num, length=5.08):
        a = comp.sdef.pin(num).angle % 360
        if a == 0:   return (-length, 0.0)
        if a == 180: return (length, 0.0)
        if a == 90:  return (0.0, length)
        return (0.0, -length)

    for p in slot.sdef.pins:
        if p.name in NC:
            sch.no_connect(slot.pin_xy(p.number)); continue
        net = slot_map.get(p.name)
        if net is None:
            sch.no_connect(slot.pin_xy(p.number)); continue
        dx, dy = sdir(slot, p.number)
        sch.net(slot, p.number, net, kind="label", dx=dx, dy=dy)

    # J2: 60-pin sidecar header (shared isa_conn building block; soft-card compat).
    isa_conn.place_header(sch, "J2", (571.5, 152.4), label="ISA SIDECAR")
```

- [ ] **Step 2: Validate**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -10`
Expected: zero `endpoint_off_grid` / `unconnected_wire_endpoint` / `multiple_net_names`; `components placed: 36`. If `multiple_net_names` appears, the slot sits too close to another block — move `slot`/`J2` right/down by 12.7 mm and re-run.

- [ ] **Step 3: Commit**

```bash
git add hardware/sheets/card_isatest.py
git commit -m "card_isatest: add ISA card-edge slot (true pinout) + sidecar header

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Notes, README, and full-project build verification

**Files:**
- Create: `hardware/notes/questions-isatest.md`
- Modify: `hardware/README.md` (layout table)

**Interfaces:** none (documentation + integration verification).

- [ ] **Step 1: Create `hardware/notes/questions-isatest.md`**:

```markdown
# card_isatest -- decisions & open questions

Board: standalone Pico-based ISA host/bus-master card tester.
Spec: docs/superpowers/specs/2026-07-01-isa-test-card-design.md

## Decisions made during generation

- **Data bus direct, address shift-registered.** D0-7 on Pico GPIO (MD0-7);
  A0-19 on a split 74HC595 OUT chain (address latch RCLK_ADDR, control latch
  RCLK_CTRL). Fits 24/26 GPIO. (spec D2-D4)
- **Real ISA slot uses Connector:Bus_ISA_8bit** (stock true-pinout symbol) with a
  name remap to our mxbus nets; no custom isa_slot symbol was needed. The
  DACK0/REFRESH# pin maps to ~{REFRESH}; -5V/-12V/+12V/UNUSED left NC.
- **74HC595 (standard 74xx lib) for the OUT chain; mini-xt:74HCT165 reused for the
  IN chain.** Both run at +3V3; at 3.3V the HCT vs HC threshold distinction is
  moot. Confirm HC595 part choice at layout (74LVC595 also acceptable).
- **Config selects (SPEED_SEL / CLK_SRC / DUT_PWR_EN)** ride the address-latch
  spare 595 outputs (U11 QE/QF/QG), keeping GP27/GP28 as true spares.
- **Clock tree mirrors cpu_core** (14.318 can osc, /2 74HCT74, /3 74HCT163
  preset-to-3, 74HCT157 mux, 74HCT04 buffer), plus a second 74HCT157 for the
  PIO_CLK override selected by CLK_SRC.

## Open questions (review before layout)

- **/3 preset-to-3 (U16):** DIV3_TC/DIV3_LD wiring is copied from cpu_core and
  carries the same review flag -- verify the terminal-count-to-load path (polarity
  / one-shot) on the bench.
- **P-FET gate drive (Q1):** G is driven from DUT_PWR_EN (3V3 logic) with a pull
  to keep it off by default. A high-side P-FET switching a 5V rail needs its gate
  pulled to the source rail when off and pulled low (possibly via an NPN/level
  shift) to turn on -- the current single-resistor idle is a placeholder; finalize
  the gate-drive network at layout.
- **ISA slot analog pins:** -5V/-12V/+12V left NC. Decide whether to add labeled
  test points/jumpers for the rare 8-bit card that needs them.
- **Pico module symbol pin numbers:** GPIO NAMES are authoritative; the 40-pin
  physical numbers are best-effort -- confirm against the Pico datasheet at layout.
- **Bus-mastering DUT:** address is output-only; testing a card that drives the
  address bus is out of scope (would need address-readback buffering).
```

- [ ] **Step 2: Add `card_isatest` to the README layout table** — in `hardware/README.md`, under the `| File | Subsystem |` table, add this row after the `sheets/sidecar` row:

```markdown
| `sheets/card_isatest`     | Pico ISA host/bus-master test card (standalone; ISA slot + sidecar) |
```

- [ ] **Step 3: Full main-project build (ensures the lib change didn't break anything)**

Run: `python3 hardware/tools/build.py 2>&1 | tail -20`
Expected: all sheets build; ERC summary lines show no new errors; ends without a traceback.

- [ ] **Step 4: Build all standalone cards including the new one**

Run: `python3 -c 'import sys;sys.path.insert(0,"hardware/tools");import build;build.build_cards()' 2>&1 | tail -8`
Expected: a `card card_isatest  36 comps  ...` line (component count may differ slightly if coords were nudged); every card line present, no load errors.

- [ ] **Step 5: Final validate of the completed sheet**

Run: `python3 hardware/tools/validate_sheet.py card_isatest 2>&1 | tail -12`
Expected: zero `endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`, no "Failed to load".

- [ ] **Step 6: Commit**

```bash
git add hardware/notes/questions-isatest.md hardware/README.md hardware/cards/
git commit -m "card_isatest: add design notes, README entry, and built card outputs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage** (§ = spec section):
- §1–2 role/standalone board → Tasks 2, 8 (`PINS=[]`, ISA slot + sidecar).
- §4/§6 direct data + split OUT chain + unified IN chain → Tasks 3, 4, 5.
- §4 8× `74LVC245A` buffers → Task 3.
- §5 address output-only / data bidirectional → Task 3 (`'245` directions).
- §7 clock tree + PIO override + `CLK_SENSE` → Task 6 (+ `CLK_S` sense in Task 3).
- §8 power (USB + jack + FET) → Task 7.
- §9 power-up safe state (`~{BUF_EN}` pull-up, config defaults) → Tasks 4, 7.
- §10 pin budget (24/26) → Task 2 `GPIO_NET`.
- §11 firmware model → informative only (out of scope), noted in notes doc.
- §12 integration (new sheet, `CARD_SHEETS`, notes, README) → Tasks 2, 9. **Note:** spec §12 anticipated a custom `isa_slot.py`; the stock `Connector:Bus_ISA_8bit` symbol replaces it — recorded in the notes doc.
- §13 open questions → `questions-isatest.md` (Task 9).

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" — every step shows complete code and exact commands.

**Type/name consistency:** Internal net names are consistent across tasks — `MD0..MD7` (Task 2 GPIO ↔ Task 3 data `'245`), `MA0..MA19` (Task 3 ↔ Task 4), `M_*` control (Task 3 ↔ Task 4), `*_S` sensed inputs (Task 3 ↔ Task 5), `IOCHRDY_S`/`CLK_S` (Task 2 GPIO ↔ Task 3), `SPEED_SEL`/`CLK_SRC`/`DUT_PWR_EN` (Task 4 ↔ Tasks 6/7), `SER`/`SRCLK`/`RCLK_ADDR`/`RCLK_CTRL`/`IN_PL`/`IN_QH` consistent. `~{BUF_EN}` gates every `'245` `CE` (Task 3 `xcvr`) and is pulled up in Task 7. Component refs unique: `M1`, `U1`–`U19`, `OSC1`, `J1`–`J3`, `D1`/`D2`, `Q1`, `R1`–`R3`, `C1`–`C8`.

---

## Execution options

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
**2. Inline Execution** — execute tasks in this session with checkpoints.

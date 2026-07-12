# NE2000 Network Card (`network` sheet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `network` soft-card sheet (RTL8019AS NE2000, transcribed from Manawyrm's ISA8019) to the mini-xt motherboard, hardwired to 0x340 / IRQ2 / 10BaseT-with-link-test, with one disable jumper.

**Architecture:** One new declarative sheet builder (`hardware/sheets/network.py`) plus four new custom symbols in `gensym.py`. Connectivity is by net name against the mxbus ISA contract; a single 74HCT125 implements the disable jumper (tri-states IRQ2 and forces chip AEN high). Spec: `docs/superpowers/specs/2026-07-12-network-card-design.md`.

**Tech Stack:** Python sheet generator (`mxsch`/`mxbus`), KiCad 10 CLI for ERC/netlist.

## Global Constraints

- **KiCad 10**: every build/validate command runs with `KICAD_CLI=~/.local/bin/kicad-cli` (verified working, v10.0.4). Leave `KICAD_SYMBOL_DIR` unset — stock symbol data still comes from the snap dir (`/snap/kicad/current/...`), which mxsch finds by default; the data files are version-stable.
- KiCad 10 ERC adds a new noise category `isolated_pin_label` (66 hits on the existing `rtc` sheet) — it joins the EXPECTED/ignorable list alongside `pin_not_connected`, `pin_not_driven`, `label_dangling`, `lib_symbol_issues`. Must-be-zero list is unchanged: `endpoint_off_grid`, `unconnected_wire_endpoint`, `multiple_net_names`, "Failed to load".
- Soft-card isolation: `network.py` may use ONLY ISA signals + power (no `PRIV_*`).
- All placement on the 2.54 mm grid; canonical mxbus net names exactly.
- Commit after each task (`git add` the generated `.kicad_sch`/`.net` outputs together with their Python sources — they are build outputs but ARE checked in).
- **Do not trust memory for RTL8019AS facts** — every pin/strap value below was verified 2026-07-12 against the Realtek datasheet (scratchpad `rtl8019as.pdf`, pages 5–22) AND the LCSC/EasyEDA symbol (C10016). If something looks inconsistent while implementing, re-check those sources, not intuition.

### Verified RTL8019AS facts used throughout (do not re-derive)

- Config pins have **internal 100 kΩ pull-downs**, latched at RSTDRV falling edge: open = 0, 10 k external pull-up = 1. (Datasheet §4.3.)
- Strap targets: JP(65)=1, IOS[3:0]=0010 → 0x340 (IOS1 = pin 82), IRQS[2:0]=000 → INT0 = IRQ2/9, **PL[1:0]=00** = auto-detect **with 10BaseT link test enabled** (this is the "10BaseT with link test" the user asked for — PL=01 is link test *disabled*; spec §3 has been corrected), BS[4:0]=00000 = no boot ROM, PNP(66)=0. All zeros = leave open.
- AUI (64) tied directly to GND ("if not used, connect to GND" — datasheet §4.4).
- IOCS16B/SLOT16 (96): 27 k pull-down = 8-bit slot (datasheet §4.2).
- INT0 (pin 4) is push-pull when selected (unselected INT pins tri-state; IRQEN powers up = 1) — hence the '125 gate on IRQ2.
- 93C46 is read for the MAC even in strap mode; EEDO(77)/EEDI(78)/EESK(79) still carry the EEPROM interface while doubling as PL1/IRQS0/IRQS1 straps (all three strap to 0 = no pull-ups, EEPROM drives them only while EECS is asserted).

---

### Task 1: Custom symbols (gensym.py)

**Files:**
- Modify: `hardware/tools/gensym.py` (add four `make_ic` calls; add them to the `lib` list at the bottom)
- Regenerates: `hardware/mini-xt.kicad_sym`

**Interfaces:**
- Produces symbols `mini-xt:RTL8019AS`, `mini-xt:AT93C46`, `mini-xt:13F-39MNL`, `mini-xt:RJ45_LED` with the exact pin numbers/names below. Task 2 wires against these names.

- [ ] **Step 1: Add the four symbols to gensym.py**

Follow the existing `make_ic` style (see `aps6404l` at the bottom of the file). Pin lists below are complete and verified (datasheet + EasyEDA C10016/C6499/C115949/C386757). Distribute left/right for readability; `top`/`bottom` for power.

```python
rtl8019as = make_ic(
    "RTL8019AS",
    left=[  # ISA side
        ("5","SA0","input"),("7","SA1","input"),("8","SA2","input"),
        ("9","SA3","input"),("10","SA4","input"),("11","SA5","input"),
        ("12","SA6","input"),("13","SA7","input"),("15","SA8","input"),
        ("16","SA9","input"),("18","SA10","input"),("19","SA11","input"),
        ("20","SA12","input"),("21","SA13","input"),("22","SA14","input"),
        ("23","SA15","input"),("24","SA16","input"),("25","SA17","input"),
        ("26","SA18","input"),("27","SA19","input"),
        ("36","SD0","bidirectional"),("37","SD1","bidirectional"),
        ("38","SD2","bidirectional"),("39","SD3","bidirectional"),
        ("40","SD4","bidirectional"),("41","SD5","bidirectional"),
        ("42","SD6","bidirectional"),("43","SD7","bidirectional"),
        ("95","SD8","bidirectional"),("94","SD9","bidirectional"),
        ("93","SD10","bidirectional"),("92","SD11","bidirectional"),
        ("91","SD12","bidirectional"),("90","SD13","bidirectional"),
        ("88","SD14","bidirectional"),("87","SD15","bidirectional"),
        ("29","IORB","input"),("30","IOWB","input"),
        ("31","SMEMRB","input"),("32","SMEMWB","input"),
        ("33","RSTDRV","input"),("34","AEN","input"),
        ("35","IOCHRDY","output"),("96","IOCS16B","bidirectional"),
        ("4","INT0","output"),("3","INT1","output"),("2","INT2","output"),
        ("1","INT3","output"),("100","INT4","output"),("99","INT5","output"),
        ("98","INT6","output"),("97","INT7","output"),
    ],
    right=[  # config straps / BROM bus / EEPROM / medium / LEDs
        ("65","JP","input"),("66","PNP","input"),
        ("67","BS0","input"),("68","BS1","input"),("69","BS2","input"),
        ("71","BS3","input"),("72","BS4","input"),
        ("73","BA15","output"),("74","PL0","input"),("75","~{BCS}","output"),
        ("76","EECS","output"),("77","EEDO","bidirectional"),
        ("78","EEDI","bidirectional"),("79","EESK","bidirectional"),
        ("80","BD4","bidirectional"),("81","BD3","bidirectional"),
        ("82","BD2","bidirectional"),("84","BD1","bidirectional"),
        ("85","BD0","bidirectional"),
        ("50","X1","input"),("51","X2","output"),
        ("45","TPOUT+","output"),("46","TPOUT-","output"),
        ("59","TPIN+","input"),("58","TPIN-","input"),
        ("49","TX+","output"),("48","TX-","output"),
        ("56","RX+","input"),("55","RX-","input"),
        ("54","CD+","input"),("53","CD-","input"),("64","AUI","input"),
        ("60","LEDBNC","output"),("61","LED0","output"),
        ("62","LED1","output"),("63","LED2","output"),
    ],
    top=[("6","VDD","power_in"),("17","VDD","power_in"),("47","VDD","power_in"),
         ("57","VDD","power_in"),("70","VDD","power_in"),("89","VDD","power_in")],
    bottom=[("14","GND","power_in"),("28","GND","power_in"),("44","GND","power_in"),
            ("52","GND","power_in"),("83","GND","power_in"),("86","GND","power_in")],
    description="RTL8019AS NE2000-compatible ISA Ethernet, TQFP-100. Pins verified vs datasheet + LCSC C10016 2026-07-12.",
    datasheet="http://realtek.info/pdf/rtl8019as.pdf")

at93c46 = make_ic(
    "AT93C46",
    left=[("1","CS","input"),("2","SK","input"),("3","DI","input")],
    right=[("4","DO","output"),("6","ORG","input"),("7","NC","no_connect")],
    top=[("8","VCC","power_in")], bottom=[("5","GND","power_in")],
    description="93C46 microwire EEPROM (NIC MAC storage), SOIC-8. Pins verified vs LCSC C6499.",
    datasheet="https://www.lcsc.com/datasheet/lcsc_datasheet_2102011832_Microchip-Tech-AT93C46DN-SH-T_C6499.pdf")

lan_xfmr = make_ic(
    "13F-39MNL",
    left=[("1","TD+","passive"),("2","TDCT","passive"),("3","TD-","passive"),
          ("6","RD+","passive"),("7","RDCT","passive"),("8","RD-","passive")],
    right=[("16","TX+","passive"),("15","TXCT","passive"),("14","TX-","passive"),
           ("11","RX+","passive"),("10","RXCT","passive"),("9","RX-","passive")],
    ref="T",
    description="10BaseT pulse transformer 1:1 w/ filters (pins 4,5,12,13 n/c in package). Pins verified vs LCSC C115949.",
    datasheet="https://www.lcsc.com/datasheet/lcsc_datasheet_1810311821_Shanghai-YDS-Tech-13F-39MNL_C115949.pdf")

rj45_led = make_ic(
    "RJ45_LED",
    left=[("1","P1","passive"),("2","P2","passive"),("3","P3","passive"),
          ("4","P4","passive"),("5","P5","passive"),("6","P6","passive"),
          ("7","P7","passive"),("8","P8","passive")],
    right=[("9","LA+","passive"),("10","LA-","passive"),
           ("11","LB+","passive"),("12","LB-","passive"),
           ("13","SH1","passive"),("14","SH2","passive")],
    ref="J",
    description="RJ45 jack, shielded, 2 LEDs (Ckmtw R-RJ45R08P-C000). Pins verified vs LCSC C386757: 9/10 + 11/12 are the LED anode/cathode pairs, 13/14 shield.",
    datasheet="https://www.lcsc.com/product-detail/C386757.html")
```

If `make_ic` rejects `"no_connect"` as an etype, use `"input"` for the AT93C46 NC pin (Task 2 no_connects it anyway).

- [ ] **Step 2: Add the new symbols to the `lib` list**

In the `lib = [...]` assignment at the bottom, append `rtl8019as, at93c46, lan_xfmr, rj45_led` before `] + glue_syms`.

- [ ] **Step 3: Regenerate and verify**

```sh
cd /home/andrew/repos/mini-xt
python3 hardware/tools/gensym.py
python3 hardware/tools/pins.py mini-xt:RTL8019AS | head -30
python3 hardware/tools/pins.py mini-xt:AT93C46
python3 hardware/tools/pins.py mini-xt:13F-39MNL
python3 hardware/tools/pins.py mini-xt:RJ45_LED
```

Expected: each lists its pins with the numbers above; RTL8019AS shows 100... actually 88 placed pins (12 power pins are 6 VDD + 6 GND stacks) — verify SA0=5, INT0=4, JP=65, BD2=82, IOCS16B=96 specifically.

- [ ] **Step 4: Confirm the existing build still passes (symbols file feeds every sheet)**

```sh
KICAD_CLI=~/.local/bin/kicad-cli python3 hardware/tools/validate_sheet.py rtc
```

Expected: same result as before the change (no structural violations).

- [ ] **Step 5: Commit**

```sh
git add hardware/tools/gensym.py hardware/mini-xt.kicad_sym
git commit -m "Symbols: RTL8019AS, AT93C46, 13F-39MNL, RJ45_LED (verified vs datasheet + EasyEDA)"
```

---

### Task 2: The `network` sheet

**Files:**
- Create: `hardware/sheets/network.py`
- Create: `hardware/notes/questions-network.md`

**Interfaces:**
- Consumes: Task 1 symbols.
- Produces: sheet module with `NAME="network"`, `TITLE`, `PAPER="A3"`, `PINS` (list below) — Task 3 registers it in `build.py`.

**PINS (the sheet's ISA interface, nothing else):**

```python
PINS = (
    [pin(s, "input") for s in mxbus.ADDR] +               # A0..A19
    [pin(s, "bidirectional") for s in mxbus.DATA] +       # D0..D7
    [pin(s, "input") for s in ["~{IOR}", "~{IOW}", "~{MEMR}", "~{MEMW}",
                               "AEN", "RESET_DRV"]] +
    [pin("IOCHRDY", "output"), pin("IRQ2", "output")]     # IRQ2 via '125; JP1 open frees it
)
```

- [ ] **Step 1: Write `network.py`**

Module docstring: transcription provenance (Manawyrm ISA8019 Rev A, CERN-OHL; `../ISA8019`), deviations (no boot ROM, straps hardwired, disable jumper + '125, successor RJ45 part), and the three hardwired choices (0x340 / IRQ2 / PL=00 link-test-on).

Complete net map (every non-NC pin; NC everything else with `sch.no_connect`):

**U1 = `mini-xt:RTL8019AS`:**

| U1 pins | Net |
|--------------------------------|-----------------------------------|
| SA0..SA19 | `A0`..`A19` |
| SD0..SD7 | `D0`..`D7` |
| IORB / IOWB | `~{IOR}` / `~{IOW}` |
| SMEMRB / SMEMWB | `~{MEMR}` / `~{MEMW}` |
| RSTDRV | `RESET_DRV` |
| AEN | `AEN_CHIP` (from U3, NOT bus AEN) |
| IOCHRDY | `IOCHRDY` |
| INT0 | `INT0_RAW` (to U3, NOT IRQ2) |
| IOCS16B | `SLOT16` |
| JP | `JP_HI` |
| BD2 (=IOS1) | `IOS1_HI` |
| AUI | `GND` |
| EECS / EESK / EEDI / EEDO | `EECS` / `EESK` / `EEDI` / `EEDO` |
| X1 / X2 | `XTAL1` / `XTAL2` |
| TPOUT+ / TPOUT- | `TPOUT+` / `TPOUT-` |
| TPIN+ / TPIN- | `TPIN+` / `TPIN-` |
| LED0 / LED1 | `LED_LNK` / `LED_ACT` |
| VDD ×6 / GND ×6 | `+5V` / `GND` |
| NC (each gets `sch.no_connect`): SD8-15, INT1-7, PNP, BS0-4, BA15, PL0, ~{BCS}, BD4, BD3, BD1, BD0, TX+, TX-, RX+, RX-, CD+, CD-, LEDBNC, LED2 | — |

Add `sch.text` notes: (1) strap table — "Hardwired config (RSTDRV-latched, internal 100k pull-downs; open=0): JP=1 strap mode, IOS[3:0]=0010 → I/O 0x340, IRQS[2:0]=000 → INT0=IRQ2/9, PL[1:0]=00 → 10BaseT + link test, BS=00000/PNP=0 → no BROM, no PnP. Only JP and IOS1 (BD2) get 10k pull-ups; all other config pins deliberately open."; (2) "SLOT16: 27k pull-down = 8-bit slot (datasheet-specified value, not a generic 10k)."; (3) "93C46 holds the MAC — ships blank; program once from DOS with RSET8019.EXE (Manawyrm repo, Programming utilities)."

**Straps/support (Device:R unless noted):**

| Ref | Value | From → To |
|------|-------|--------------------------|
| R1 | 10k | `JP_HI` → `+5V` |
| R2 | 10k | `IOS1_HI` → `+5V` |
| R3 | 27k | `SLOT16` → `GND` |
| R4 | 1M | `XTAL1` → `XTAL2` |
| R5 | 200 | `TPIN+` → `TPIN-` |
| R6 | 10k | `~{NET_EN}` → `+5V` |
| R7 | 10k | `AEN_CHIP` → `+5V` |
| R8 | 1k | `+5V` → `LNK_A` |
| R9 | 1k | `+5V` → `ACT_A` |

**U2 = `mini-xt:AT93C46`:** CS→`EECS`, SK→`EESK`, DI→`EEDI`, DO→`EEDO`, ORG→`+5V` (x16 org, as upstream — U2-6 on the +5V net in ISA8019.xml), VCC→`+5V`, GND→`GND`, NC pin 7 no_connect. 100nF decoupler.

**U3 = `mini-xt:74HCT125`** (pin naming as in com_port.py U6: P1=1OE, P2=1A, P3=1Y, ...):

| Pin | Net | Role |
|-----|--------------|-------------------------------------------|
| P1 | `~{NET_EN}` | gate-1 OE (low = enabled) |
| P2 | `INT0_RAW` | |
| P3 | `IRQ2` | tri-stated when JP1 open → sidecar can use |
| P4 | `~{NET_EN}` | gate-2 OE |
| P5 | `AEN` | bus AEN in |
| P6 | `AEN_CHIP` | R7 parks it high when JP1 open |
| P10, P13 | `+5V` | spare OEs disabled |
| P9, P12 | `GND` | spare inputs tied |
| P8, P11 | no_connect | |
| VCC/GND | `+5V`/`GND` | + 100nF |

**JP1 = `Connector_Generic:Conn_01x02`**, value "NET_EN": Pin_1→`~{NET_EN}`, Pin_2→`GND`. `sch.text`: "JP1 closed = NIC enabled; open = R6 parks ~{NET_EN} high → '125 tri-states IRQ2 AND forces chip AEN high (all I/O ignored). Fully releases the bus for a sidecar card."

**Y1 = `Device:Crystal`** "20MHz": 1→`XTAL1`, 2→`XTAL2`; C 20pF `XTAL1`→`GND`, C 20pF `XTAL2`→`GND` (R4 1M above).

**T1 = `mini-xt:13F-39MNL`** (connectivity from ISA8019.xml, verified):

| T1 pin | Net |
|--------------|----------------------------------|
| TD+ / TD- | `TPOUT+` / `TPOUT-` |
| TDCT | `TDCT` → 1nF → `GND` |
| RD+ / RD- | `TPIN+` / `TPIN-` |
| RDCT | `RDCT` → 1nF → `GND` |
| TX+ / TX- | `ETH_TX+` / `ETH_TX-` |
| TXCT | `TXCT` → 1nF → `EARTH` |
| RX+ / RX- | `ETH_RX+` / `ETH_RX-` |
| RXCT | `RXCT` → 1nF → `EARTH` |

**J1 = `mini-xt:RJ45_LED`:** P1→`ETH_TX+`, P2→`ETH_TX-`, P3→`ETH_RX+`, P6→`ETH_RX-`, P4/P5/P7/P8 no_connect, LA+→`LNK_A`, LA-→`LED_LNK`, LB+→`ACT_A`, LB-→`LED_ACT`, SH1/SH2→`EARTH`.

**FB1 = `Device:FerriteBead`** "100R@100MHz": 1→`EARTH`, 2→`GND`. Add `power:PWR_FLAG` on `EARTH` if ERC complains about an undriven net (mirror the picogus PWR_FLAG idiom).

**Decoupling:** 6× 100nF `+5V`/`GND` (row near U1) + 1× 47uF `Device:C` bulk. Plus the U2/U3 100nF above. `sch.text` note: LED semantics default to COL/RX at power-up; RSET8019 sets LEDS0=1 for link/activity — same behavior as the real ISA8019.

Layout: U1 center (~152.4, 152.4); interface column far left (emit_interface at 25.4,25.4); straps top-right; EEPROM + '125 + JP1 right; crystal below U1; T1/J1/EARTH parts far right (~300+); decoupling row at bottom. ~40 mm spacing.

- [ ] **Step 2: Validate (iterate until clean)**

```sh
KICAD_CLI=~/.local/bin/kicad-cli python3 hardware/tools/validate_sheet.py network
```

Expected: ZERO `endpoint_off_grid` / `unconnected_wire_endpoint` / `multiple_net_names` / "Failed to load". Large `pin_not_connected` / `pin_not_driven` / `isolated_pin_label` / `lib_symbol_issues` counts are normal.

- [ ] **Step 3: Write `hardware/notes/questions-network.md`**

Log (question / why / options / pick) at minimum: (a) PL[1:0]=00 not 01 — datasheet table showed "with link test" = auto-detect mode, spec corrected; (b) 93C46 kept + ships blank, MAC programming procedure (RSET8019.EXE / pg8019 from the ISA8019 repo); (c) LED default semantics (COL/RX until LEDS0/LEDS1 set in EEPROM — RSET8019 fixes; identical to upstream behavior); (d) SMEMRB/SMEMWB wired though BROM disabled (faithful transcription, inert, zero cost); (e) RJ45 successor part choice (C133529 EOL → C386757, LED polarity verified from EasyEDA pin names); (f) EARTH/chassis net: shield + line-side CTs through 1nF, single ferrite bead to logic GND (upstream design carried over).

- [ ] **Step 4: Commit**

```sh
git add hardware/sheets/network.py hardware/notes/questions-network.md
git commit -m "Network sheet: RTL8019AS NE2000 soft card (ISA8019 transcription)"
```

---

### Task 3: Wire into the build + parts binding

**Files:**
- Modify: `hardware/tools/build.py` (SHEETS list, line ~53)
- Modify: `hardware/tools/parts.py` (new entries)
- Regenerates: `hardware/network.kicad_sch`, root sheet, `hardware/mini-xt.net`, `hardware/erc.rpt`

**Interfaces:**
- Consumes: Task 2's `network` module.
- Produces: netlist with the NIC on the shared bus — Task 4's doc claims depend on it.

- [ ] **Step 1: Register the sheet**

In `build.py`, change:

```python
SHEETS = ["cpu_core", "bus_mcu", "supervisor", "video", "com_port",
          "parallel", "rtc", "power", "storage", "audio", "sidecar", "picogus"]
```

to append `"network"`:

```python
SHEETS = ["cpu_core", "bus_mcu", "supervisor", "video", "com_port",
          "parallel", "rtc", "power", "storage", "audio", "sidecar", "picogus",
          "network"]
```

- [ ] **Step 2: parts.py entries**

Add a `# ---- network (NE2000, ISA8019 transcription) 2026-07-12 ----` block to `PART_MAP`:

```python
("mini-xt:RTL8019AS", "RTL8019AS"): E("C22465363", "RTL8019AS-LF_R", "TQFP-100",
    "NE2000 NIC. Alt C10016 (~$11) had only 4 pcs on 2026-07-12; C22465363 (~$19.5, 202 pcs) is the safe bind -- re-check both at order time"),
("mini-xt:AT93C46", "AT93C46"): E("C6499", "AT93C46DN-SH-T", "SOIC-8",
    "NIC MAC EEPROM; ships blank -- program once with RSET8019.EXE"),
("mini-xt:13F-39MNL", "13F-39MNL"): E("C115949", "13F-39MNL", "SMD-16",
    "10BaseT magnetics, as ISA8019 upstream"),
("mini-xt:RJ45_LED", "RJ45_LED"): E("C386757", "R-RJ45R08P-C000", "RJ45 TH right-angle",
    "shielded + 2 LEDs; successor to upstream C133529 (EOL)"),
("Device:Crystal", "20MHz"): E("C110936", "X322520MSB4SI", "SMD-3225",
    "NIC 20 MHz crystal, as ISA8019 upstream"),
```

Check whether `Device:R` values `27k`/`200`/`1M` and `Device:C` values `20pF`/`1nF`/`47uF` already resolve (grep `parts.py` for how R/C values are mapped — there may be a generic fallback). Add value entries only for the ones the build reports unmapped.

- [ ] **Step 3: Full build**

```sh
KICAD_CLI=~/.local/bin/kicad-cli python3 hardware/tools/build.py
```

Expected: exit 0, "wrote project: root + 13 sheets", no STRUCTURAL violations, netlist exported.

- [ ] **Step 4: Netlist span checks**

```sh
python3 - <<'EOF'
import re
net = open("hardware/mini-xt.net").read()
for sig in ["IRQ2", "IOCHRDY", "/network/EECS", "/network/~{NET_EN}", "/network/ETH_TX+"]:
    print(sig, "FOUND" if sig in net else "MISSING")
EOF
grep -c "network" hardware/mini-xt.net
```

Expected: IRQ2 net includes nodes from BOTH `network` (U3 gate 1) and `bus_mcu`/`sidecar` (the '165 collector + header); IOCHRDY spans network + the other soft cards; the local nets exist. If IRQ2 only has network nodes, the hier pin name is off — fix and rebuild.

- [ ] **Step 5: Commit**

```sh
git add hardware/tools/build.py hardware/tools/parts.py hardware/*.kicad_sch hardware/*.kicad_pro hardware/mini-xt.net hardware/erc.rpt hardware/sym-lib-table
git commit -m "Build: register network sheet; parts.py NIC bindings"
```

---

### Task 4: Documentation

**Files:**
- Modify: `docs/irq-io-map.md`
- Modify: `docs/xt-mcu-sbc-design.md` (soft-card enumeration — grep for where picogus/storage are listed)
- Modify: `hardware/notes/jlcpcb-sourcing.md`

**Interfaces:** none (prose only); claims must match the Task 3 netlist.

- [ ] **Step 1: irq-io-map.md**

IRQ table — replace the IRQ2 row:

```markdown
| IRQ2  | physical | NE2000 NIC (0x340) — hardwired     | delivered as IRQ9 via AT redirect; NIC JP1 open tri-states it for the sidecar   |
```

(The old "reserved: future COM4" note dies; also update the COM4 rows: `0x2E8 (reserved) sidecar COM4` becomes "future; needs a freed COM/LPT IRQ (IRQ2 now taken by the NIC)".)

I/O table — insert between 0x300 and 0x3F0 rows:

```markdown
| 0x340–0x35F               | NE2000 NIC (RTL8019AS)                       | hardwired strap; IRQ2→9; JP1 = disable (frees IRQ2 + ignores all I/O)   |
```

Keep the table column alignment (pad with spaces — the tables must stay readable as plain text).

- [ ] **Step 2: xt-mcu-sbc-design.md**

Find the soft-card list/section (grep `picogus\|soft card`). Add a short subsection mirroring how picogus is described: NE2000 NIC, RTL8019AS at 0x340/IRQ2(9), 10BaseT, ISA8019 provenance, no boot ROM (MCU shadow-loads option ROMs; none needed for the NIC), 93C46 MAC EEPROM programmed via RSET8019, JP1 disable behavior.

- [ ] **Step 3: jlcpcb-sourcing.md**

Add a `## Network card (2026-07-12)` section: the RTL8019AS stock situation (C22465363 ~$19.5/202 pcs vs C10016 ~$11/4 pcs — bind C22465363, re-check at order), the C133529→C386757 RJ45 swap, symbol pin verification note (RTL8019AS/AT93C46/13F-39MNL/RJ45_LED all verified vs EasyEDA + datasheet 2026-07-12), and add RTL8019AS to the "thin stock — check before ordering" list.

- [ ] **Step 4: Verify tables render aligned, then commit**

```sh
git add docs/irq-io-map.md docs/xt-mcu-sbc-design.md hardware/notes/jlcpcb-sourcing.md
git commit -m "Docs: NE2000 NIC — IRQ2/0x340 maps, sourcing notes"
```

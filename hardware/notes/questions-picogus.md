# Open questions -- picogus sheet (on-board PicoGUS 2.0 chip-down, RP2040)

## Q1. Fidelity model: copy the reference verbatim, don't redesign
**Question:** How much of polpo's PicoGUS 2.0 "chip-down" reference (`picogus/hw-chipdown/`,
CERN-OHL-P) should be reproduced as-is vs. adapted to mini-xt conventions?
**Why:** The GPIO map, the ADS/BUSOE address-data-mux time-sharing scheme, and the
BUSOE-latch/AEN-masking glue are all baked into STOCK PicoGUS firmware. Renaming a
pin or re-deriving the glue logic "more cleanly" would silently break firmware
compatibility -- there is no generic substitute here the way there is for, say, a
74HCT245 bus buffer.
**Pick:** Transcribed pin-for-pin from `picogus/hw-chipdown/chipdown.net` (which
carries `pinfunction` annotations tying every GPIO to its schematic net name).
Verified against the netlist: the full stock GPIO map (SPI_RX/TX/SCK/~{SPI_CS} on
GPIO0-3; ~{RIOW}/~{RIOR} on GPIO4/5; AD0-AD7 on GPIO6-13; RA8/RA9 on GPIO14/15;
DIN/BCK/LRCK on GPIO16-18; ~{RDACK} on GPIO19; RTC_LS on GPIO20; RIRQ/RDRQ on
GPIO21/22; LED on GPIO23; RV_DATA/RV_CLK on GPIO24/25; RIOCHRDY on GPIO26; ADS on
GPIO27; MIDI_TX on GPIO28; GPIO29 grounded), the crystal network (12MHz + 30pF x2 +
1k series damping resistor on the post-resistor node, matching the reference's
Y1/C24/C25/R14 topology exactly), the BUSOE latch (2x 74HCT00 gates forming a
set-reset-like latch keyed off ADS toggling), and the CB3T3257/CB3T3245 FET-switch
address/data muxing all match the reference net-for-net.

## Q2. Design-change: wavetable header + MIDI out removed (2026-07-11)
**Question:** Keep the reference's OPL/wavetable daughterboard header and MIDI-out
port, or drop them?
**Why:** User decision to simplify the build. Both are optional peripherals in the
original PicoGUS -- the wavetable header only matters if a separate wavetable
daughterboard is fitted, and MIDI-out is a discrete niche feature.
**Pick:** Removed both, plus everything that existed only to serve them:
  - The M62429 (U13 in the reference) -- its ONLY job was wavetable-channel
    volume control via RV_CLK/RV_DATA.
  - The passive audio mix node (2x 2.2uF coupling caps + 2x 1k mixing resistors
    per channel) -- it existed to sum the DAC output with the wavetable board's
    return; with no wavetable there is nothing to mix.
  - The 40-pin wavetable header (J8 in the reference) and its ±12V pins (which
    were already NC on this board -- see Q3).
  - The MIDI TRS jack, its 220R current-limit resistors, and its two
    1k@100MHz ferrite beads.
  Audio path is now simply: PCM5102A OUTL/OUTR -> 470R + 2.2nF RC filter ->
  PG_L/PG_R directly (the DAC is ground-referenced via its own VNEG charge pump,
  and the audio sheet's summer input AC-couples anyway, so no additional coupling
  cap or mixing resistor is needed on this sheet).
  Stock firmware still drives GPIO24 (RV_DATA), GPIO25 (RV_CLK), and GPIO28
  (MIDI_TX) regardless of what's stuffed on the board -- those three GPIOs are
  left wired to local net labels with no destination (documented dangling nets,
  `label_dangling` in ERC, which is expected/ignorable noise per this repo's
  validation rules) rather than left floating with no net at all.
  All three removed blocks are still present in the untouched reference design
  under `picogus/hw-chipdown/` if a wavetable daughterboard or MIDI port is
  ever wanted on a future revision.

## Q3. Isolation exceptions (deviations from a pure soft card)
**Question:** The design brief calls for soft cards to touch ONLY ISA signals +
power (see `mxbus.py`/SHEET_AUTHORING_GUIDE.md). PicoGUS needs a few side
channels the reference design gets from its own edge connector / local jack /
local USB port. How to handle those without leaking private motherboard nets?
**Why / pick, itemized:**
  - **No ISA edge connector.** The bus arrives by net name like every other
    soft card (A0-A9, D0-D7, ~{IOR}/~{IOW}/AEN/RESET_DRV/TC/~{DACK1}/~{DACK3},
    IOCHRDY/DRQ1/DRQ3/IRQ2-5/IRQ7 out) -- no physical 60-/98-pin header on this
    sheet.
  - **No USB-A joystick port.** The Supervisor sheet owns USB HID; PicoGUS
    firmware's gameport support isn't wired up here.
  - **No local audio jack.** PG_L/PG_R (post-RC-filter DAC output, see Q2) feed
    the motherboard's audio summer instead of a 3.5mm TRS jack.
  - **No local programming USB.** The shared USB-C programming port lives on
    the supervisor sheet (J6 + SW2 DPDT selector); it reaches this chip as
    `PGUS_USB_DP`/`PGUS_USB_DM`. This is a **documented isolation exception**
    -- `mxbus.PRIV_PROG` exists specifically for this pair, with a comment at
    its definition explaining the escape hatch: to lift this card onto a
    standalone ISA board, delete the PGUS_USB_DP/DM hier pins and fit a local
    USB connector (exactly what the reference chip-down board does).
  - **GPIO29 grounded.** Firmware board-detect strap distinguishing the
    chip-down variant from PicoGUS's APU-daughterboard hardware; matches the
    reference's `GPIO29_ADC3` tied to GND.

## Q4. Sourcing traps (see `hardware/tools/parts.py` -- already populated)
**Question:** Which parts on this sheet have grade/stock gotchas that would
silently break the board if JLC substitutes the "obvious" alternative?
**Pick / notes:**
  - **APS6404L sample RAM MUST be the -3SQR grade (3.0-3.6V).** The -3SQN
    variant is a 1.8V part and is NOT pin/voltage compatible even though LCSC
    lists both under similar part numbers.
  - **M62429 was removed with the wavetable path (Q2)** -- if it's ever
    reinstated, note it MUST be the `M62429L` grade (3-5.5V); plain M62429 is
    a 4-6V part and won't run reliably off this board's 3.3V-derived AVDD_PGUS.
  - **(resolved 2026-07-14, later)** U8/U9 were 74LVC00 -- thin JLC stock,
    ~125 units -- but the LVC grade was a fossil of the 5V-ISA reference
    design; with the island all-3.3V they are plain **74HC00** now (basic
    part, shared BOM line with parallel/addr_decode), and the 74LVC00
    parts.py line is deleted.
  - **74AHC14 (the '04-body glue, U7)** is a 5V-tolerant-input 3.3V part;
    confirm continued stock before a run since it's a value-override on a
    generic 74HCT04 symbol body (see parts.py comment).
  All four are already keyed into `hardware/tools/parts.py`'s (lib_id, value)
  sourcing map with LCSC part numbers and the above caveats inline.

## Q5. DMA channel restriction
**Question:** Which DMA channel does the on-board Bus MCU actually service?
**Why:** The reference supports either DMA1 or DMA3 via the IRQ/DMA jumper
block (J1 here); our Bus MCU's DMA support is more limited.
**Pick:** Documented directly on-sheet (`sch.text` next to J1): the Bus MCU
services DMA channel 1 ONLY, so DRQ1/~{DACK1} must be the jumpered pair.
DRQ3/~{DACK3} remain available on the header for a future/alternate host but
won't work with this motherboard's current Bus MCU. IRQ5 is called out as the
recommended IRQ pick since the storage sheet's default is IRQ14 (see
`questions-storage.md`) -- don't strap both cards to IRQ5.

## Q6. 3.3V bus redesign (2026-07-14) -- which gates are level shifters?
**Question:** Task 6 brief: delete this sheet's LVC245s, keep U7 (74AHC14)/
U8,U9 (74LVC00)/U10 (LVC2G06) if they have a real non-level-shift function.
This sheet has no bare 74LVC245A -- what plays that role, and which of
U7-U10 actually needs deleting?
**Why / evaluation, per chip** (cross-checked against 3v3-verification.md
check 6, which pre-verified this exact GPIO map):
  - **U4/U5 (CB3T3257, "address/data mux"): KEEP.** A genuine 2:1 FET-switch
    mux -- the RP2040 only has 8 GPIO for AD0-7 and time-shares them between
    address and data roles via ADS (select) / ~{BUSOE} (gate). This is a
    GPIO-budget contract independent of bus voltage (check 6 already flagged
    it "must be preserved as-is even at 3.3V"). Unchanged.
  - **U6 (CB3T3245, "misc level shift"): DELETE.** Unlike U4/U5, U6 has NO
    mux -- 6 single-direction always-passthrough channels (A8/A9 sense in,
    TC sense in, IRQ5/DRQ drive out). Check 6 called this out by name as
    "the piece that becomes removable once the bus is 3.3V-native." Deleted;
    GPIO17/18/31/32/34 now label directly onto A8/A9/TC/IRQ5/DRQ (gpio_map
    updated, comment table added per the brief's "preserve exactly" ask).
  - **U7 (74HCT04 body, value 74AHC14): KEEP.** Real combinational/sequential
    logic: inverts ~{IOR}/~{IOW} to active-high, inverts DACK to ~{RDACK},
    forms a 2-stage RESET_DRV inversion (reset-delay chain feeding U9), and
    inverts ADS for the BUSOE latch (U9). None of this is a voltage bridge --
    it already ran on 3V3_PGUS before this task, unaffected by the redesign.
  - **U8 (74HCT00 body, value 74LVC00): KEEP.** NAND(AEN,DACK)=IOMASK gates
    ~{RIOR}/~{RIOW} so the card ignores I/O strobes during a DMA cycle it
    isn't acknowledging (check 6's "qualified via U7/U8 gates" masking).
    Already on 3V3_PGUS; not a level shifter.
  - **U9 (74HCT00 body, value 74LVC00): KEEP.** Forms the BUSOE set-reset-
    like latch (keyed off ADS toggling, per Q1) and the post-reset-delay RUN
    enable. Sequential glue logic, not a voltage bridge.
  - **U10 (74LVC2G06): KEEP.** Open-drain buffer for IOCHRDY's wired-AND bus
    semantics -- check 6: "stays regardless of voltage domain." Unchanged.
  So: only U6 falls in the "was purely 3.3V<->5V buffering" bucket this task
  targets; U4/U5/U7/U8/U9/U10 all have real non-level-shift jobs and stay.
**Also fixed while auditing for stray 5V nets touching RP2040-reachable
logic (brief: "confirm every net it now touches is 3.3V-only"):** R9 (15k
pull-up parking DACK idle-high when no DMA jumper is fitted) was tied to
`+5V`, even though DACK feeds U7/U8 gate inputs that are entirely on
3V3_PGUS and one hop from RP2040 GPIO6/7 (~{RIOR}/~{RIOW}) -- a real
5V-domain node reaching 3.3V-domain logic. Repointed to `3V3_PGUS`, matching
the R7/R8 pull-up convention already used elsewhere on this sheet. Audited
every other `+5V` use on the sheet (U3 regulator input, C7/C9 decoupling on
that same input) -- all are the AMS1117's 5V supply-side, not logic, so no
further changes needed.

## Q7. RP2040 GPIO map: keyed by GPIO name, not bare package-pin digits (2026-07-14)

**Question / trigger.** A review flagged `gpio_map` as a Critical wiring defect:
its keys were bare digit strings (`"17"`, `"31"`, `"32"`) and the report claimed
they were meant as GPIO numbers but the generator resolved them to package pins,
so "nearly every PicoGUS signal is wired to the wrong GPIO pad" and stock
firmware wouldn't run.

**Investigation.** `mxsch.Symbol.pin()` resolves a pin ref by `number == key OR
name == key`. On the KiCad `MCU_RaspberryPi:RP2040` symbol, GPIOs carry pin
**names** `GPIO0..GPIO29` at **package pin numbers** 2..41 (GPIO0=pin2,
GPIO14=pin17, GPIO20=pin31, GPIO29=pin41; power pins interleaved). No pin is
*named* a bare digit, so a key like `"31"` fell through to **package pin 31 =
GPIO20**.

**Ground truth.** `docs/PicoGUS-chipdown-schematic.pdf` (the reference RP2040
sheet, rendered at 300 dpi and read directly) gives the GPIO→signal map:
GPIO0-3=SPI, GPIO4=RIOW, GPIO5=RIOR, GPIO6-13=AD0-7, GPIO14/15=RA8/RA9(=A8/A9),
GPIO16-18=DIN/BCK/LRCK, GPIO19=RDACK, GPIO20=RTC(=TC), GPIO21=RIRQ(=IRQ5),
GPIO22=RDRQ(=DRQ), GPIO23=LED, GPIO24/25=RV_DATA/RV_CLK, GPIO26=RI/OCHRDY,
GPIO27=ADS, GPIO28=UART_TX(=MIDI_TX), GPIO29=GND(board-detect strap).

**Conclusion — the wiring was already CORRECT; the report's premise was a
misread.** The old digit keys were **package-pin numbers**, each deliberately
chosen so the signal lands on the correct GPIO pad per the reference. Every one
of the 30 keys checks out (e.g. `"31"`→pin31→GPIO20→TC, exactly what the
reference wants; `"32"`→pin32→GPIO21→IRQ5; `"41"`→pin41→GPIO29→GND strap). The
netlist confirms it: `GPIO20_31→/TC`, `GPIO21_32→/IRQ5`, `GPIO14_17→/A8`,
`GPIO4_6→~{RIOW}`, `GPIO19_30→~{RDACK}`, `GPIO29/ADC3_41→GND`. There was **no**
mis-wired pad. What was wrong was the *presentation*: the variable is named
`gpio_map` and the comment header said "GPIO", so the package-pin keys read like
GPIO numbers — which is exactly what produced this false report and the phantom
"GPIO29→LRCK / GPIO41→GND discrepancy" in 3v3-verification.md check 6.

**Fix (this commit).** Re-keyed `gpio_map` (and only the GPIO refs) by the
symbol's GPIO **name** (`"GPIO20"`, …; GPIO26-29 keep their `/ADCn` name
suffix). This resolves to the identical pads, so **connectivity is
byte-identical** — the regenerated `picogus.kicad_sch` and the netlist did not
change (only the netlist timestamp moved). The change is purely to make the
source self-documenting and immune to the name-vs-number trap. The in-sheet
comment table and 3v3-verification.md check 6 were annotated (not rewritten) to
mark the first column as package pins and to resolve the phantom discrepancy.
Power rails (multiple pins named `IOVDD`) and the QSPI/RUN/TESTEN pins were left
keyed by number — those names are non-unique or overbarred and were never part
of the confusing map.

# JLCPCB sourcing — 2026-07-03

Every component in the design was checked against the JLCPCB parts database.
The authoritative machine-readable result is `tools/parts.py` (the (lib_id,
value) → LCSC map that build.py applies as `LCSC Part Num` properties); this
file records the decisions and the things a human must re-check at order time.

## Custom-symbol pin verification (open-questions Q5 — RESOLVED)

Verified against JLCPCB/EasyEDA symbol data and the Maxim datasheets:

- **MAX3241** (MAX3241EEAI+T, LCSC C406859, SSOP-28): the original
  best-effort symbol was wrong on essentially EVERY pin (only C2+ matched),
  and used MAX3243-style pin names. The real part has `SHDN#` (22, tie high
  to run), `EN#` (23, tie LOW to enable receiver outputs), and two
  always-active receiver outputs `R1OUTB`/`R2OUTB` (21/20, NC here).
  Symbol regenerated; com_port.py rewired (~FORCEON→~EN is a polarity fix:
  it must be GROUNDED, where the old ~FORCEON was tied high).
- **DS12C887** (DS12C887+, LCSC C9869, EDIP-24): four pins were wrong —
  DS is 17 (was 16), RESET# 18 (was 17), IRQ# 19 (was 18), SQW 23 (was 21).
  Symbol regenerated; rtc.py wiring is by pin NAME so it followed along.

## Stock-forced substitutions (all same-pinout, netlist-verified)

| Wanted        | Not stocked → used     | LCSC     | Why it is safe |
|---------------|------------------------|----------|----------------|
| 74HCT374      | 74HCT574               | C6001    | same function, flow-through pinout; parallel.py rewired (Q→ outputs) |
| 74HCT163      | 74HC161                | C5610    | same pinout; async ~MR tied inactive; see voltage-domain note below |
| 74HCT157      | 74HC157                | C5609    | 3.3 V selects/PIO clock now pass through spare HCT04 gates (inverting → mux I0/I1 swapped) |
| 74HCT02       | 74HC02                 | C5588    | RTC decode inputs are always-5 V address lines |
| TCM809        | MCP809T-450I/TT        | C511285  | same SOT-23 pinout, 4.375 V threshold |
| 2N3904        | MMBT3904               | C20526   | SMD version of the same die |
| TL072→MCP6002 | (already swapped, H6)  | C7377    | RRIO, pin-identical |
| 1.8432 MHz XO | crystal on 16C550 XIN/XOUT | C47345430 | canned XOs at this frequency are 3.3 V-only and soft cards have no 3.3 V rail |

**HC-at-5V voltage-domain rule:** plain 74HC at 5 V cannot read a 3.3 V high
(Vih ≈ 3.5 V). Wherever an HC substitute would have seen a 3.3 V input:
- **bus_mcu address counters (5× HC161 + the HC08 CNT_RUN gate) moved into
  the 3.3 V domain** (VCC = 3V3_BUS): all their control inputs are MCU
  GPIOs, and the load data now comes from the MCU-side MD0–7 nets. Their
  3.3 V outputs feed the 5 V 74HCT244 bus buffers, whose TTL Vih (2.0 V)
  reads 3.3 V cleanly. No level shifters needed at all.
- **clock muxes (HC157 at 5 V)**: SPEED_SEL / CLK_SRC / PIO_CLK are squared
  up through spare 74HCT04 gates (HCT reads 3.3 V, drives 5 V). The gates
  invert, so each mux's I0/I1 inputs are swapped to keep firmware polarity.
- **14.31818 MHz oscillators are 3.3 V-only parts**: powered from +3V3 and
  buffered to the 5 V OSC net by a spare HCT04 gate (cpu_core U13,
  card_isatest U19). Clock phase inversion is irrelevant.

## Socket policy (fab installs the socket, chip goes in by hand)

| Component            | Socket (= its LCSC Part Num) | Chip source        |
|----------------------|------------------------------|--------------------|
| V20 (µPD70108)       | DIP-40 **machined** socket C2874018 | user stock (vintage) |
| AS6C4008-55 SRAM ×2  | DIP-32 **machined** socket C2874017 | user stock (no 5 V 512K×8 SRAM at JLC at all) |
| DS12C887 RTC         | DIP-24 600 mil **machined** socket C2684765 | LCSC C9869 ($14, extended) or user stock |
| 16550 UART (COM ×2)  | **SMD** PLCC-44 socket C2828044 (reflows with the SMD pass) | TL16C550CFNR (Active, Mouser ~320 pcs, $4-6; JLC C2653193) — or NOS/period NS16550AFN pulls, same industry PLCC pinout |
| Core2350B module ×2  | 2.54 mm female headers C2897411 | Waveshare (consign) |
| Pico module          | 2.54 mm female headers C2897411 | Raspberry Pi — official Pico stocked at JLC (C7203002, ~$8; Pico W C7203003) |

Module mounting (verified 2026-07-03 from the photos in
`hardware/Core2350B0-details-size.jpg` / `-inter.jpg`):
- **Core2350B has NO castellated edges** — it is a 25.4 × 25.4 mm
  double-ring through-hole PGA (two concentric 2.54 mm rows, 22.86 mm inner
  span, ~6 GND holes). It MUST mount on headers: one dual-row 2×N female
  strip per side covers both rings. Holes are silk-labelled by signal name
  (no canonical pin numbering), so the symbol's pin numbers are
  project-defined and the layout footprint must be authored to match them.
  Photos also confirm HSTX = GP12–19 and PSRAM CS = GP47, as the design
  assumes.
- **The Pico IS castellated** and JLC stocks the official module
  (C7203002), so the test card's Pico could alternatively be reflowed
  flat as an SMD part (confirm assembly eligibility of the dev-board
  category at quote time, or consign). Currently still on female headers.

The DIP sockets are the machined-pin (round-hole) grade, all verified
600 mil (15.24 mm) row spacing — ~$0.70–0.90 each vs $0.06–0.12 stamped,
worth it for vintage pins and repeated insertion. (Stamped fallbacks if
the machined parts go out of stock: DIP-40 C2332, DIP-32 C72122, DIP-24
C72120. Beware: many catalog DIP-24/32 sockets are the NARROW 300 mil
variant — check row spacing.)

The 16550 socket choice (2026-07-03): swappable UART for ~$0.39 + ~2 cm²
per port; one footprint takes new TI silicon, NOS tubes, and vintage pulls.
MaxLinear's PLCC ST16C550CJ44-F is EOL (their TQFP ST16C550IQ48-F lives on),
and TI's tube-packed CFN is obsolete — the reel CFNR is the active leg.

## Not available at JLCPCB (source elsewhere / consign)

- **8-bit ISA card-edge slot** (card_isatest J1) — 3.96 mm edge connector;
  consign or CONNFLY/EDAC from another distributor.
- **VGA HD15 (DE15) connector** (video card) — THT part from another
  distributor, or build the video card HDMI-only initially.

## Thin stock — re-verify with jlc_stock_check before ordering

- 16550: now SOCKETED (SMD PLCC-44, see socket table) with TL16C550CFNR as
  the chip — Active TI production, ~320 pcs at Mouser ($4-6 ea; ~$4.10@100),
  ~10 CIFNR at JLC. The TL16C550C/D family in general is healthy (LQFP DPT
  ~233, CPTR ~1066, DPFBR ~508 at Mouser), so no used pulls are ever
  *required*; the socket merely also accepts NOS/period NS16550AFN if
  wanted. Avoid eBay/AliExpress "16550" pulls for function — widely
  remarked/fake. PLCC-44 pin numbers differ from the DIP-40-style KiCad
  symbol — remap at footprint time.
- DB25 male (C5400534): ~10 pcs — likely needs a substitute.
- MAX3241EEAI+T (C406859): ~175. DS12C887+ (C9869): ~573.
- TPS563200DDCR (C97253): ~256.

## Other design changes made during sourcing

- **Supervisor QSPI flash is now a real W25Q128JVSIQ (C97521, basic)** —
  the placeholder 8-pin header could never boot the RP2040.
- 12 MHz crystal C9002 (CL = 20 pF): the 15 pF load caps (C1644) should be
  revisited against the crystal's CL at layout (≈2×(CL−Cstray) suggests
  more like 27–33 pF).
- 22 µF bulk caps: MLCC (C12891) replaces the polarized symbol's implied
  electrolytic.
- LEDs: KT-0603R (C2286) for both rail indicators.
- All jumpers/headers are cut-to-length 2.54 mm breakaway strips
  (C2337 1×40, C2333 2×40); the CF socket is a real SMD CompactFlash
  connector (C2962036) whose footprint replaces the generic 2×25 header at
  layout.

## Design-review additions (2026-07-11)

Protection + best-practice parts added by the 2026-07-11 review:

| Part                       | LCSC      | Where                                        |
|----------------------------|-----------|----------------------------------------------|
| BSMD1812-200-16V 2A hold   | C883156   | sidecar +5V_ISA feed fuse                    |
| BSMD1812-300-24V 3A hold   | C7500481  | power USB-C VBUS input fuse                  |
| SMBJ5.0A TVS (SMB)         | C19077558 | +5V clamps: power input, sidecar, isatest    |
| USBLC6-2SC6 (SOT-23-6)     | C2687116  | supervisor USB-A ESD array                   |
| 2N7002 (SOT-23)            | C8545     | storage IRQ5 tri-state inverter              |
| 27R 0603 (0603WAF270JT5E)  | C25190    | supervisor USB series termination            |
| 100R 0603                  | C22775    | VGA sync series, audio output series         |
| 47nF 0603                  | C1622     | MAX3241 C1 (5V values)                       |
| 330nF 0603                 | C1615     | MAX3241 C2-C4 (5V values)                    |
| 100uF alu SMD 16V          | C2887276  | supervisor USB host VBUS bulk                |

STOCK ALERT: TPS563200DDCR is down to 4 pcs at JLC (was ~256 on 2026-07-03).
Re-verify before any order; TPS563201DDCR (D-CAP2, different feedback network)
or another 3A 5->3.3V buck is the fallback -- re-check the divider/compensation
against whichever datasheet applies.

No JLC-stocked/KiCad-symboled TMDS ESD array was picked for the video card's
HDMI pairs (TPD4E05U06-class, <=0.15pF/line) -- choose at layout time.

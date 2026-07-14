# JLCPCB sourcing — 2026-07-03 (updated 2026-07-14: 3.3V single-board redesign)

Every component in the design was checked against the JLCPCB parts database.
The authoritative machine-readable result is `tools/parts.py` (the (lib_id,
value) → LCSC map that build.py applies as `LCSC Part Num` properties); this
file records the decisions and the things a human must re-check at order time.

**2026-07-14 update:** the board's internal bus moved to 3.3V (one PCB, V20's
own demux stage is now the sole 5V↔3.3V boundary; see
`docs/superpowers/specs/2026-07-14-3v3-single-board-design.md` and
`hardware/notes/3v3-verification.md`). This deleted several of the HCT
substitution rows below (their only use was removed with the DS12C887/
AS6C4008 parts) and added a new set of LVC-grade picks — see "3.3V redesign —
new/changed parts" below. The tables in this file were edited in place; rows
that are still live in the current sheets are kept, dead ones are removed.

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
  **Removed 2026-07-14** (3.3V redesign, decision #4): the RTC is now
  emulated in the Bus MCU + a PCF8563 I2C RTC on the Supervisor; the
  `rtc.py` sheet, the DS12C887 symbol (`gensym.py`), and this socket/chip
  pick are all gone. Kept here as history only.

## Stock-forced substitutions (all same-pinout, netlist-verified)

Rows still live in the current (3.3V, single-board) design:

| Wanted        | Not stocked → used     | LCSC     | Why it is safe |
|---------------|------------------------|----------|----------------|
| 74HCT163      | 74HC161 (bus_mcu address counter, card_isatest) | C5610    | same pinout; async ~MR tied inactive; 3.3V-domain part, no cross-voltage concern |
| 74HCT157      | 74HC157 (clock mux, now 3.3V-powered)  | C5609    | direct 3.3V select drive — no HCT-inverter stage needed any more (§3.2) |
| TCM809        | TCM809TENB713          | C47195   | same family/SOT-23 pinout, **-T grade, 3.08 V threshold** — correct for the 3.3V rail it now monitors (was wrongly bound to the 4.375V -450I/TT grade; fixed Task 10, see Q9 in questions-cpu_core.md) |
| 2N3904        | MMBT3904               | C20526   | SMD version of the same die |
| TL072→MCP6002 | (already swapped, H6)  | C7377    | RRIO, pin-identical |
| 1.8432 MHz XO | crystal on the UART's XIN/XOUT | C47345430 | canned XOs at this frequency are 3.3 V-only; now drives the TL16C550CPFBR's crystal pins instead of the old 16C550's |

**Dead as of the 3.3V redesign (rows removed):**
- **74HCT374 → 74HCT574** (C6001): the LPT data latch (parallel.py) moved
  again, from 74HCT574 to **74LVC574A** (3.3V) — see the new-parts table below.
  The 74HCT574 (C6001) PART_MAP entry is kept in `parts.py` but is now
  unreferenced by any sheet.
- **74HCT02 → 74HC02** (C5588): its only use was the RTC's ISA decode, which
  is deleted along with the RTC sheet. `parts.py` keeps the mapping (harmless,
  unreferenced) in case a future sheet needs plain 3.3V-domain 74HC02.

**RESOLVED (Task 10):** the TCM809 substitute was bound to MCP809T-450I, a
**4.375 V** reset threshold chosen when the part monitored the **5V** rail.
`cpu_core.py`'s reset supervisor runs on **+3V3**, so a 4.375V threshold could
never be satisfied by a healthy 3.3V rail — the supervisor held reset
permanently, and the board could never start. Rebound to **TCM809TENB713**
(C47195, real TCM809-family part, SOT-23, **3.08 V** threshold, stock 94):
3.08V sits safely below a 3.3V rail at -2% regulation tolerance (3.234V) with
~150 mV of margin, while still tripping well above ground. See
`hardware/notes/questions-cpu_core.md` Q9 for the full margin arithmetic.

**HC-at-3.3V-vs-5V voltage-domain rule (superseded picture):** the old
"plain 74HC at 5V cannot read a 3.3V high" caveat drove several of the
substitutions above; with the board now almost entirely 3.3V, that specific
cross-voltage hazard mostly disappeared (everything HC-grade left in the
design is 3.3V-powered with 3.3V-driven inputs). The remaining voltage-domain
hazard is the opposite one: **plain HC/HCT parts don't meet fmax margin at
3.3V** for the fastest signal in the design (the 14.318 MHz clock dividers) —
see the LVC picks below.

## 3.3V redesign — new / changed parts (2026-07-14)

Picks confirmed live via `jlc_search`/`jlc_get_part`/`jlc_stock_check`
(research: `hardware/notes/3v3-verification.md`). "Stock" is the count at
query time; **thin** flags anything to re-check before ordering.

| Role | MPN | LCSC | Package | Stock |
|--------------------------------------|------------------------|-----------|------------|--------------------|
| SRAM 512K×16 (replaces 2× AS6C4008)  | IS62WV51216BLL-55TLI   | C11315    | TSOP-II-44 | 1913 |
| Octal latch, 3.3V, 5V-tol (cpu_core address latches) | 74LVC573APW,118 | C6096 | TSSOP-20 | 18,681 |
| Octal xceiver, 3.3V, 5V-tol (cpu_core data, sidecar) | 74LVC245A (existing symbol/value) | — | — | see existing `parts.py` entry |
| Octal buffer, 3.3V, 5V-tol (sidecar) | 74LVC244APW,118        | C6079     | TSSOP-20   | 23,742 |
| Octal D-FF (parallel.py LPT latch, was 74HCT574) | 74LVC574AT20-13 | C842658 | TSSOP-20 | 88 **thin** |
| Quad tri-state (cpu_core U11/U15, network AEN/INT0) | 74LVC125AD,118 | C6057 | SOIC-14 | 17,935 |
| Dual open-drain (sidecar IOCHRDY/IOCHCK̄) | 74LVC2G07GW,125 (2G06 body, value override) | C24478 | SOT-363-6 | 6,631 |
| ÷2 clock divider (cpu_core U8, was 74HCT74) | 74LVC74APW,118 | C6100 | TSSOP-14 | 7,807 |
| ÷3 clock divider (cpu_core U9, was 74HC161) | 74LVC161PW,118 | C548136 | TSSOP-16 | 100 **thin** |
| UART ×2 (replaces socketed 16C550)   | TL16C550CPFBR          | C882798   | TQFP-48    | 5 **thin — verify**       |
| I2C RTC (Supervisor, battery-backed) | PCF8563T/5,518         | C7440     | SO-8       | 166,556 |
| CR2032 holder (Supervisor)           | CR2032-BS-6            | C22363833 | SMD        | 13,541 |

Notes:
- 74HC00 (SRAM `/CE` inverter + LPT NAND, re-bought for the 3.3V domain), 74HC04, 74HC32,
  74HC125, 74HC138, 74HC244, 74HC245 also got fresh 3.3V-domain LCSC picks in this pass
  (smaller-name fabs — MDD/Toshiba — since Nexperia-branded parts are thin/unstocked at
  those values); see `parts.py` for the exact entries, unchanged pinouts throughout.
- 74LVC161 and 74LVC574A are both thin (100/88 units) — re-check immediately before BOM
  lock, same as the existing TL16C550/DB25/MAX3241/TPS563200 thin-stock flags below.

## Socket policy (fab installs the socket, chip goes in by hand)

**2026-07-14 update:** the socket list shrank to the **V20 only** — the
AS6C4008 SRAM sockets are gone with that chip (→ IS62WV51216BLL SMD TSOP-44,
no socket) and the DS12C887 socket is gone with that chip (→ RTC emulated
+ SMD PCF8563). The COM UARTs also dropped their PLCC-44 socket: the
TL16C550CPFBR is a soldered TQFP-48 reflow part (thin JLC stock, C882798;
still not socketed).

| Component            | Socket (= its LCSC Part Num) | Chip source        |
|----------------------|------------------------------|--------------------|
| V20 (µPD70108)       | DIP-40 **machined** socket C2874018 | user stock (vintage) |
| Core2350B module ×2  | 2.54 mm female headers C2897411 | Waveshare (consign) |
| Pico module          | 2.54 mm female headers C2897411 | Raspberry Pi — official Pico stocked at JLC (C7203002, ~$8; Pico W C7203003) |

**Header caveat (found 2026-07-13):** C2897411 is specifically the
PM254-2-10-Z-8.5, a **2×10** female strip. That suits the Core2350B's
dual-row rings, but the Pico needs 2× **1×20** strips — pick a 1×N part
(same PM254 family) at order time.

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

The V20's DIP-40 socket is the machined-pin (round-hole) grade, verified
600 mil (15.24 mm) row spacing — ~$0.70–0.90 vs $0.06–0.12 stamped, worth it
for a vintage pin and repeated insertion. (Stamped fallback if the machined
part goes out of stock: C2332. The DIP-32/DIP-24 machined-socket picks for
the now-deleted AS6C4008/DS12C887 sockets — C2874017/C2684765 — are kept
here only as history; beware many catalog DIP-24/32 sockets are the NARROW
300 mil variant if either part ever comes back.)

**16550 socket choice — HISTORICAL (2026-07-03), superseded 2026-07-14:** the
board no longer sockets its UARTs. The original rationale (swappable UART for
~$0.39 + ~2 cm² per port, one footprint taking new TI silicon / NOS tubes /
vintage pulls) applied to a PLCC-44 16C550; the 3.3V redesign moved both COM
ports to a soldered 48-pin QFP instead (TL16C550CPFBR, C882798, since later
that day — thin JLC stock, see the thin-stock list below).

## Not available at JLCPCB (source elsewhere / consign)

- **8-bit ISA card-edge slot** (card_isatest J1) — 3.96 mm edge connector;
  consign or CONNFLY/EDAC from another distributor.
- **VGA HD15 (DE15) connector** (video card) — THT part from another
  distributor, or build the video card HDMI-only initially.
- **16C550 UART — RESOLVED (2026-07-14, later), moved to the thin-stock
  list.** The LQFP-48 PT revisions (TL16C550CPTR C181382, PTRG4 C2653207)
  remain at **0 units**, but the active **TL16C550CPFBR** (TQFP-48,
  **C882798**, 5 in stock, extended part) is pin-identical — verified
  against EasyEDA/`jlc_get_pinout` for C882798, all 48 pins including the 8
  NCs — and is now bound in `parts.py`. Still a **soldered SMD reflow part,
  not socketed**. A socketed PLCC-44 fallback (TL16C550CIFNR, C2653193)
  exists if a future revision wants sockets back.

## Network card (2026-07-12)

RTL8019AS NE2000 NIC soft-card sourcing pass (schematic from Tasks 1-3):

- **RTL8019AS**: bound to **C22465363** (~$19.5, 202 pcs on 2026-07-12). The
  cheaper alternative **C10016** (~$11) has only 4 pcs in stock — not enough
  for a build. Re-check both at order time.
- **RJ45 jack**: the upstream reference's part **C133529 is EOL** →
  swapped to **C386757** (Ckmtw R-RJ45R08P-C000).
- **Line-side CT caps**: 1nF/2kV 1206 (**C9196**), matching the upstream
  reference design.
- **New passives** (all basic library, verified live 2026-07-12): 27k
  (C22967), 1M (C22935), 200R (C8218), 20pF (C1648), 1nF (C1588).
- **Custom symbols pin-verified** against EasyEDA + datasheet on 2026-07-12:
  **RTL8019AS**, **AT93C46** (MAC EEPROM), **13F-39MNL** (RJ45 magnetics
  jack), **RJ45_LED** (the jack's integrated LEDs) — all four new
  hand-authored symbols this card needed.

## Passives audit (2026-07-14) — basic-library sweep + resistor arrays

Every discrete R and C value on the board audited against the JLC library:
all were already **basic** (the 27R USB terminator is "preferred" = also
fee-free) except three, resolved as follows:

- **Ferrite beads (x3, picogus AVDD + network)**: extended Murata
  BLM18KG101TN1D (100R@100MHz) -> **basic BLM18PG121SN1D, C14709**
  (120R@100MHz, 2A) -- same family/role, fee-free.
- **100uF SMD electrolytic (power, x2, C2887276)** and **2.2uH/4.8A buck
  inductor (power, C602029)**: stay extended -- JLC's fee-free library
  contains ZERO parts in either subcategory. Accepted cost of the buck.
- Pruned the orphaned 47nF/330nF entries (5V-era MAX3241 caps, unused
  since the 3.3V redesign).

**Pull consolidation**: 65 discrete 10k/4.7k rail pulls collapsed into 18
**basic** 4-element isolated arrays (RN refs): 10kx4 = 4D03WGJ0103T5E
C29718, 4.7kx4 = 4D03WGJ0472T5E C1980 (0603x4, R_Array_Convex_4x0603,
element k = pins k/9-k). Isolated elements, so packs mix rails; +-5%
tolerance is fine for pulls. Kept discrete: RC/divider/series roles, the
supervisor I2C pair + RUN, and singletons.

- **10k 0603 discrete (C25804): 0 stock at audit time and it is the ONLY
  basic 10k 0603** -- basics restock, but verify before ordering (only ~5
  discrete 10k remain on the board after the array conversion; the arrays
  themselves are 2.8M-deep).

## Thin stock — re-verify with jlc_stock_check before ordering

- **TL16C550CPFBR (C882798): 5 units — genuinely thin**, extended part;
  re-verify with `jlc_stock_check` before every order (fallback: TI
  direct/Mouser, where the PFB channel is healthy). Avoid eBay/AliExpress
  "16550" pulls — widely remarked/fake. 48-QFP pin numbers differ from the
  old PLCC/DIP-style symbol assumption — the `mini-xt:TL16C550PT` symbol
  uses TI's NO.PT column (SLLS177I Table 4-1), re-verified pin-for-pin
  against `jlc_get_pinout` for C882798 (PT and PFB share the pinout).
- DB25 male (C5400534): ~10 pcs — likely needs a substitute.
- MAX3241EEAI+T (C406859): ~175.
- TPS563200DDCR (C97253): down to **4 pcs** as of the 2026-07-11 review (was
  ~256 on 2026-07-03) — re-verify before any order; TPS563201DDCR (D-CAP2,
  different feedback network) or another 3A 5→3.3V buck is the fallback.
- RTL8019AS (C22465363): 202 pcs on 2026-07-12 — healthy for now, but the
  cheaper C10016 alt sits at only 4 pcs; re-verify before ordering.
- **74LVC161PW,118** (C548136, ÷3 clock divider): ~100 pcs. **74LVC574AT20-13**
  (C842658, LPT data latch): ~88 pcs. Both new 2026-07-14 picks — re-verify
  before BOM lock.

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

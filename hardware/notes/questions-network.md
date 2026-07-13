# Open questions -- network sheet (RTL8019AS NE2000 Ethernet)

## 1. PL[1:0] strap value -- 00 not 01
**Question:** The reference design docs paraphrase the mode as "link test
enabled" -- does that mean PL[1:0] = 01 (a literal "on" bit) or 00?
**Why:** The RTL8019AS datasheet's PL[1:0] table encodes four *modes*, not a
single on/off bit: 00 = 10BaseT with auto-detect (link test enabled), 01 =
10BaseT link test disabled (forced no-autodetect), 10 = AUI, 11 = reserved.
Naively picking "01 looks more like on" would be wrong.
**Options:** (a) PL=01 (disable link test, force 10BaseT); (b) PL=00
(10BaseT, auto-detect with link test).
**Pick:** (b) PL[1:0] = 00 -- matches the reference's actual strap and gives
normal link-test/auto-negotiate-adjacent behavior. Both pins are left open
(internal pull-down = 0), no strap resistors needed.

## 2. 93C46 MAC EEPROM: keep it, ship blank
**Question:** Populate U2 (AT93C46) at all, and if so, does it need to be
pre-programmed before the board is usable?
**Why:** The RTL8019AS reads its MAC address, and jumper-vs-EEPROM config
overrides, from this EEPROM at reset. Without it, the chip still works with
the hardwired strap configuration (JP=1 strap mode ignores most EEPROM
fields) but will report all-zero or garbage MAC bytes -- unusable on a real
network until programmed.
**Options:** (a) Omit the EEPROM, rely on straps only (loses MAC storage,
chip may still boot in strap-only mode with an invalid MAC); (b) populate it
and ship blank, program in the field.
**Pick:** (b) Populate U2, ship blank. Program once from DOS after assembly
with `RSET8019.EXE` (Realtek's Register/EEPROM setup utility, carried in the
Manawyrm ISA8019 repo's "Programming utilities" folder) or the repo's
`pg8019` equivalent -- same procedure the upstream board requires. This is a
one-time step, not a board defect.

## 3. LED default semantics (COL/RX vs LNK/ACT)
**Question:** LED0/LED1 are wired to J1's link/activity LEDs, but does the
RTL8019AS drive them as link/activity out of the box?
**Why:** The chip's LED pin function is configurable via EEPROM bits
LEDS0/LEDS1; the power-on default (before EEPROM is programmed) is the
legacy NE2000 COL/RX indication, not LNK/ACT. Silkscreening the LEDs as
"LNK"/"ACT" could be read as a hardware bug if they blink COL/RX instead.
**Options:** (a) Note the discrepancy as a known limitation; (b) note it and
point at the same fix (RSET8019) already needed for the MAC (Q2).
**Pick:** (b) -- documented via `sch.text` on the sheet. Once RSET8019 sets
LEDS0=1 during MAC programming, LED0/LED1 read out link/activity as wired.
Identical behavior to the real ISA8019; not a mini-xt-specific gap.

## 4. SMEMRB/SMEMWB wired despite no boot ROM
**Question:** With the boot-ROM socket omitted (see module docstring), should
SMEMRB/SMEMWB (the chip's memory-cycle strobes, needed only for boot-ROM
access) still be wired to the bus?
**Why:** They cost nothing to wire (faithful transcription of the reference's
pinout) and leaving them floating is worse practice than tying them to their
correct bus signals, even though the chip will never see a matching MEM
cycle in this configuration (BS0-4=00000 disables the ROM decode window).
**Options:** (a) Leave NC since functionally inert; (b) wire them anyway.
**Pick:** (b) -- wired to `~{MEMR}`/`~{MEMW}` per the reference netlist.
Inert with no boot ROM populated, zero cost, and keeps the transcription
faithful/complete if a future revision adds the ROM socket back.

## 5. RJ45 successor part (magjack)
**Question:** The reference's magjack (JLC part C133529) is EOL at JLCPCB --
what replaces it?
**Why:** A direct BOM substitution needs pin-for-pin compatibility,
including LED polarity (LA+/LA-/LB+/LB- anode/cathode sense), or the link/
activity LEDs wire up backwards.
**Options:** (a) Pick any similarly-priced RJ45-with-magnetics-and-LEDs part
and assume standard polarity; (b) verify the replacement's actual pinout
before trusting it.
**Pick:** (b) -- `mini-xt:RJ45_LED` (C386757) chosen as successor; LED
polarity (LA+/LA-, LB+/LB-) verified against EasyEDA's pin-name data for
that part rather than assumed identical to the EOL part.

## 6. EARTH / chassis net topology
**Question:** T1's line-side center taps (TXCT/RXCT) and J1's shield pins
land on a separate `EARTH` net rather than logic `GND` -- keep that
separation on this board?
**Why:** This is standard Ethernet magnetics practice (isolate chassis/earth
return from digital ground to reduce common-mode noise coupling into the
PHY), and it's how the upstream ISA8019 reference wires it: TDCT/RDCT (local
side) to GND, TXCT/RXCT (line side) + J1 shield through a single ferrite
bead to GND, keeping earth quasi-isolated at DC while still bonded at RF.
**Options:** (a) Simplify to one GND net board-wide; (b) carry the
upstream's GND/EARTH split through unchanged.
**Pick:** (b) -- carried over unchanged: TDCT/RDCT -> 1nF -> GND, TXCT/RXCT
-> 1nF/2kV -> EARTH (2 kV rating added post-review: barrier caps, as upstream), J1 SH1/SH2 -> EARTH, single FB1 ferrite bead EARTH -> GND.
A `power:PWR_FLAG` was added on EARTH (mirroring the picogus sheet's
AVDD_PGUS/AGND_PGUS idiom) since it's a locally-generated net with no other
driven source in isolated-sheet ERC.

## 7. RTL8019AS/EEPROM stay at +5V (2026-07-14, 3.3V single-board redesign, task 7)
**Question:** The task brief says "power sweep -> +3V3 for bus-facing logic"
-- does that include U1 (RTL8019AS) and U2 (AT93C46 EEPROM) themselves, or
only the glue (U3)?
**Why:** Checked the RTL8019AS datasheet: its D.C. characteristics are
specified at Vcc = 5V +-5%, with no documented 3.3V operating mode --
unlike the 74-series glue, this is a fixed real-world part with no
electrically-verified low-voltage operation (same category as MAX3241 on
com_port, which the brief explicitly keeps at +5V). U2 (AT93C46) is wired
directly to U1's EECS/EESK/EEDI/EEDO pins with no buffer between them, so it
must share U1's voltage domain to keep valid logic levels on that link.
**Options:** (a) Move U1/U2 to +3V3 per a literal reading of "power sweep
for bus-facing logic" (unverified, risks a part not actually rated for it);
(b) leave U1/U2 at +5V (same treatment as MAX3241), only convert the glue
that bridges U1's domain onto the shared 3.3V bus.
**Pick:** (b). U3 (IRQ/AEN gate) is the only chip converted --
`74LVC125A @ +3V3` (LVC specifically because its input, U1's INT0 pin, is a
5V signal). R6 (U3's own OE pull-up) moved to +3V3 to match U3's rail; R7
(AEN_CHIP park) -- see the Task-10 correction below (moved +5V -> +3V3).

**Task-10 correction -- R7 (AEN_CHIP park) moves +5V -> +3V3.** The original
pick parked AEN_CHIP to +5V "matching U1's domain," but AEN_CHIP does NOT feed
only U1: it also drives **U5's ~{E0}** (the 0x340-decode 74HC138 @ +3V3, added
in Q8). A +5V park would push that 3.3V-powered '138 input above its own rail.
+3V3 satisfies U1's AEN input either way -- the RTL8019AS AEN is a **5V-TTL
input (Vih 2.0V)**, so a 3.3V park reads as a valid logic high. So with JP1 open,
R7 now parks AEN_CHIP at 3.3V: U1 still sees "AEN high -> ignore all I/O" AND U5
is no longer over-driven. Netlist: R1307 (R7) pin2 -> +3V3; pin1 -> AEN_CHIP.
Every other 5V tie on this sheet (R1/R2/R8/R9 straps, U2's VCC/ORG, the bulk
decoupling row, C15) is directly wired to U1 or U2 and is unaffected.
**Correction (review fix, see Q8):** the original claim here -- that "5V
outputs are fine feeding 5V-tolerant inputs elsewhere on the 3.3V bus" -- is
TRUE only for U1's control outputs that pass through a 3.3V LVC stage (INT0
-> U3 -> IRQ2, and the AEN path). It is FALSE for U1's bidirectional SD0-7
data pins: those were wired directly to the shared D0-7 bus, which also
reaches the RP2040/PicoGUS GPIOs -- and the RP2040 is NOT 5V-tolerant. During
a NIC I/O read U1 would drive 5V onto those pins. Fixed in Q8; every 5V
signal U1 puts on the shared bus now passes through a 3.3V buffer.

## 8. RTL8019AS 5V data bus isolated behind a gated LVC245 (review fix, 2026-07-14)
**Finding (reviewer-verified, Critical):** U1's bidirectional SD0-7 pins were
wired DIRECTLY to the shared 3.3V bus D0-7. The RTL8019AS is a 5V-only part
(Q7); during a read of its 0x340 I/O window it drives 5V TTL onto D0-7, which
also feed the RP2040/PicoGUS GPIOs -- and the RP2040 is NOT 5V-tolerant. The
old Q7 comment claiming "5V outputs are fine on the shared bus" was wrong for
the data path (corrected above). Everything else on the sheet was clean: the
SA/strobes are NIC inputs, AEN and INT0 are isolated via U3 (74LVC125A), and
IOCHRDY is open-drain with a 3.3V pull-up.

**Fix:** insert U4, a 74LVC245A powered at +3V3 (5V-tolerant B-side faces U1's
5V SD pins; A-side outputs only ever swing 0-3.3V), between U1's SD0-7 (now on
private nets SD0_NIC..SD7_NIC) and the shared D0-7. Same idiom as storage.py
U8 / cpu_core.py U5.

**Enable gating -- need our own 0x340 decode.** Unlike storage's IDE (external
chip-selects), the RTL8019AS decodes its I/O window *internally* and exposes no
"selected" pin, so U4's ~OE needs its own copy of that decode -- otherwise a
B->A direction on any *other* card's I/O read would drive floating NIC pins
onto the bus (contention). Added U5, one 74HC138 (all inputs 3.3V-driven, HC
value override like storage/cpu_core), decoding the 10-bit ISA I/O address
0x340 (A9..A5 = 1 1 0 1 0, A4..A0 selected inside the NIC):
  * sel C,B,A = A8,A7,A6  -> 101 = ~Y5
  * ~E1 = AEN_CHIP  (enabled when AEN low; parks OFF when JP1 open, so the
                     whole NIC path -- IRQ, chip AEN, AND now the data bus --
                     releases together)
  * ~E2 = A5  (enabled when A5 = 0)
  *  E3 = A9  (enabled when A9 = 1)
  => ~Y5 low  <=>  A9.A8.~A7.A6.~A5.~AEN_CHIP  =  I/O access in 0x340-0x35F.
~{NIC_SEL} = ~Y5 -> U4 CE (~OE). So U4 is Hi-Z on both sides whenever the NIC
is not the addressed target: no bus contention, full release when JP1 open.

**DIR truth table** (mini-xt 74HCT245 pin 1 is literally named "A->B"; high =
A->B -- verified via `pins.py mini-xt:74HCT245` + datasheet). DIR pin wired
directly to ~{IOR}:
  | ~{IOR} | DIR pin | direction | when                          |
  |--------|---------|-----------|-------------------------------|
  | 1      | high    | A -> B    | write / idle: bus drives NIC  |
  | 0      | low     | B -> A    | read: NIC drives bus          |
The transient where the NIC is addressed but IOR is still high just has the
(floating, read-cycle) bus drive the NIC's SD *inputs* harmlessly; the NIC
only latches on IOW, and only drives on IOR low. Standard bidirectional-buffer
behavior.

**~OE choice: ~{NIC_SEL} (the decode), NOT tied to GND.** Tying ~OE=GND would
leave DIR=~{IOR} flipping the buffer to B->A on *every* I/O read, driving the
bus from floating NIC pins during other cards' reads. Gating ~OE with the
window decode is the robust choice and matches storage.py U8's ~{DBUF_OE}
pattern. AEN/DMA: the RTL8019AS is programmed-I/O only (no ISA DMA), so
AEN-high (third-party DMA) correctly disables U4 -- the NIC is never a DMA
data source. Timing: one LVC245 (~4 ns) in the read path is negligible vs ISA
I/O timing.

**Minor (same commit):** the gensym.py RTL8019AS symbol modeled IOCHRDY and
INT0 as plain "output"; changed to open_collector (IOCHRDY is open-drain with
a 3.3V pull-up) and tri_state (INT0). The symbol is generated by gensym.py and
regeneration is byte-stable, so this is a clean 2-line change (dropped one ERC
driver-conflict: 12 -> 11 violations).

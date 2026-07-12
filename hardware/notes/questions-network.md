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

# Open questions -- power sheet

## 1. CC strategy: discrete 5.1k Rd vs. CH224K (both drawn)
**Question.** The board only needs 5 V. A Type-C sink can pull up to 3 A at 5 V
with nothing but the two mandatory 5.1 k Rd pulldowns on CC1/CC2. The CH224K PD
sink is the *optional* upgrade that guarantees a 5 V/3 A contract from PD-only
sources. These two are not normally populated together: the CH224K manages the
CC lines itself, so discrete Rd resistors on the same nets are redundant.

**Decision (proceeding).** Draw both so either build is buildable from one
schematic: R1/R2 (5.1 k) are the cheap no-silicon baseline; U1 (CH224K) is the
guaranteed-contract option. R1/R2 are marked for DNP-when-CH224K-populated in the
text note. Confirm at layout which variant is the default stuff option.

## 2. CH224K CFG1 voltage-select strap value
**Question.** CH224K selects the requested PD voltage via the CFG1/CFG2/CFG3
straps (resistor-to-GND code per the WCH datasheet table). The exact code for a
fixed 5 V profile must be read off that table.

**Decision (proceeding).** R3 ties CFG1 to GND as the 5 V-select strap and is
marked "DNP" pending the datasheet value (5 V is also the Type-C default, so an
open CFG1 is a safe fallback); CFG2/CFG3 left unconnected. Confirm the resistor
code against the CH224K datasheet before fab.

## 3. Buck regulator part choice
**Question.** Design doc S13 asks for a 5 V -> 3.3 V buck but names no part.

**Decision (proceeding).** Used `Regulator_Switching:TPS563200` -- a 3 A, 580 kHz
synchronous buck with a 0.768 V reference, which exists in the stock KiCad library
and comfortably covers the 4-MCU + USB load. Feedback divider 33k/10k gives
0.768 * (1 + 33/10) = 3.30 V. L1 = 2.2 uH and the 22 uF in/out caps are typical
starting values; verify against the final 3.3 V current budget and the chosen
device's datasheet (inductor ripple, output cap ESR/stability).

## 4. 3.3 V current budget not yet fixed
The four MCUs (2x RP2350B, RP2040 supervisor, PicoGUS RP2040) plus USB logic set
the 3.3 V rail current; design doc S16 lists "3.3 V buck current for 4 MCUs" as an
open item. The TPS563200 (3 A) was picked with margin, but resize the inductor and
output caps once the budget is fixed.

---
**Correction (2026-07-03, design review H1):** the CFG1-strap answer above was
wrong — CH224K CFG1 must be left OPEN for 5 V (internal pull-up); ANY resistor
to GND selects the 9/12/15/20 V rows and would put >=9 V on the +5V rail. R3
has been removed from power.py; CFG1 is no-connect with a warning note.

## 5. Input/rail protection added (design review 2026-07-11)
VBUS now enters through F1 (3A-hold 1812 polyfuse) with an SMBJ5.0A TVS on +5V;
the sidecar +5V feed gets its own 2A polyfuse + SMBJ5.0A + 22uF bulk on the
+5V_ISA side (a misbehaving ISA card trips its own fuse instead of dropping the
board, and a back-fed voltage is clamped). Reverse polarity needs no diode --
USB-C connector geometry excludes it. CH224K gains a local 1uF VDD cap; its PG
(open-drain, pulled to +3V3) is now routed to the Supervisor as PD_PG (GPIO16)
so firmware can tell whether the 5V/3A contract succeeded. Buck output doubled
to 2x22uF per TPS563200 datasheet; 10uF added at VIN; one extra 22uF bulk on +5V.

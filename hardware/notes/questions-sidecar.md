# questions-sidecar — SUPERSEDED

The original contents of this file described the first-cut 64-pin sidecar
header (IRQ10/11/14, pin-63 key). That design was replaced by the shared
standard-pinout **60-pin 8-bit ISA header** in `sheets/isa_conn.py` — see
`open-questions.md` ("ISA connector re-based on the standard 8-bit ISA
pinout") for the current pin map and rationale:

- pins 7 / 11 / 15 reclaimed as ~IOCHCK / GND / IRQ8; pin 35 = REFRESH#
- IRQ10/11/14 dropped (not on an 8-bit edge); a sidecar COM4 uses the bus
  IRQ2 line, delivered as IRQ9 via the AT redirect (design doc §11.1/§14)

---

# sidecar sheet -- design decisions (task 9: buffered expansion port)

The sidecar sheet became the 3.3V board's ONLY real-ISA attachment point: an
isolation/buffer bank (LVC: 5V-tolerant in, 3.3V-TTL out) between the internal
bus and an external 60-pin ISA header. Decisions made while under-specified:

## Q1 -- EXT_IRQ8 has no header source

**Why:** bus_mcu (task 5) declares `EXT_IRQ2..8` (7 nets), but the isa_conn
header only carries IRQ2..7 (6 lines): pin 15, formerly IRQ8, was reclaimed to
GND when the RTC moved on-board (IRQ8 is now the RTC's private push-pull net,
per isa_conn's docstring). So there is no `X_IRQ8` to buffer.

**Options:** (a) invent an X_IRQ8 pin on the header; (b) leave EXT_IRQ8 driven
only by bus_mcu's own idle pull-down.

**Pick:** (b). Adding an IRQ8 header pin would break the standard 8-bit ISA
pinout (the whole point of isa_conn). bus_mcu already fits a 10k pull-down on
every EXT_* line (R29..R35), so EXT_IRQ8 reads idle-low with no sidecar node --
correct and harmless. The inbound bank therefore buffers 6 IRQ + 3 DRQ = 9
lines (2x 74LVC244A, one channel spare).

## Q2 -- Data transceiver direction / power-on safety

**Why:** the brief requires the data '245 (`U6`) to default to a bus-safe
direction before the Bus MCU boots and drives EXP_DDIR (GPIO43).

**Pick:** verified from pins.py + 74LVC245A datasheet that pin 1 ("A->B") is
DIR with **DIR=H => A->B**. A-side = internal D0..D7, B-side = X_D0..X_D7, so
DIR=H = internal->external = OUTBOUND. R1 (10k) pulls EXP_DDIR **HIGH**, so the
port is outbound-safe during the MCU-Hi-Z window (it presents internal read data
to a card; it never drives inward into the internal bus uninvited). `~OE` (pin
19 CE) is tied GND = always enabled -- direction is the only safety here, owned
by EXP_DDIR firmware policy. Truth table stated in the sheet comment.

**Limitation (documented in sch.text):** external BUS-MASTER cards are NOT
supported -- there is no port arbitration, only the Bus MCU's fixed direction
choice. Contention with a card that also drives the data lines is prevented
solely by firmware setting EXP_DDIR inward before letting a card decode a read.

## Q3 -- IOCHRDY / ~{IOCHCK} return path (open-drain, no separate 2G07 symbol)

**Why:** these two lines must come back from a card and pull the INTERNAL net
low without ever contending with the internal driver (wired-AND).

**Pick:** one 74LVC2G07 (dual non-inverting OPEN-DRAIN buffer) -- `U9`. It has
no dedicated symbol; per parts.py it rides the `mini-xt:74LVC2G06` body with a
value override "74LVC2G07" (pin-identical SOT-23-6). Gate1: X_IOCHRDY ->
IOCHRDY; gate2: X_~{IOCHCK} -> ~{IOCHCK}. 10k pull-UPS on the X_ side so an
unplugged port reads inactive-high; the open-drain outputs float (hi-Z) unless
a card pulls its X_ line low. Deviation comment added at the placement.

## Q4 -- Inbound pull-downs vs. bus_mcu pull-downs

**Why:** the brief asks for 100k pull-DOWNs on every X_ inbound input; bus_mcu
already pulls the EXT_* nets low.

**Pick:** kept both. The bus_mcu pull-downs hold EXT_* defined when no sidecar
is stuffed; the sidecar's 100k pull-downs hold the '244 INPUTS (X_ side) defined
when the header is unplugged (input floats otherwise -> the buffer would pass
noise onto EXT_*). Different nets, both needed.

## PINS surgery

Built a filtered COPY of `isa_conn.ISA_PINS` (never mutated -- card_video /
card_isatest import it unchanged). Dropped every IRQ*/DRQ* (now buffered onto
private EXT_*); kept IOCHRDY / ~{IOCHCK} (our 2G07s drive the internal nets);
added the PRIV_EXP pins (EXP_DDIR input, EXT_* outputs, verbatim from mxbus).

## Q5 -- floating inputs on the always-enabled '244s (Task-10 fix)

**Finding (reviewer-verified):** `buf244()` only wired the channels it was
handed, so the partially-filled '244s left their unused **A inputs floating** on
the real chip -- and these '244s are ALWAYS enabled (both ~OE = GND), so a
floating CMOS input is a real hazard (oscillation / crowbar current), not just
ERC noise. Two banks were short: the outbound command-strobe '244 U5 (10 strobes
across 2 chips -> U5 carries 2, **6 spare channels**) and the inbound IRQ/DRQ
'244 U8 (9 lines across 2 chips -> U8 carries 1, **7 spare channels**).

**Pick:** for every unused channel, tie the **A input to GND** and **no_connect
the Y output** -- the same convention bus_mcu uses for its spare '165/'244 pins.
Done generically inside `buf244()` (loop `range(len(pairs), 8)`), so it also
covers any future short bank. Netlist (post-fix): the only remaining
`unconnected-(U1105-* / U1108-*` nets are the deliberately-NC'd **Y outputs**;
**zero A-input pads float** -- all A pads (U1105: 6, U1108: 7) are on GND.

## 50-pin header + port DMA channel (2026-07-14, user decision)

Three linked changes, decided together:

1. **Header 60-pin (2x30) -> 50-pin (2x25).** 50-way IDC ribbons/headers are
   far easier to source than 60-way. Cost: the pinout is now PROJECT-PRIVATE
   (the 60-pin layout mirrored the PicoGUS `Bus_ISA_8bit` standard-edge
   arrangement). The pin budget forced two signal drops -- 47 signals +
   one +5V + two GND = 50 exactly:
   - **OSC (14.318 MHz) dropped.** No on-board consumer (cpu_core's U15 '125
     OSC re-buffer gate freed; OSC left mxbus/cpu_core PINS). A real CGA card
     would want it for colorburst -- the planned **ISA backplane expansion
     board** re-creates it locally.
   - **~{REFRESH} dropped.** No DRAM-refresh support on the port; DRAM-based
     ISA cards are the only casualty (also backplane-recoverable). This freed
     Bus MCU **GPIO47**, which is exactly what the DACK below needed.
   - BALE KEPT (the video sheet senses it; a standalone video card would take
     it from this header). TC KEPT (DMA lives, see below).
2. **Port DMA re-added as ONE channel: EXT_DRQ / ~{EXT_DACK}** (pins 9/13,
   header names DRQ / ~{DACK}). EXT_DRQ rides the inbound '244's spare channel
   onto the '165 collector's spare D6 lane (zero GPIO); ~{EXT_DACK} = GPIO47
   out through the strobe '244's spare channel (7 of 8 used). Deliberately
   SEPARATE nets from the internal PicoGUS pair -- the false-trigger hazard
   that motivated NCing the old DACK pins stays solved.
3. **DRQ1/~{DACK1} renamed DRQ/~{DACK}** (mxbus, bus_mcu, picogus): ch2/3 are
   long retired, so the suffix carried no information.

Also that day: **card_video + card_isatest deleted** (sheets, hardware/cards/,
build_cards(), the parts.py ISA-edge-slot entry). Long-term plan is the ISA
backplane board on this port; git history has the last card versions.

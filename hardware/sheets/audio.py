"""audio -- PC-speaker + op-amp summer -> line-out (PicoGUS line-in stub).

Design doc S9. The PicoGUS card itself is OUT OF SCOPE for this board: this sheet
is only the simple analog back end that doc S9 calls for -- "PicoGUS line-out is
summed with the PC-speaker signal in a simple op-amp summer -> line-out jack".

Signal path (single +5V supply, so a Vref = +2.5V virtual ground is used):
  * SPKR (PIT ch2 tone as a PWM square wave from the Bus MCU) arrives as the one
    interface net. It is reconstructed with an RC low-pass (R_PWM / C_PWM) and
    AC-coupled (C_SPKR) before mixing.
  * The (absent) PicoGUS analog line-out enters on J1, a 1x3 header stub
    (L / R / GND). Each channel is AC-coupled (C_PGL / C_PGR).
  * A TL072 (unit A) forms one inverting unity summer:
      OUT = -(SPKR + PicoGUS_L + PicoGUS_R)
    Non-inverting input sits on VREF; feedback = 10k, summing resistors = 10k.
    (Mono mix -- the build harness instantiates only unit 1 of a multi-unit
    symbol, so the second op-amp half cannot be placed independently; see
    notes/questions-audio.md. Unit B is left unused.)
  * The mono output is AC-coupled (C_OUT) and driven to both tip and ring of J2,
    the stereo line-out jack (TRS: tip=L, ring=R, sleeve=GND).

Interface is intentionally minimal: SPKR (in) + GND. Everything else (the PicoGUS
header, the line-out jack, Vref) is local to this sheet. No ISA or private nets
are touched, so the isolation contract is trivially satisfied.

Substitutions (no exact KiCad symbol available -- see notes/questions-audio.md):
  * line-out jack and PicoGUS line-in both use Connector_Generic:Conn_01x03
    (no Connector_Audio / AudioJack library is installed).
  * LM386 small-speaker amp omitted (no LM386 symbol installed); line-out only.
"""
import mxbus
from mxbus import pin

NAME = "audio"
TITLE = "Audio -- PC-speaker + op-amp summer -> line-out (PicoGUS line-in stub)"

PINS = [pin("SPKR", "input"), pin("GND", "power_in")]


def build(sch, lib):
    L = lambda c, p, net, **k: sch.net(c, p, net, kind="label",
                                       dx=k.get("dx", 2.54), dy=k.get("dy", 0))

    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ---- helpers for the two passive families (Device:R / Device:C, pins 1/2) ----
    def res(ref, val, at, na, nb):
        r = sch.place("Device:R", ref, val, at=at)
        sch.net(r, "1", na, kind="label", dx=0, dy=-2.54)
        sch.net(r, "2", nb, kind="label", dx=0, dy=2.54)
        return r

    def cap(ref, val, at, na, nb):
        c = sch.place("Device:C", ref, val, at=at)
        sch.net(c, "1", na, kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", nb, kind="label", dx=0, dy=2.54)
        return c

    # ---------------- virtual-ground reference (+2.5V) ----------------
    # single-supply op-amp bias: 10k/10k divider off +5V, bypassed.
    res("R1", "10k", (50.8, 76.2), "+5V", "VREF")
    res("R2", "10k", (50.8, 109.22), "VREF", "GND")
    cap("C1", "10uF", (76.2, 109.22), "VREF", "GND")    # VREF bypass

    # ---------------- PC-speaker conditioning (SPKR PWM -> SPKR_AC) ----------------
    # reconstruct the tone from the PWM square wave, then AC-couple.
    res("R3", "1k",   (50.8, 165.1), "SPKR", "SPKR_F")  # RC low-pass series R
    cap("C2", "10nF", (76.2, 198.12), "SPKR_F", "GND")  # RC low-pass shunt C
    cap("C3", "1uF",  (101.6, 165.1), "SPKR_F", "SPKR_AC")  # AC-couple into summer

    # ---------------- PicoGUS line-in header stub (J1: L / R / GND) ----------------
    # NOTE: PicoGUS card is NOT on this board -- this is just the input header it
    # would drive. Pin 1 = Left, pin 2 = Right, pin 3 = GND.
    J1 = sch.place("Connector_Generic:Conn_01x03", "J1", "PicoGUS_LineIn", at=(50.8, 228.6))
    L(J1, "1", "PG_L", dx=-2.54)
    L(J1, "2", "PG_R", dx=-2.54)
    L(J1, "3", "GND",  dx=-2.54)
    sch.text("J1: PicoGUS line-out (card not on board)", (38.1, 246.38))
    cap("C4", "1uF", (101.6, 215.9), "PG_L", "PG_L_AC")  # AC-couple L
    cap("C5", "1uF", (101.6, 241.3), "PG_R", "PG_R_AC")  # AC-couple R

    # ---------------- TL072 unit A: inverting unity summer (mono mix) ----------------
    U1 = sch.place("mini-xt:TL072", "U1", at=(177.8, 152.4))
    L(U1, "8", "+5V", dx=2.54, dy=2.54)   # V+
    L(U1, "4", "GND", dx=-2.54, dy=-2.54) # V-
    # Power pins 8 (V+) and 4 (V-) live in the TL072's separate power unit, which
    # the build harness does not instantiate (it places unit 1 only). They are
    # therefore wired implicitly: +5V on pin 8, GND on pin 4, with C6 decoupling
    # at the part. See notes/questions-audio.md.
    cap("C6", "100nF", (203.2, 101.6), "+5V", "GND")  # supply decoupling
    # unit A: pin 1 = out, pin 2 = -in (summing junction), pin 3 = +in
    L(U1, "3", "VREF", dx=-2.54)                       # +in -> virtual ground
    L(U1, "2", "SUM",  dx=-2.54, dy=2.54)             # summing junction (-in)
    L(U1, "1", "OUT",  dx=2.54)                        # output
    res("R4",  "10k", (127, 127),   "SPKR_AC", "SUM")  # spkr -> summer
    res("R5",  "10k", (152.4, 127), "PG_L_AC", "SUM")  # picogus L -> summer
    res("R10", "10k", (152.4, 177.8), "PG_R_AC", "SUM")  # picogus R -> summer
    res("R6",  "10k", (203.2, 127), "SUM",     "OUT")  # feedback
    cap("C7", "10uF", (228.6, 127), "OUT",     "LINE") # output AC-couple
    # (unit B -- pins 5/6/7 -- intentionally unused: see module docstring.)

    # ---------------- stereo line-out jack (J2: tip=L, ring=R, sleeve=GND) ----------------
    # mono mix driven to both channels.
    J2 = sch.place("Connector_Generic:Conn_01x03", "J2", "LineOut_TRS", at=(266.7, 152.4))
    L(J2, "1", "LINE", dx=2.54)
    L(J2, "2", "LINE", dx=2.54)
    L(J2, "3", "GND",  dx=2.54)
    sch.text("J2: line-out jack (TRS: tip=L ring=R sleeve=GND)", (254, 170.18))

"""audio -- PC-speaker + PicoGUS line-out op-amp summer -> line-out.

Design doc S9. The PicoGUS is now on-board (picogus.py sheet), driving PG_L
and PG_R directly (its jack-node mix, post-M62429 volume control).

Signal path (single +5V supply, so a Vref = +2.5V virtual ground is used):
  * SPKR (PIT ch2 tone as a PWM square wave from the Bus MCU) arrives as an
    interface net. It is reconstructed with an RC low-pass (R_PWM / C_PWM) and
    AC-coupled (C_SPKR) before mixing.
  * PG_L and PG_R (PicoGUS post-mix, post-volume) arrive as interface nets from
    the picogus sheet. Each channel is AC-coupled (C4 / C5).
  * An MCP6002 (unit A) forms one inverting unity summer. (RRIO part chosen
    because the supply is a single +5 V with a +2.5 V virtual ground: a TL072
    needs >= +-5 V and its JFET input CM range excludes (V-)+4 V, i.e. it is out
    of spec on both counts here. The MCP6002 pinout is identical to the TL072
    dual-op-amp body, so the mini-xt:TL072 symbol is reused with a value
    override -- same pattern as the 74LVC245A.)
      OUT = -(SPKR + 0.5*PicoGUS_L + 0.5*PicoGUS_R)
    Non-inverting input sits on VREF; feedback = 10k; SPKR sums at 10k (1x),
    PG_L/PG_R at 20k (0.5x each, headroom: a unity L+R sum of correlated
    content would exceed the MCP6002's swing on the +5V rail).
    (Mono mix -- unit B is unused and parked as a follower on VREF.)
  * The mono output is AC-coupled (C_OUT) and driven to both tip and ring of J2,
    the stereo line-out jack (TRS: tip=L, ring=R, sleeve=GND).

Interface: SPKR (in), PG_L (in), PG_R (in), + GND (power_in). The line-out jack
and virtual-ground bias network are local to this sheet. No ISA or private nets
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

PINS = [pin("SPKR", "input"), pin("PG_L", "input"), pin("PG_R", "input"),
        pin("GND", "power_in")]


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

    # ------------- PicoGUS line-level inputs (AC-coupled from picogus sheet) ----------
    cap("C4", "1uF", (101.6, 215.9), "PG_L", "PG_L_AC")  # AC-couple L
    cap("C5", "1uF", (101.6, 241.3), "PG_R", "PG_R_AC")  # AC-couple R

    # ------------- MCP6002 unit A: inverting unity summer (mono mix) -------------
    # RRIO single-supply part (TL072 is out of spec at +5V single-supply / 2.5V CM);
    # identical pinout, so the TL072 symbol body carries a value override.
    U1 = sch.place("mini-xt:TL072", "U1", "MCP6002", at=(177.8, 152.4))
    L(U1, "8", "+5V", dx=2.54, dy=2.54)   # V+
    L(U1, "4", "GND", dx=-2.54, dy=-2.54) # V-
    # Power pins 8 (V+) and 4 (V-) live in the TL072's separate power unit, which
    # the build harness does not instantiate (it places unit 1 only). They are
    # therefore wired implicitly: +5V on pin 8, GND on pin 4, with C6 decoupling
    # at the part. See notes/questions-audio.md.
    cap("C6", "100nF", (203.2, 101.6), "+5V", "GND")  # supply decoupling
    # unit A: pin 1 = out, pin 2 = -in (summing junction), pin 3 = +in
    L(U1, "3", "VREF", dx=-2.54)                       # +in -> virtual ground
    # SUM stub stays on pin 2's own row (a dy bend would land on pin 5's stub
    # endpoint now that unit B is wired, silently merging SUM with VREF)
    L(U1, "2", "SUM",  dx=-5.08)                       # summing junction (-in)
    L(U1, "1", "OUT",  dx=2.54)                        # output
    # PG_L/PG_R at 20k = 0.5x each: the PCM5102A is 2.1 Vrms/channel full-scale,
    # and a unity L+R sum of correlated (mono-ish) content would demand ~+-6 Vpk
    # from an op-amp with ~+-2.5 V of swing around VREF. 0.5x keeps the worst
    # case inside the rails; SPKR stays 1x (small square wave after the RC).
    res("R4",  "10k", (127, 127),   "SPKR_AC", "SUM")  # spkr -> summer (1x)
    res("R5",  "20k", (152.4, 127), "PG_L_AC", "SUM")  # picogus L -> summer (0.5x)
    res("R10", "20k", (152.4, 177.8), "PG_R_AC", "SUM")  # picogus R -> summer (0.5x)
    res("R6",  "10k", (203.2, 127), "SUM",     "OUT")  # feedback
    res("R7",  "100", (241.3, 127),   "OUT",     "OUT_R")  # series isolation into the cable
    cap("C7", "10uF", (228.6, 127), "OUT_R",   "LINE") # output AC-couple
    # bleed on the jack side of C7: without a DC path the LINE node floats and
    # C7 charges through whatever gets plugged in -- an audible pop every time.
    res("R8", "100k", (254.0, 101.6), "LINE", "GND")
    # unit B (pins 5/6/7) is unused: park it as a follower on VREF -- floating
    # CMOS op-amp inputs can oscillate and pollute the shared +5V supply.
    L(U1, "5", "VREF", dx=-2.54)                       # +in B -> virtual ground
    L(U1, "6", "UB_FB", dx=-2.54, dy=2.54)             # -in B ...
    L(U1, "7", "UB_FB", dx=2.54)                       # ... = out B (follower)

    # ---------------- stereo line-out jack (J2: tip=L, ring=R, sleeve=GND) ----------------
    # mono mix driven to both channels.
    J2 = sch.place("Connector_Generic:Conn_01x03", "J2", "LineOut_TRS", at=(266.7, 152.4))
    L(J2, "1", "LINE", dx=2.54)
    L(J2, "2", "LINE", dx=2.54)
    L(J2, "3", "GND",  dx=2.54)
    sch.text("J2: line-out jack (TRS: tip=L ring=R sleeve=GND)", (254, 170.18))

"""Sidecar -- buffered/isolated 5V-compatible ISA expansion port (S4.3).

On the 3.3V single board this sheet is the board's ONLY real-ISA attachment
point.  It is an isolation/buffer bank between the internal 3.3V bus and an
external 60-pin (2x30) ISA header, so real 5V ISA cards can be driven and read
without damaging the 3.3V logic:

  * The header (isa_conn building block, standard 8-bit ISA pinout) presents its
    bus-side nets as PORT-LOCAL nets (prefix "X_", e.g. X_A0, X_D3, X_IRQ5) via
    place_header(remap=...).  Nothing internal touches the raw external pins.
  * Between X_* and the internal bus sit LVC buffers (74LVC245A / 74LVC244A):
    5V-TOLERANT inputs, 3.3V-TTL-legal outputs.  Outbound (internal -> X_) lines
    are DIR-strapped one way; inbound status/IRQ/DRQ lines feed dedicated EXT_*
    nets (never the internal IRQ/DRQ nets -- see mxbus.PRIV_EXP), so a floating
    external line can't fight an internal driver.  IOCHRDY / ~{IOCHCK} come back
    through open-drain gates (wired-AND, no contention).

LIMITATION: the data transceiver has a FIXED, firmware-chosen direction
(EXP_DDIR from the Bus MCU).  External BUS-MASTER cards (a card driving the ISA
bus itself) are NOT supported -- there is no request/grant arbitration to the
port, only the Bus MCU's direction policy.  The port always presents internal
read data outward by default; contention with a card that also drives the data
lines is prevented only by firmware setting EXP_DDIR inward before it lets a
card decode a read.

The +5V feed is fused (2A polyfuse) + TVS-clamped (SMBJ5.0A) so a shorted or
misbehaving card trips its own fuse instead of dropping the board rail.
Header power pins are ~3A each; keep daisy-chains to 2-3 cards.
"""
import mxbus
from mxbus import pin
import isa_conn

NAME = "sidecar"
TITLE = "Sidecar -- buffered 5V-compatible ISA expansion port"

# --- Sheet interface (PINS surgery, task-9 brief) -----------------------------
# Start from the full ISA contract, but the inward IRQ/DRQ lines no longer pass
# straight through: they are buffered onto the private EXT_* nets instead, so
# they LEAVE the ISA pin list here.  IOCHRDY / ~{IOCHCK} STAY (our open-drain
# gates drive the internal nets).  The PRIV_EXP pins are ADDED.
# NOTE: build a filtered COPY -- never mutate isa_conn.ISA_PINS (other cards
# import it unchanged).
_INWARD = ("IRQ", "DRQ")   # buffered to EXT_*, not passed through
_KEEP = [p for p in isa_conn.ISA_PINS
         if not p["name"].startswith(_INWARD)]
PINS = _KEEP \
    + [pin("EXP_DDIR", "input")] \
    + [pin(n, "output") for n in mxbus.PRIV_EXP if n != "EXP_DDIR"]

# Signal groups (canonical mxbus spellings) --------------------------------
_ADDR = mxbus.ADDR                                             # A0..A19
_OUT245 = _ADDR + ["BALE", "AEN", "CLK", "OSC"]                # 24 = 3x '245
_OUT244 = ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}",           # 10 = 2x '244
           "RESET_DRV", "TC",
           "~{DACK1}", "~{DACK2}", "~{DACK3}", "~{REFRESH}"]
# inward lines actually present on the header (IRQ8 was dropped for the on-board
# RTC, so only IRQ2..7 exist here; EXT_IRQ8 was formally retired 2026-07-14 --
# its '165 lane on bus_mcu ties low).
_INBOUND = [p["name"] for p in isa_conn.ISA_PINS
            if p["name"].startswith(_INWARD)]                   # 6 IRQ + 3 DRQ


def _chunk(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def build(sch, lib, expose=True):
    if expose:
        mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # -- helpers ---------------------------------------------------------------
    def buf245(ref, at, pairs, dir_net):
        # 74LVC245A: pin1 "A->B" = DIR (H => A->B), pin19 CE = ~OE.
        u = sch.place("mini-xt:74HCT245", ref, "74LVC245A", at=at)  # value=245 -> parts.py
        for i, (a, b) in enumerate(pairs):
            sch.net(u, "A%d" % i, a, kind="label", dx=-2.54)
            sch.net(u, "B%d" % i, b, kind="label", dx=2.54)
        sch.net(u, "1", dir_net, kind="label", dy=-2.54)   # DIR
        sch.net(u, "CE", "GND", kind="label", dy=2.54)     # ~OE tied enabled
        sch.net(u, "VCC", "+3V3", kind="label", dx=2.54, dy=-2.54)
        sch.net(u, "GND", "GND", kind="label", dx=-2.54, dy=2.54)
        return u

    def buf244(ref, at, pairs):
        # 74LVC244A: two 4-bit banks, 1OE(pin1)/2OE(pin19) tied enabled (GND).
        u = sch.place("mini-xt:74HCT244", ref, "74LVC244A", at=at)
        for i, (inn, out) in enumerate(pairs):
            g, k = i // 4 + 1, i % 4
            sch.net(u, "%dA%d" % (g, k), inn, kind="label", dx=-2.54)
            sch.net(u, "%dY%d" % (g, k), out, kind="label", dx=2.54)
        # These '244s are ALWAYS enabled (both ~OE = GND), so any unused channel's
        # A input must not float on the real chip -- tie it GND, NC its Y output
        # (same convention as bus_mcu's spare '165/'244 pins). Fixes the floating
        # A-input pads flagged on U5 (6 spare) and U8 (7 spare) in review.
        for i in range(len(pairs), 8):
            g, k = i // 4 + 1, i % 4
            sch.net(u, "%dA%d" % (g, k), "GND", kind="label", dx=-2.54)
            sch.no_connect(u.pin_xy("%dY%d" % (g, k)))
        sch.net(u, "1OE", "GND", kind="label", dy=-2.54)
        sch.net(u, "2OE", "GND", kind="label", dy=2.54)
        sch.net(u, "VCC", "+3V3", kind="label", dx=2.54, dy=-2.54)
        sch.net(u, "GND", "GND", kind="label", dx=-2.54, dy=2.54)
        return u

    def pull(ref, net, rail, at, val):
        r = sch.place("Device:R", ref, val, at=at)
        sch.net(r, "1", net, kind="label", dy=-2.54)
        sch.net(r, "2", rail, kind="label", dy=2.54)

    def decouple(ref, at):
        c = sch.place("Device:C", ref, "100nF", at=at)
        sch.net(c, "1", "+3V3", kind="label", dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dy=2.54)

    # -- Outbound address/timing: 3x 74LVC245A, DIR strapped OUTWARD -----------
    # DIR pin (pin1 "A->B") high => A(internal) -> B(external); A-side is the
    # internal bus, B-side is X_.  Tied +3V3 = permanently outbound.  ~OE=GND.
    for n, chunk in enumerate(_chunk(_OUT245, 8)):
        pairs = [(s, "X_" + s) for s in chunk]
        buf245("U%d" % (n + 1), (63.5, 45.72 + n * 63.5), pairs, "+3V3")

    # -- Outbound command strobes: 2x 74LVC244A --------------------------------
    for n, chunk in enumerate(_chunk(_OUT244, 8)):
        pairs = [(s, "X_" + s) for s in chunk]   # 1A/2A in (internal), 1Y/2Y out (X_)
        buf244("U%d" % (4 + n), (114.3, 45.72 + n * 63.5), pairs)

    # -- Data transceiver: 1x 74LVC245A, DIR = EXP_DDIR ------------------------
    # A-side = internal D0..D7, B-side = X_D0..X_D7.  Truth table (74LVC245A):
    #   DIR=H, ~OE=L : A -> B  (internal -> X_, OUTBOUND -- the safe default)
    #   DIR=L, ~OE=L : B -> A  (X_ -> internal, card read data inbound)
    # ~OE tied GND (always enabled) so the port can always present read data to
    # a card; DIRECTION is the only safety, owned by EXP_DDIR firmware policy.
    # R1 pulls EXP_DDIR HIGH so the port is OUTBOUND-safe at power-on, BEFORE
    # the Bus MCU boots and drives GPIO43 (no bus contention during that window).
    buf245("U6", (114.3, 172.72),
           [("D%d" % i, "X_D%d" % i) for i in range(8)], "EXP_DDIR")
    # (EXP_DDIR's default-outbound pull-up lives in RN1, below)

    # -- Inbound IRQ/DRQ: 2x 74LVC244A onto EXT_* nets -------------------------
    # X_<sig> in (5V-tol), EXT_<sig> out.  100k pull-DOWN on every X_ input so an
    # unplugged port reads all-zeros (active-high IRQ/DRQ idle low).
    inbound = [("X_" + s, "EXT_" + s) for s in _INBOUND]
    for n, chunk in enumerate(_chunk(inbound, 8)):
        buf244("U%d" % (7 + n), (63.5, 172.72 + n * 63.5), chunk)
    for i, s in enumerate(_INBOUND):
        pull("R%d" % (2 + i), "X_" + s, "GND", (25.4 + i * 10.16, 260.35), "100k")

    # -- IOCHRDY / ~{IOCHCK}: open-drain buffers back to the INTERNAL nets ------
    # DEVIATION: place the mini-xt:74LVC2G06 body with value "74LVC2G07" -- the
    # 2G07 (non-inverting OPEN-DRAIN buffer) is pin-identical to the 2G06 and has
    # no separate symbol (parts.py binds this (lib_id,value) pair).
    # X_IOCHRDY low (card wants wait) -> pull internal IOCHRDY low; hi-Z otherwise.
    # X_~{IOCHCK} low -> pull internal ~{IOCHCK} low.  Wired-AND, no contention.
    # 10k pull-UPS on the X_ side so an unplugged port reads inactive-high.
    u9 = sch.place("mini-xt:74LVC2G06", "U9", "74LVC2G07", at=(114.3, 236.22))
    sch.net(u9, "1A", "X_IOCHRDY", kind="label", dx=-2.54)
    sch.net(u9, "1Y", "IOCHRDY", kind="label", dx=2.54)
    sch.net(u9, "2A", "X_~{IOCHCK}", kind="label", dx=-2.54, dy=2.54)
    sch.net(u9, "2Y", "~{IOCHCK}", kind="label", dx=2.54, dy=2.54)
    sch.net(u9, "VCC", "+3V3", kind="label", dy=-2.54)
    sch.net(u9, "GND", "GND", kind="label", dy=2.54)
    # (2026-07-14: one 4x10k basic array replaces the three discrete pulls:
    # EXP_DDIR default-outbound, X_IOCHRDY/X_~{IOCHCK} wire-OR idle-high)
    mxbus.r_pack4(sch, "RN1", "10kx4", (152.4, 226.06),
                  [("EXP_DDIR", "+3V3"), ("X_IOCHRDY", "+3V3"),
                   ("X_~{IOCHCK}", "+3V3")])

    decouple("C4", (48.26, 20.32))
    decouple("C5", (99.06, 20.32))
    decouple("C6", (48.26, 147.32))
    decouple("C7", (99.06, 147.32))

    # -- Header: standard ISA pinout, bus nets -> X_ port-local nets ------------
    # remap EVERY signal -> "X_"+name (built from ISA_PINS); keep +5V->+5V_ISA,
    # leave GND unmapped.  isa_conn.place_header keys remap by raw PIN_NETS names
    # (individual A0/D3/~{MEMR}..., NOT bus-group form), which is exactly what
    # ISA_PINS enumerates -- so this covers every pin.
    remap = {p["name"]: "X_" + p["name"] for p in isa_conn.ISA_PINS}
    remap["+5V"] = "+5V_ISA"
    isa_conn.place_header(sch, "J1", (215.9, 152.4), remap=remap)

    # +5V feed protection (design review 2026-07-11): a shorted/misbehaving
    # expansion card must not drag down or back-drive the motherboard rail.
    F1 = sch.place("Device:Polyfuse", "F1", "2A", at=(266.7, 45.72))
    sch.net(F1, "1", "+5V", kind="label", dx=0, dy=-2.54)
    sch.net(F1, "2", "+5V_ISA", kind="label", dx=0, dy=2.54)
    D1 = sch.place("Device:D_Zener", "D1", "SMBJ5.0A", at=(281.94, 45.72))
    sch.net(D1, "K", "+5V_ISA", kind="label", dx=0, dy=-2.54)   # clamp back-fed >5V
    sch.net(D1, "A", "GND", kind="label", dx=0, dy=2.54)
    C3 = sch.place("Device:C_Polarized", "C3", "22uF", at=(297.18, 45.72))
    sch.net(C3, "1", "+5V_ISA", kind="label", dx=0, dy=-2.54)   # bulk downstream of fuse
    sch.net(C3, "2", "GND", kind="label", dx=0, dy=2.54)
    for n, x in [(1, 266.7), (2, 281.94)]:
        c = sch.place("Device:C", "C%d" % n, "100nF", at=(x, 71.12))
        sch.net(c, "1", "+5V_ISA", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

    sch.text("ONLY real-ISA attachment point on the 3.3V board: LVC buffers "
             "(5V-tolerant in, 3.3V-TTL out) between the internal bus and the "
             "external header. Header nets are port-local (X_*).", (200.66, 96.52))
    sch.text("Data xcvr direction = EXP_DDIR (Bus MCU); R1 pulls it OUTBOUND-safe "
             "at power-on. External BUS-MASTER cards are UNSUPPORTED -- fixed, "
             "firmware-chosen direction, no port arbitration.", (200.66, 106.68))
    sch.text("IRQ2-7/DRQ1-3 buffered onto private EXT_* nets (soft-PIC/soft-8237 "
             "merge them in firmware), NOT the internal IRQ/DRQ nets. IOCHRDY / "
             "~{IOCHCK} return via open-drain (wired-AND).", (200.66, 116.84))
    sch.text("J1: 60-pin (2x30) standard 8-bit ISA pinout; same as the soft-card "
             "IN/OUT headers (isa_conn). +5V feed fused (2A) + TVS-clamped; "
             "header power ~3A/pin, keep chains to 2-3 cards.", (200.66, 127.0))
    sch.text("Pin 13 = reserved/0WS# (unconnected), per the standard/PicoGUS header.",
             (200.66, 218.44))

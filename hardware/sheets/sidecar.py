"""Sidecar -- 2x32 (64-pin) IDC ISA expansion header (design doc S4.3).

Instead of on-board slots, a single 2.54 mm 2x32 IDC ribbon header carries the
FULL buffered 8-bit XT/ISA signal set off-board with interleaved grounds:
  * A0-A19 latched address, D0-D7 buffered data
  * ~{MEMR} ~{MEMW} ~{IOR} ~{IOW}, BALE, AEN
  * CLK (7.16 MHz), OSC (14.318 MHz), RESET_DRV
  * IOCHRDY, ~{IOCHCK}
  * IRQ2-7 plus extended IRQ10/11/14 (sidecar/spare lines from the soft-PIC)
  * TC, DRQ1-3, ~{DACK1-3} (so the Bus MCU's emulated 8237 can service a real
    DMA card on the cable)
  * two +5V pins, six grounds, and one keyed (no-connect) pin to prevent reversed
    insertion.

This is a pure pass-through to the backplane -- no active parts. The on-board
245/573 only ever drive the cable + one future re-buffer (S4.3), so at 7.16 MHz
over a short ribbon this is comfortable. A couple of bypass caps keep the cable
+5V quiet. Soft-card rules: ISA signals + power only, no private nets.
"""
import mxbus
from mxbus import pin

NAME = "sidecar"
TITLE = "Sidecar -- 2x32 IDC ISA expansion header"

# Full ISA bus contract exposed as the sheet interface (S2/S8 portability rule).
PINS = (
    [pin(s) for s in mxbus.ADDR] +
    [pin(s) for s in mxbus.DATA] +
    [pin(s) for s in mxbus.IRQ] +
    [pin(s) for s in ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN",
                      "IOCHRDY", "~{IOCHCK}", "CLK", "OSC", "RESET_DRV", "TC",
                      "DRQ1", "DRQ2", "DRQ3", "~{DACK1}", "~{DACK2}", "~{DACK3}"]]
)


def build(sch, lib):
    # interface: one hierarchical label per bus signal (cross-sheet by name)
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))

    # ---------------- the 64-pin header ----------------
    cx, cy = 177.8, 152.4
    J1 = sch.place("Connector_Generic:Conn_02x32_Odd_Even", "J1", at=(cx, cy))

    GND, V5, KEY = "GND", "+5V", None
    ctrl = ["~{MEMR}", "~{MEMW}", "~{IOR}", "~{IOW}", "BALE", "AEN",
            "IOCHRDY", "~{IOCHCK}", "CLK", "OSC", "RESET_DRV"]
    dma = ["TC", "DRQ1", "DRQ2", "DRQ3", "~{DACK1}", "~{DACK2}", "~{DACK3}"]
    irq = ["IRQ2", "IRQ3", "IRQ4", "IRQ5", "IRQ6", "IRQ7",   # 8-bit ISA IRQs
           "IRQ10", "IRQ11", "IRQ14"]                         # extended (S14 sidecar)

    # Pin order, pins 1..64. GND dropped at each functional-group boundary so a
    # return runs alongside every signal cluster (interleaved-ground rule, S4.3).
    seq = [V5, GND]                       # 1-2   : top power pair
    seq += list(mxbus.ADDR[0:10]) + [GND]  # 3-13  : A0-A9  + gnd
    seq += list(mxbus.ADDR[10:20]) + [GND]  # 14-24 : A10-A19 + gnd
    seq += list(mxbus.DATA) + [GND]        # 25-33 : D0-D7  + gnd
    seq += ctrl + [GND]                    # 34-45 : command/control + gnd
    seq += dma + [GND]                     # 46-53 : DMA group + gnd
    seq += irq                             # 54-62 : IRQ lines
    seq += [KEY, V5]                       # 63-64 : key pin, +5V
    assert len(seq) == 64, "header is 64 pins, got %d" % len(seq)

    for i, net in enumerate(seq):
        num = str(i + 1)
        if net is KEY:
            sch.no_connect(J1.pin_xy(num))   # keyed slot: plugged on the ribbon
            continue
        # odd pins = left column (stub left), even pins = right column (stub right)
        dx = -2.54 if (i + 1) % 2 == 1 else 2.54
        sch.net(J1, num, net, kind="label", dx=dx)

    sch.text("KEY = pin 63: no-connect / plugged ribbon hole -- prevents "
             "reversed insertion", (139.7, 200.66))
    sch.text("J1: 2x32 IDC -- full buffered 8-bit ISA bus off-board (S4.3)",
             (139.7, 106.68))

    # ---------------- cable bypass / power anchors ----------------
    for n, x in [(1, 205.74), (2, 218.44)]:
        c = sch.place("Device:C", "C%d" % n, "100nF", at=(x, 134.62))
        sch.net(c, "1", "+5V", kind="label", dx=0, dy=-2.54)
        sch.net(c, "2", "GND", kind="label", dx=0, dy=2.54)

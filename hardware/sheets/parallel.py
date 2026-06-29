"""Parallel port (LPT) -- 74HC374/244 @ 0x378 + DB25
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "parallel"
TITLE = "Parallel port (LPT) -- 74HC374/244 @ 0x378 + DB25"
PINS = [pin(s,"input") for s in mxbus.ADDR[:10]]+[pin(s) for s in mxbus.DATA]+[pin(s,"input") for s in ["~{IOR}","~{IOW}","AEN","RESET_DRV"]]+[pin("IRQ7","output")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("mini-xt:74HC374", "U1", at=(127, 127))
    sch.text("STUB: parallel to be completed", (101.6, 109.22))

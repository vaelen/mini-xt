"""Real-time clock -- DS12C887 @ 0x70/0x71
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "rtc"
TITLE = "Real-time clock -- DS12C887 @ 0x70/0x71"
PINS = [pin(s,"input") for s in mxbus.ADDR[:8]]+[pin(s) for s in mxbus.DATA]+[pin(s,"input") for s in ["~{IOR}","~{IOW}","AEN","RESET_DRV"]]+[pin("IRQ8","output")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("mini-xt:DS12C887", "U1", at=(127, 127))
    sch.text("STUB: rtc to be completed", (101.6, 109.22))

"""Storage -- XT-IDE (Chuck-mod) + CompactFlash @ 0x300
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "storage"
TITLE = "Storage -- XT-IDE (Chuck-mod) + CompactFlash @ 0x300"
PINS = [pin(s,"input") for s in mxbus.ADDR[:10]]+[pin(s) for s in mxbus.DATA]+[pin(s,"input") for s in ["~{IOR}","~{IOW}","AEN","RESET_DRV"]]+[pin("IRQ5","output")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("mini-xt:74HC573", "U1", at=(127, 127))
    sch.text("STUB: storage to be completed", (101.6, 109.22))

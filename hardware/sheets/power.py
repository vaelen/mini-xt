"""Power supply -- USB-C 5V in (CC/CH224K) -> 3.3V buck
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "power"
TITLE = "Power supply -- USB-C 5V in (CC/CH224K) -> 3.3V buck"
PINS = [pin("+5V","output"), pin("+3V3","output"), pin("GND","power_in")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("Interface_USB:CH224K", "U1", at=(127, 127))
    sch.text("STUB: power to be completed", (101.6, 109.22))

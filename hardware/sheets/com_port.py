"""COM port -- 16C550 UART + MAX3241 + DB9 (instanced x2)
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "com_port"
TITLE = "COM port -- 16C550 UART + MAX3241 + DB9 (instanced x2)"
PINS = [pin(s,"input") for s in mxbus.ADDR[:10]]+[pin(s) for s in mxbus.DATA]+[pin(s,"input") for s in ["~{IOR}","~{IOW}","AEN","RESET_DRV","CLK"]]+[pin("IRQ4","output"), pin("IRQ3","output")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("Interface_UART:16550", "U1", at=(127, 127))
    sch.text("STUB: com_port to be completed", (101.6, 109.22))

INSTANCES = [("COM1", "", {"COM_IRQ": "IRQ4"}),
             ("COM2", "B", {"COM_IRQ": "IRQ3"})]

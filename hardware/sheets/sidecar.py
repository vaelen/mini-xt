"""Sidecar -- 2x32 IDC ISA expansion header
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "sidecar"
TITLE = "Sidecar -- 2x32 IDC ISA expansion header"
PINS = [pin(s) for s in mxbus.ADDR]+[pin(s) for s in mxbus.DATA]+[pin(s) for s in mxbus.IRQ]+[pin(s) for s in ["~{MEMR}","~{MEMW}","~{IOR}","~{IOW}","BALE","AEN","IOCHRDY","~{IOCHCK}","CLK","OSC","RESET_DRV","TC","DRQ1","DRQ2","DRQ3","~{DACK1}","~{DACK2}","~{DACK3}"]]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("Connector_Generic:Conn_02x32_Odd_Even", "U1", at=(127, 127))
    sch.text("STUB: sidecar to be completed", (101.6, 109.22))

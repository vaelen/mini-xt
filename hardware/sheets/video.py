"""Video card MCU (RP2350B) -- soft CGA/MDA/Herc, VGA + HDMI out
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "video"
TITLE = "Video card MCU (RP2350B) -- soft CGA/MDA/Herc, VGA + HDMI out"
PINS = [pin(s,"input") for s in mxbus.ADDR]+[pin(s) for s in mxbus.DATA]+[pin(s,"input") for s in ["~{MEMR}","~{MEMW}","~{IOR}","~{IOW}","BALE","AEN","CLK","RESET_DRV"]]+[pin("IOCHRDY","output")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("MCU_RaspberryPi:RP2350B", "U1", at=(127, 127))
    sch.text("STUB: video to be completed", (101.6, 109.22))

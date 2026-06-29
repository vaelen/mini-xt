"""Audio -- PC-speaker + op-amp summer -> line-out (PicoGUS input stub)
STUB to be completed by subagent."""
import mxbus
from mxbus import pin
NAME = "audio"
TITLE = "Audio -- PC-speaker + op-amp summer -> line-out (PicoGUS input stub)"
PINS = [pin("SPKR","input"), pin("GND","power_in")]
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("Amplifier_Operational:TL072", "U1", at=(127, 127))
    sch.text("STUB: audio to be completed", (101.6, 109.22))

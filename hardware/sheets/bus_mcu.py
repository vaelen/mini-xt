"""bus_mcu -- STUB to be completed by subagent.
Bus Master MCU (RP2350B): soft PIC(x2)/PIT/KBC/DMA/NMI/POST, bus slave+master,
local 74LVC245A level shifters (bidir addr/ctrl with role DIR), external 20-bit
loadable address counter (5x 74HC163), 74HC165 IRQ collector, UART link to Super."""
import mxbus
from mxbus import pin
NAME = "bus_mcu"
TITLE = "Bus Master MCU (RP2350B) -- soft chipset + bus master"
PINS = ([pin(s) for s in mxbus.ADDR] + [pin(s) for s in mxbus.DATA] +
        [pin(s) for s in mxbus.IRQ] +
        [pin(s) for s in ["~{MEMR}","~{MEMW}","~{IOR}","~{IOW}","BALE","AEN",
                          "IOCHRDY","~{IOCHCK}","CLK","RESET_DRV","TC",
                          "DRQ1","DRQ2","DRQ3","~{DACK1}","~{DACK2}","~{DACK3}"]] +
        [pin(s) for s in mxbus.PRIV_CPU] + [pin(s) for s in mxbus.PRIV_COUNTER] +
        [pin("LINK_B2S","output"), pin("LINK_S2B","input")])
def build(sch, lib):
    mxbus.emit_interface(sch, PINS, at=(25.4, 25.4))
    sch.place("MCU_RaspberryPi:RP2350B", "U1", at=(127, 127))
    sch.text("STUB: to be completed", (127, 110))

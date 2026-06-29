"""Introspection helper: print pins of a symbol, or search symbol names.

Usage:
  python3 pins.py <Lib:Name>        # list pins (number:name:type)
  python3 pins.py -s <substr>       # search symbol names across std libs + mini-xt
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from mxsch import SymbolLib

SYMDIR = "/snap/kicad/22/usr/share/kicad/symbols"
HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBS = ["Device", "power", "Connector", "Connector_Generic", "74xx", "4xxx",
        "Interface_UART", "Interface_USB", "Interface_LineDriver", "Memory_RAM",
        "MCU_RaspberryPi", "Oscillator", "Regulator_Switching", "Regulator_Linear",
        "Power_Supervisor", "Switch", "Audio", "Amplifier_Operational", "Timer_RTC",
        "Diode", "Transistor_BJT", "Connector_Specific"]


def load():
    lib = SymbolLib()
    for n in LIBS:
        p = os.path.join(SYMDIR, n + ".kicad_sym")
        if os.path.exists(p):
            lib.load(p, n)
    p = os.path.join(HW, "mini-xt.kicad_sym")
    if os.path.exists(p):
        lib.load(p, "mini-xt")
    return lib


if __name__ == "__main__":
    lib = load()
    if sys.argv[1] == "-s":
        q = sys.argv[2].lower()
        for k in sorted(lib.defs):
            if q in k.lower():
                print(k, "(%d pins)" % len(lib.defs[k].pins))
    else:
        sd = lib.get(sys.argv[1])
        for p in sd.pins:
            print("%4s  %-12s %s" % (p.number, p.name, p.etype))

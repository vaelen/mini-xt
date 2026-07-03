"""Empirical validation of mxsch coordinate math via netlist export."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mxsch import SymbolLib, Schematic

SYMDIR = __import__("mxsch").kicad_symdir()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest")
CLI = __import__("mxsch").kicad_cli()

os.makedirs(OUT, exist_ok=True)

lib = SymbolLib()
lib.load(os.path.join(SYMDIR, "Device.kicad_sym"), "Device")
lib.load(os.path.join(SYMDIR, "power.kicad_sym"), "power")

sch = Schematic(lib, title="selftest", rev="1")

r1 = sch.place("Device:R", "R1", "1k", at=(50, 50))
r2 = sch.place("Device:R", "R2", "2k", at=(80, 50))

# Connect R1 pin2 to R2 pin1 via net "MID" (label-based, no direct wire between them)
sch.net(r1, "2", "MID", dx=0, dy=2.54)   # R pin2 is at bottom; stub down
sch.net(r2, "1", "MID", dx=0, dy=-2.54)  # R pin1 is at top; stub up

# Power: R1 pin1 -> +5V, R2 pin2 -> GND
sch.net(r1, "1", "+5V", dx=0, dy=-2.54)
sch.net(r2, "2", "GND", dx=0, dy=2.54)

open(os.path.join(OUT, "selftest.kicad_sch"), "w").write(sch.render())
print("wrote schematic")

# export netlist
r = subprocess.run([CLI, "sch", "export", "netlist", "-o",
                    os.path.join(OUT, "selftest.net"),
                    os.path.join(OUT, "selftest.kicad_sch")],
                   capture_output=True, text=True)
print("netlist rc", r.returncode)
print(r.stdout[-2000:])
print(r.stderr[-2000:])

if os.path.exists(os.path.join(OUT, "selftest.net")):
    net = open(os.path.join(OUT, "selftest.net")).read()
    # check the MID net has both R1-2 and R2-1
    import re
    for netname in ["MID", "+5V", "GND"]:
        m = re.search(r'\(net \(code "\d+"\) \(name "[^"]*%s[^"]*"\)(.*?)\n\s*\)' % re.escape(netname),
                      net, re.S)
        if m:
            refs = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', m.group(1))
            print("NET %-6s ->" % netname, refs)
        else:
            print("NET %-6s -> NOT FOUND" % netname)

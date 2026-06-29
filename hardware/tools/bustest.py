"""Validate bus member connectivity across a hierarchical sheet boundary."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from mxsch import SymbolLib, Schematic

SYMDIR = "/snap/kicad/22/usr/share/kicad/symbols"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bustest")
CLI = "/snap/bin/kicad.kicad-cli"
os.makedirs(OUT, exist_ok=True)
lib = SymbolLib(); lib.load(SYMDIR + "/Device.kicad_sym", "Device")

# ---- sub-sheet: R1.1 -> D0 member, tied to bus D[0..7] via bus entry; hier bus pin ----
sub = Schematic(lib, title="sub", rev="1")
r1 = sub.place("Device:R", "R1", "1k", at=(60, 60))
# bus runs vertically at x=80
sub.bus_wire((80, 40), (80, 80))
sub.hier_label("D[0..7]", (80, 40), 90, "input")     # bus hier pin (top of bus)
# member D0: from R1.1 (top, at (60, 60-3.81=56.19... computed)) wire to bus entry
p = r1.pin_xy("1")   # top pin
# wire from pin up/right to bus entry base, bus entry to bus
sub.wire(p, (70, p[1]))
sub.label("D0", (70, p[1]), 0)
sub.bus_entry((77.46, p[1] + 2.54))   # entry rises 2.54 to bus at (80, p1y)... approximate
sub.wire((70, p[1]), (77.46, p[1]))

# ---- root: sheet with bus pin D[0..7], bus to a resistor's pin labeled D0 ----
root = Schematic(lib, title="root", rev="1"); root.is_root = True
suuid = root.sheet("SUB", "sub.kicad_sch", at=(100, 40), size=(40, 40),
                   pins=[("D[0..7]", "input", "l", 10)])
# root bus from sheet pin (100,50) leftwards
root.bus_wire((100, 50), (80, 50))
root.bus_wire((80, 50), (80, 70))
root.label_bus = None
# put a bus label
root.items.append(["label", "D[0..7]", ["at", 90, 50, 0],
                   ["effects", ["font", ["size", 1.27, 1.27]]], ["uuid", __import__("mxsch").uid()]])
# a resistor whose pin is D0, tied to root bus
r2 = root.place("Device:R", "R2", "2k", at=(60, 70))
p2 = r2.pin_xy("1")
root.wire(p2, (74, p2[1])); root.label("D0", (74, p2[1]), 0)
root.bus_entry((77.46, 70 - 2.54)); root.wire((74, p2[1]), (77.46, p2[1]))

sub.inst_paths = [("/" + root.uuid + "/" + suuid, {})]
open(OUT + "/root.kicad_sch", "w").write(root.render())
open(OUT + "/sub.kicad_sch", "w").write(sub.render())
open(OUT + "/bustest.kicad_pro", "w").write('{"meta":{"version":1}}\n')

r = subprocess.run([CLI, "sch", "export", "netlist", "-o", OUT + "/root.net",
                    OUT + "/root.kicad_sch"], capture_output=True, text=True)
print("rc", r.returncode, r.stdout.strip(), r.stderr.strip())
if os.path.exists(OUT + "/root.net"):
    net = open(OUT + "/root.net").read()
    print(net[net.find("(nets"):][:1400])

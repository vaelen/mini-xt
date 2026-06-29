"""Validate hierarchical cross-sheet connectivity via netlist export."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from mxsch import SymbolLib, Schematic

SYMDIR = "/snap/kicad/22/usr/share/kicad/symbols"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_hiertest")
CLI = "/snap/bin/kicad.kicad-cli"
os.makedirs(OUT, exist_ok=True)

lib = SymbolLib()
lib.load(SYMDIR + "/Device.kicad_sym", "Device")
lib.load(SYMDIR + "/power.kicad_sym", "power")

# ---- sub-sheet ----
sub = Schematic(lib, title="sub", rev="1")
r1 = sub.place("Device:R", "R1", "1k", at=(60, 60))
r2 = sub.place("Device:R", "R2", "2k", at=(60, 80))
# R1.1 (top) -> hier label VIN ; R1.2 (bottom) -> internal net N1
sub.net(r1, "1", "VIN", dx=0, dy=-2.54, kind="hier", shape="input")
sub.net(r1, "2", "N1", dx=0, dy=2.54)
# R2.1 (top) -> N1 ; R2.2 (bottom) -> hier label VOUT
sub.net(r2, "1", "N1", dx=0, dy=-2.54)
sub.net(r2, "2", "VOUT", dx=0, dy=2.54, kind="hier", shape="output")

# ---- root ----
root = Schematic(lib, title="root", rev="1")
root.is_root = True
suuid = root.sheet("SUB", "sub.kicad_sch", at=(100, 50), size=(40, 30),
                   pins=[("VIN", "input", "l", 8), ("VOUT", "output", "r", 8)])
# wire sheet pins to power nets at root
vin_xy = (100, 58)      # left pin
vout_xy = (140, 58)     # right pin
p5 = root.power("power:+5V", "#PWR1", at=(90, 50))
root.wire(vin_xy, (90, 58)); root.wire((90, 58), (90, 50 + 0))  # rough
root.label("+5V", (95, 58), 0)
gnd = root.power("power:GND", "#PWR2", at=(150, 66))
root.label("GND", (145, 58), 0)
root.wire(vout_xy, (148, 58))

# bind sub-sheet instance path
sub.inst_paths = [("/" + root.uuid + "/" + suuid, {})]

open(OUT + "/root.kicad_sch", "w").write(root.render())
open(OUT + "/sub.kicad_sch", "w").write(sub.render())
# minimal project file
open(OUT + "/hiertest.kicad_pro", "w").write('{\n  "meta": {"version": 1}\n}\n')
print("written")

r = subprocess.run([CLI, "sch", "export", "netlist", "-o", OUT + "/root.net",
                    OUT + "/root.kicad_sch"], capture_output=True, text=True)
print("rc", r.returncode, r.stdout.strip(), r.stderr.strip())
if os.path.exists(OUT + "/root.net"):
    import re
    net = open(OUT + "/root.net").read()
    print("=== nets ===")
    print(net[net.find("(nets"):][:1200])

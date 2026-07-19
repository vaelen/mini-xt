"""Assemble the full mini-xt hierarchical schematic project and validate it.

Each sheet lives in sheets/<name>.py exposing:
    NAME        short id (file becomes sheets/<NAME>.kicad_sch)
    TITLE       title block text
    PINS        list of mxbus.pin(...) dicts -- the sheet's interface
    INSTANCES   (optional) list of (instance_label, ref_suffix) for multi-instantiation
    build(sch, lib)   place parts + wire; connect each interface signal via a
                      hierarchical label whose name is in PINS.

The root ties identically-named sheet pins together (drawing A/D/IRQ as buses)
so the independently-authored sheets interconnect into the buffered ISA backplane.
"""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HW, "sheets"))

import mxsch
import mxbus
from mxsch import SymbolLib, Schematic

SYMDIR = mxsch.kicad_symdir()   # $KICAD_SYMBOL_DIR / user data dir / system
CLI = mxsch.kicad_cli()         # $KICAD_CLI / PATH

# ERC categories that MUST be zero (everything else is expected interface-
# fidelity noise, see notes/open-questions.md Q10). These fail the build.
STRUCTURAL_ERC = ("endpoint_off_grid", "unconnected_wire_endpoint",
                  "multiple_net_names")


def structural_violations(rpt_path):
    """Count structural ERC violations in a kicad-cli ERC report."""
    import re
    from collections import Counter
    if not os.path.exists(rpt_path):
        return {"missing_report": 1}
    c = Counter(re.findall(r"\[([a-z_]+)\]", open(rpt_path).read()))
    return {k: c[k] for k in STRUCTURAL_ERC if c.get(k)}

STD_LIBS = ["Device", "power", "Connector", "Connector_Generic", "74xx",
            "Interface_UART", "Interface_USB", "Interface_LineDriver",
            "Memory_RAM", "Memory_Flash", "MCU_RaspberryPi", "Oscillator",
            "Regulator_Switching", "Regulator_Linear", "Power_Supervisor",
            "Switch", "Audio", "Amplifier_Operational", "Timer_RTC", "Diode",
            "Transistor_BJT", "Power_Protection"]

SHEETS = ["cpu_core", "bus_mcu", "supervisor", "video", "com_port",
          "parallel", "power", "storage", "audio", "sidecar", "picogus",
          "addr_decode"]


def load_lib():
    lib = SymbolLib()
    for name in STD_LIBS:
        p = os.path.join(SYMDIR, name + ".kicad_sym")
        if mxsch.lib_source(p):
            lib.load(p, name)
    lib.load(os.path.join(HW, "mini-xt.kicad_sym"), "mini-xt")
    return lib


def build_subsheet(modname, lib):
    mod = importlib.import_module(modname)
    sch = Schematic(lib, title=getattr(mod, "TITLE", modname), rev="1",
                    paper=getattr(mod, "PAPER", "A3"))
    mod.build(sch, lib)
    import parts
    parts.apply(sch)      # attach 'LCSC Part Num' properties (JLCPCB BOM)
    return mod, sch


# (Standalone dev-card PCBs -- card_video, card_isatest -- and their
# build_cards() harness were DELETED 2026-07-14: the long-term plan is an ISA
# backplane expansion board off the sidecar port instead. Tag/history has the
# last version.)


def assemble(write=True, run_checks=True):
    lib = load_lib()
    mods = {}
    schs = {}
    for name in SHEETS:
        try:
            mod, sch = build_subsheet(name, lib)
            mods[name] = mod
            schs[name] = sch
        except Exception as e:
            print("!! sheet %s failed to build: %s" % (name, e))
            raise

    # ---- root ----
    root = Schematic(lib, title="mini-xt XT-class MCU-SBC (root)", rev="1")
    root.is_root = True

    # place sheet symbols in a grid; collect member pins for bus rails
    col_x = [25.4, 120.65, 215.9, 311.15]
    row_y = 25.4
    placed = []  # (name, suuid, pin_world_positions dict)
    x_i = 0
    y_cursor = {c: 25.4 for c in range(len(col_x))}
    W = 38.1
    for name in SHEETS:
        mod = mods[name]
        pins = mod.PINS
        npins = len(pins)
        h = max(25.4, ((npins + 1) // 2 + 1) * 2.54)
        left = pins[: (npins + 1) // 2]
        right = pins[(npins + 1) // 2:]
        instances = getattr(mod, "INSTANCES", [(name.upper(), "")])
        for inst in instances:
            inst_label, _suf = inst[0], inst[1]
            netmap = inst[2] if len(inst) > 2 else {}
            col = x_i % len(col_x)
            x = col_x[col]
            y = y_cursor[col]
            # build sheet-pin list and record world positions FOR THIS instance
            sheetpins = []
            pinpos = {}
            for i, pd in enumerate(left):
                off = 5.08 + i * 2.54
                sheetpins.append((pd["name"], pd["dir"], "l", off))
                pinpos[pd["name"]] = (x, y + off)
            for i, pd in enumerate(right):
                off = 5.08 + i * 2.54
                sheetpins.append((pd["name"], pd["dir"], "r", off))
                pinpos[pd["name"]] = (x + W, y + off)
            suuid = root.sheet(inst_label, "sheets/%s.kicad_sch" % name,
                               at=(x, y), size=(W, h), pins=sheetpins)
            placed.append((name, inst_label, suuid, pinpos, netmap))
            y_cursor[col] = y + h + 7.62
            x_i += 1

    # ---- tie identically-named pins across sheets ----
    # stub + label each pin with its (possibly per-instance remapped) net name
    for (name, inst_label, suuid, pinpos, netmap) in placed:
        for pinname, pos in pinpos.items():
            netname = netmap.get(pinname, pinname)
            on_left = any(abs(pos[0] - cx) < 0.01 for cx in col_x)
            dx = -5.08 if on_left else 5.08
            p1 = (round(pos[0] + dx, 4), pos[1])
            root.wire(pos, p1)
            root.label(netname, p1, 0 if not on_left else 180,
                       justify="left" if not on_left else "right")

    # (No root power flags: power.py's #FLG1-3 already drive +5V/+3V3/GND;
    # a second set here made flag-vs-flag pin_to_pin ERC errors.)

    # ---- bind sub-sheet instance paths with UNIQUE reference banks ----
    # Each sheet instance gets a 'bank' so refs never collide across sheets:
    # ref "U1" in bank 3 becomes "U301", "RAM1" -> "RAM301", etc.
    import re as _re
    inst_by_sheet = {}
    for tup in placed:
        inst_by_sheet.setdefault(tup[0], []).append(tup[2])
    bank = 0
    for name in SHEETS:
        sch = schs[name]
        suuids = inst_by_sheet[name]
        paths = []
        for suuid in suuids:
            bank += 1
            refmap = {}
            for c in sch.components:
                m = _re.match(r"([^\d]+)(\d+)$", c.ref)
                if m:
                    refmap[c.ref] = "%s%d%02d" % (m.group(1), bank, int(m.group(2)))
                else:
                    refmap[c.ref] = "%s%d" % (c.ref, bank)
            paths.append(("/" + root.uuid + "/" + suuid, refmap))
        sch.inst_paths = paths

    if not write:
        return root, schs

    # ---- write files ----
    os.makedirs(os.path.join(HW, "sheets"), exist_ok=True)
    open(os.path.join(HW, "mini-xt.kicad_sch"), "w").write(root.render())
    for name in SHEETS:
        open(os.path.join(HW, "sheets", "%s.kicad_sch" % name), "w").write(
            schs[name].render())
    write_project()
    print("wrote project: root + %d sheets" % len(SHEETS))

    if run_checks:
        return check()
    return root, schs


def write_project():
    open(os.path.join(HW, "mini-xt.kicad_pro"), "w").write(
        '{\n  "board": {},\n  "meta": {"filename": "mini-xt.kicad_pro", "version": 1},\n'
        '  "schematic": {},\n  "sheets": [],\n  "text_variables": {}\n}\n')
    open(os.path.join(HW, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "mini-xt")(type "KiCad")(uri "${KIPRJMOD}/mini-xt.kicad_sym")(options "")(descr ""))\n)\n')


def check():
    """ERC + netlist the assembled project. Returns 0 unless a STRUCTURAL ERC
    category is nonzero or the netlist export fails -- kicad-cli's own exit
    code is useless here because the expected interface-fidelity noise
    (pin_not_connected etc., Q10) always makes it nonzero."""
    root_sch = os.path.join(HW, "mini-xt.kicad_sch")
    rpt = os.path.join(HW, "erc.rpt")
    r = subprocess.run([CLI, "sch", "erc", "--exit-code-violations",
                        "--severity-error", "-o", rpt,
                        root_sch], capture_output=True, text=True)
    print("ERC:", r.stdout.strip()[-400:], r.stderr.strip()[-200:])
    n = subprocess.run([CLI, "sch", "export", "netlist", "-o",
                        os.path.join(HW, "mini-xt.net"), root_sch],
                       capture_output=True, text=True)
    print("NETLIST rc", n.returncode, n.stderr.strip()[-200:])
    bad = structural_violations(rpt)
    if bad:
        print("STRUCTURAL ERC FAILURES:", bad)
    return 1 if (bad or n.returncode != 0) else 0


if __name__ == "__main__":
    sys.exit(assemble())

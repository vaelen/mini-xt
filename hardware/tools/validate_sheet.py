"""Validate ONE sheet module in isolation (safe for parallel work).

Usage: python3 tools/validate_sheet.py <sheet_name>
Builds sheets/<name>.kicad_sch into tools/_val/<name>/ and runs ERC, printing a
violation-type histogram. Standalone-sheet ERC reports hierarchical pins and any
genuinely unused chip pins as 'pin_not_connected'/'label_dangling' -- those are
EXPECTED. What must be ZERO: endpoint_off_grid, unconnected_wire_endpoint,
multiple_net_names, lib_symbol_issues(other than the missing-lib note), and any
load failure.
"""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HW, "sheets"))
import mxsch  # noqa
from build import load_lib  # noqa
CLI = __import__("mxsch").kicad_cli()


def main(name):
    lib = load_lib()
    mod = importlib.import_module(name)
    sch = mxsch.Schematic(lib, title=getattr(mod, "TITLE", name), rev="1",
                          paper=getattr(mod, "PAPER", "A3"))
    mod.build(sch, lib)
    outdir = os.path.join(HERE, "_val", name)
    os.makedirs(outdir, exist_ok=True)
    # copy sym-lib-table so the custom lib resolves (silences lib_symbol_issues)
    open(os.path.join(outdir, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "mini-xt")(type "KiCad")(uri "%s/mini-xt.kicad_sym")(options "")(descr ""))\n)\n'
        % HW)
    p = os.path.join(outdir, name + ".kicad_sch")
    open(p, "w").write(sch.render())
    r = subprocess.run([CLI, "sch", "erc", "-o", p + ".rpt", p],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    if os.path.exists(p + ".rpt"):
        import re
        from collections import Counter
        c = Counter(re.findall(r"\[([a-z_]+)\]", open(p + ".rpt").read()))
        for k, n in c.most_common():
            print("  %4d  %s" % (n, k))
        print("components placed:", len(sch.components))


if __name__ == "__main__":
    main(sys.argv[1])

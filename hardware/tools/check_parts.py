"""Verify the parts map covers every placed component and that every assigned
KiCad footprint exists in the installed footprint libraries.

    python3 hardware/tools/check_parts.py

Exit 1 if any component has no parts.py entry, or an entry's fp names a
footprint missing from the libs ('mini-xt:*' customs are exempt -- they are
authored at layout time and only counted). Entries with lcsc='' are fine
(deliberately sourced elsewhere) but still need an fp.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sheets"))
import build
import mxsch
import parts

# footprint dir lives next to the symbol dir in every KiCad install layout
FPDIR = os.path.join(os.path.dirname(mxsch.kicad_symdir()), "footprints")


def fp_exists(fp):
    lib, name = fp.split(":", 1)
    return os.path.exists(os.path.join(FPDIR, lib + ".pretty", name + ".kicad_mod"))


def main():
    lib = build.load_lib()
    combos = collections.Counter()
    for name in build.SHEETS:
        _, sch = build.build_subsheet(name, lib)
        for c in sch.components:
            if not c.lib_id.startswith("power:"):
                combos[(c.lib_id, c.value)] += 1

    bad = 0
    customs = no_lcsc = 0
    for (lib_id, value), n in sorted(combos.items()):
        e = parts.lookup(lib_id, value)
        if e is None:
            print("UNMAPPED  %-40s %-20s x%d" % (lib_id, value, n))
            bad += 1
            continue
        if not e["lcsc"]:
            no_lcsc += 1
        fp = e["fp"]
        if not fp:
            print("NO FOOTPRINT  %-40s %-20s x%d" % (lib_id, value, n))
            bad += 1
        elif fp.startswith("mini-xt:"):
            customs += 1
        elif not fp_exists(fp):
            print("MISSING FP  %-40s %-20s -> %s" % (lib_id, value, fp))
            bad += 1
    print("%d combos: %d custom fps (author at layout), %d sourced off-JLC, %d problems"
          % (len(combos), customs, no_lcsc, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

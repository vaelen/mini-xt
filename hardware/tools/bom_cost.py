#!/usr/bin/env python3
"""Per-sheet BOM component-cost breakdown for the motherboard.

Reads the generated netlist (hardware/mini-xt.net) and the cached price
table (lcsc_prices.json, JLCPCB qty-1 unit prices keyed by LCSC code) and
prints cost per sheet, unpriced components, and the top cost contributors.
Component costs only -- no assembly, attrition, reels, or extended-part fees.

Refreshing prices: lcsc_prices.json is a snapshot (see its "fetched" date).
To update, re-fetch each LCSC code's qty-1 price (e.g. the pcbparts MCP
jlc_get_part tool, or lcsc.com) and rewrite the "parts" map -- the schema is
  {"fetched": "YYYY-MM-DD", "parts": {"C14663": {"price": 0.0194, ...}}}
Only "price" is required per part; model/stock/library_type/desc are notes.
Components whose LCSC code is missing from the table are listed as unpriced
rather than silently dropped, so a stale table is visible, not wrong.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(HERE, "..", "mini-xt.net")
PRICES = os.path.join(HERE, "lcsc_prices.json")


def parse_netlist(path):
    """Yield (sheet, lcsc, value, ref) for every component in the netlist."""
    txt = open(path).read()
    for c in re.findall(r"\(comp\n(.*?)\n\t\t\)", txt, re.S):
        ref = re.search(r'\(ref "([^"]+)"\)', c).group(1)
        val = re.search(r'\(value "([^"]*)"\)', c).group(1)
        m = re.search(r'\(name "LCSC Part Num"\)\s*\(value "([^"]*)"\)', c)
        s = re.search(r'\(name "Sheetname"\)\s*\(value "([^"]*)"\)', c)
        yield (s.group(1) if s else "?"), (m.group(1) if m else ""), val, ref


def main():
    price_db = json.load(open(PRICES))
    parts = price_db["parts"]
    rows = list(parse_netlist(NETLIST))

    sheet_tot = collections.defaultdict(float)
    sheet_n = collections.Counter()
    unpriced = []
    contrib = collections.Counter()
    for sheet, lcsc, val, ref in rows:
        sheet_n[sheet] += 1
        p = parts.get(lcsc, {}).get("price") if lcsc else None
        if p is None:
            unpriced.append((sheet, ref, val, lcsc or "(no LCSC)"))
            continue
        sheet_tot[sheet] += p
        contrib[(lcsc, val)] += p

    print("Component costs, JLCPCB qty-1 unit prices fetched %s"
          % price_db["fetched"])
    print()
    print("%-12s %6s %10s" % ("sheet", "parts", "USD"))
    for sheet in sorted(sheet_tot, key=sheet_tot.get, reverse=True):
        print("%-12s %6d %10.2f" % (sheet, sheet_n[sheet], sheet_tot[sheet]))
    print("%-12s %6d %10.2f" % ("TOTAL", sum(sheet_n.values()),
                                sum(sheet_tot.values())))

    if unpriced:
        print("\nUnpriced (not in %s):" % os.path.basename(PRICES))
        for sheet, ref, val, lcsc in unpriced:
            print("  %-12s %-6s %-20s %s" % (sheet, ref, val, lcsc))
    print("\nNot in the JLC BOM at all: the V20 itself (user stock; its "
          "socket IS priced),\nthe 2x Core2350B modules (only their female "
          "headers are priced), VGA DE15.")

    print("\nTop 15 cost contributors (extended price across the board):")
    for (lcsc, val), c in contrib.most_common(15):
        print("  %8.2f  %-11s %-14s %s"
              % (c, lcsc, val[:14], parts[lcsc].get("model", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

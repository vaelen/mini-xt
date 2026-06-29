"""
mxsch -- a tiny KiCad 9 schematic generator for the mini-xt project.

Why this exists: hand-authoring electrically-valid KiCad S-expressions across
~11 hierarchical sheets is error-prone. This module centralizes the format so
each sheet is described declaratively (place symbols, connect nets by name) and
emitted as a valid .kicad_sch. Connectivity is label-based: every used pin gets
a short wire stub ending in a label, so nets resolve by name rather than by
fragile point-to-point routing.

Coordinate model (verified empirically via netlist export, see selftest.py):
  - Library symbol pins live in a Y-up frame. KiCad places symbols into a Y-down
    schematic frame, so a pin at lib (lx, ly) on a component placed at (px, py)
    with rotation 0 lands at world (px + lx, py - ly).
  - A pin's (at) is its *connection endpoint* (the tip wires attach to).
  - Rotation rotates the lib point about the origin before the Y flip / offset.
"""

import math
import re
import uuid as _uuid


# --------------------------------------------------------------------------
# S-expression parser / serializer
# --------------------------------------------------------------------------

class Sym(str):
    """A bare S-expression token (unquoted)."""
    __slots__ = ()


def parse_sexp(text):
    """Parse KiCad S-expression text into nested python lists."""
    tokens = _tokenize(text)
    pos = 0

    def parse():
        nonlocal pos
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            lst = []
            while tokens[pos] != ")":
                lst.append(parse())
            pos += 1
            return lst
        else:
            pos += 1
            return tok

    # skip to first '('
    while tokens[pos] != "(":
        pos += 1
    return parse()


def _tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            tokens.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    buf.append(text[i])
                    buf.append(text[i + 1])
                    i += 2
                else:
                    buf.append(text[i])
                    i += 1
            i += 1  # closing quote
            tokens.append('"' + "".join(buf) + '"')  # keep quoted marker
        else:
            buf = []
            while i < n and not text[i].isspace() and text[i] not in '()"':
                buf.append(text[i])
                i += 1
            tokens.append("".join(buf))
    return tokens


def _atom_to_py(tok):
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1]  # quoted string -> str
    return Sym(tok)  # bare token


def parse_sexp_typed(text):
    """Like parse_sexp but marks quoted strings (str) vs bare tokens (Sym)."""
    raw = parse_sexp(text)
    return _typeify(raw)


def _typeify(node):
    if isinstance(node, list):
        return [_typeify(x) for x in node]
    return _atom_to_py(node)


def dump(node, indent=0):
    """Serialize a typed node back to KiCad-ish text."""
    pad = "\t" * indent
    if isinstance(node, list):
        # the first element of any list is the head keyword -> always bare
        head_s = str(node[0])
        # primitive list (all atoms, short) -> single line
        if all(not isinstance(x, list) for x in node):
            atoms = [head_s] + [_atom(x) for x in node[1:]]
            return pad + "(" + " ".join(atoms) + ")"
        parts = [pad + "(" + head_s]
        for child in node[1:]:
            if isinstance(child, list):
                parts.append(dump(child, indent + 1))
            else:
                parts[-1] += " " + _atom(child)
        parts.append(pad + ")")
        return "\n".join(parts)
    return pad + _atom(node)


def _atom(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(x, float):
        s = ("%f" % x).rstrip("0").rstrip(".")
        return s if s else "0"
    return str(x)


def uid():
    return str(_uuid.uuid4())


# valid shapes for hierarchical labels / sheet pins
_VALID_SHAPE = {"input", "output", "bidirectional", "tri_state", "passive"}
_SHAPE_MAP = {"power_in": "input", "power_out": "output",
              "open_collector": "passive", "open_emitter": "passive",
              "unspecified": "passive", "no_connect": "passive"}


def _shape(s):
    if s in _VALID_SHAPE:
        return s
    return _SHAPE_MAP.get(s, "passive")


_GRID = 1.27


def snap(v):
    """Round a coordinate to the 1.27 mm connection grid."""
    return round(round(v / _GRID) * _GRID, 4)


def snapxy(p):
    return (snap(p[0]), snap(p[1]))


# --------------------------------------------------------------------------
# Symbol library
# --------------------------------------------------------------------------

class Pin:
    def __init__(self, number, name, x, y, angle, length, etype):
        self.number = number
        self.name = name
        self.x = x          # lib frame (Y up), connection endpoint
        self.y = y
        self.angle = angle
        self.length = length
        self.etype = etype


class SymbolDef:
    def __init__(self, name, node):
        self.name = name        # e.g. "RP2350B"
        self.node = node        # the full (symbol "...") typed node
        self.pins = []          # collected from all unit sub-symbols

    def pin(self, key):
        for p in self.pins:
            if p.number == str(key) or p.name == str(key):
                return p
        raise KeyError("no pin %r in symbol %s (have: %s)" %
                       (key, self.name, ", ".join(p.number for p in self.pins)))


class SymbolLib:
    """Loads one or more .kicad_sym files; indexes top-level symbols + pins."""

    def __init__(self):
        self.defs = {}      # "Lib:Name" -> SymbolDef
        self._libname = {}  # path -> short lib name

    def load(self, path, libname):
        text = open(path).read()
        root = parse_sexp_typed(text)
        # root = (kicad_symbol_lib ... (symbol "Name" ...) ...)
        for node in root[1:]:
            if isinstance(node, list) and len(node) > 1 and node[0] == Sym("symbol"):
                name = node[1]
                if "_" in name and re.search(r"_\d+_\d+$", name):
                    continue  # unit sub-symbol handled below
                sd = SymbolDef(name, node)
                self._collect_pins(sd, node)
                self.defs["%s:%s" % (libname, name)] = sd
        # resolve (extends ...) inheritance within this library so embedded
        # symbols are standalone (KiCad flattens extends when embedding).
        self._resolve_extends(libname)

    def _resolve_extends(self, libname):
        for key, sd in list(self.defs.items()):
            if not key.startswith(libname + ":"):
                continue
            ext = self._find(sd.node, "extends")
            if ext is None:
                continue
            base = self.defs.get("%s:%s" % (libname, ext))
            if base is None:
                continue
            sd.node = self._merge_extends(base.node, sd.node, base.name, sd.name)
            sd.pins = []
            self._collect_pins(sd, sd.node)

    @staticmethod
    def _merge_extends(base_node, der_node, basename, dername):
        merged = _deepcopy(base_node)
        merged[1] = dername
        # rename nested unit symbols basename_* -> dername_*
        for ch in merged:
            if isinstance(ch, list) and ch and ch[0] == Sym("symbol"):
                if ch[1].startswith(basename):
                    ch[1] = dername + ch[1][len(basename):]
        # apply property overrides from the derived symbol
        der_props = {}
        for ch in der_node:
            if isinstance(ch, list) and ch and ch[0] == Sym("property"):
                der_props[ch[1]] = _deepcopy(ch)
        out = []
        for ch in merged:
            if isinstance(ch, list) and ch and ch[0] == Sym("property") and ch[1] in der_props:
                out.append(der_props.pop(ch[1]))
            elif isinstance(ch, list) and ch and ch[0] == Sym("extends"):
                continue  # drop the extends marker
            else:
                out.append(ch)
        # add any new derived-only properties
        for p in der_props.values():
            out.append(p)
        return out

    @staticmethod
    def _find(node, head):
        for ch in node:
            if isinstance(ch, list) and ch and ch[0] == Sym(head):
                return ch[1] if len(ch) > 1 else True
        return None

    def _collect_pins(self, sd, node):
        # unit sub-symbols are nested INSIDE the top-level symbol node;
        # pins live in those nested (symbol ...) children. Recurse.
        for ch in node:
            if not isinstance(ch, list) or not ch:
                continue
            if ch[0] == Sym("pin"):
                sd.pins.append(self._parse_pin(ch))
            elif ch[0] == Sym("symbol"):
                self._collect_pins(sd, ch)

    @staticmethod
    def _parse_pin(node):
        etype = str(node[1])
        x = y = angle = length = 0.0
        number = name = ""
        for ch in node[2:]:
            if not isinstance(ch, list):
                continue
            if ch[0] == Sym("at"):
                x, y = float(ch[1]), float(ch[2])
                angle = float(ch[3]) if len(ch) > 3 else 0.0
            elif ch[0] == Sym("length"):
                length = float(ch[1])
            elif ch[0] == Sym("name"):
                name = ch[1]
            elif ch[0] == Sym("number"):
                number = ch[1]
        return Pin(number, name, x, y, angle, length, etype)

    def get(self, lib_id):
        return self.defs[lib_id]


# --------------------------------------------------------------------------
# Placed component + schematic
# --------------------------------------------------------------------------

class Component:
    def __init__(self, sch, lib_id, ref, value, at, rotation, mirror, sdef):
        self.sch = sch
        self.lib_id = lib_id
        self.ref = ref
        self.value = value
        self.at = at
        self.rotation = rotation
        self.mirror = mirror      # None, "x", or "y"
        self.sdef = sdef
        self.uuid = uid()

    def pin_xy(self, key):
        """World coordinate of a pin's connection endpoint."""
        p = self.sdef.pin(key)
        lx, ly = p.x, p.y
        # apply mirror in lib frame
        if self.mirror == "y":
            lx = -lx
        elif self.mirror == "x":
            ly = -ly
        # rotate about origin (lib frame, CCW)
        if self.rotation:
            a = math.radians(self.rotation)
            rx = lx * math.cos(a) - ly * math.sin(a)
            ry = lx * math.sin(a) + ly * math.cos(a)
            lx, ly = rx, ry
        px, py = self.at
        return (round(px + lx, 4), round(py - ly, 4))


class Schematic:
    def __init__(self, lib, title="", rev="", company="Andrew C. Young",
                 date="", paper="A3", hierarchical=False):
        self.lib = lib
        self.title = title
        self.rev = rev
        self.company = company
        self.date = date
        self.paper = paper
        self.uuid = uid()
        self.components = []
        self.items = []          # wires, labels, buses, etc (typed nodes)
        self.used_libs = {}      # lib_id -> SymbolDef (to embed)
        self._refcount = {}
        self.is_root = False
        self.proj = "mini-xt"    # project name in instance blocks (per-PCB for cards)
        # instance paths this sheet is placed at: list of (path_prefix, {ref overrides})
        # default: standalone/root -> single instance at "/<own uuid>"
        self.inst_paths = None   # set by Project for sub-sheets
        self.sheet_uuids = []    # suuids of child sheet symbols (root only)

    # ---- placement ----
    def place(self, lib_id, ref, value=None, at=(0, 0), rotation=0, mirror=None):
        sdef = self.lib.get(lib_id)
        if value is None:
            value = lib_id.split(":")[1]
        at = snapxy(at)          # keep every pin on the 1.27 mm connection grid
        c = Component(self, lib_id, ref, value, at, rotation, mirror, sdef)
        self.components.append(c)
        self.used_libs[lib_id] = sdef
        return c

    # ---- connectivity helpers ----
    def wire(self, p1, p2):
        p1 = snapxy(p1); p2 = snapxy(p2)
        self.items.append(["wire", ["pts", ["xy", p1[0], p1[1]], ["xy", p2[0], p2[1]]],
                           ["stroke", ["width", 0], ["type", Sym("default")]],
                           ["uuid", uid()]])

    def bus_wire(self, p1, p2):
        self.items.append(["bus", ["pts", ["xy", p1[0], p1[1]], ["xy", p2[0], p2[1]]],
                           ["stroke", ["width", 0], ["type", Sym("default")]],
                           ["uuid", uid()]])

    def bus_entry(self, p, size=(2.54, 2.54)):
        self.items.append(["bus_entry", ["at", p[0], p[1]],
                           ["size", size[0], size[1]],
                           ["stroke", ["width", 0], ["type", Sym("default")]],
                           ["uuid", uid()]])

    def junction(self, p):
        p = snapxy(p)
        self.items.append(["junction", ["at", p[0], p[1]], ["diameter", 0],
                           ["color", 0, 0, 0, 0], ["uuid", uid()]])

    #: net names that must be GLOBAL (power rails) -- promoted automatically so
    #: every sheet's "+5V"/"GND"/"+3V3" join one project-wide net.
    POWER_GLOBAL = {"+5V", "+3V3", "+3.3V", "GND", "-5V", "+12V", "-12V", "VBUS"}

    def label(self, name, at, rotation=0, justify=None):
        if name in self.POWER_GLOBAL:
            return self.global_label(name, at, rotation, "input", justify)
        at = snapxy(at)
        node = ["label", name, ["at", at[0], at[1], rotation],
                self._eff(justify), ["uuid", uid()]]
        self.items.append(node)

    def global_label(self, name, at, rotation=0, shape="bidirectional", justify=None):
        at = snapxy(at)
        node = ["global_label", name, ["shape", Sym(_shape(shape))], ["at", at[0], at[1], rotation],
                self._eff(justify), ["uuid", uid()]]
        self.items.append(node)

    def hier_label(self, name, at, rotation=0, shape="bidirectional", justify=None):
        at = snapxy(at)
        node = ["hierarchical_label", name, ["shape", Sym(_shape(shape))],
                ["at", at[0], at[1], rotation], self._eff(justify), ["uuid", uid()]]
        self.items.append(node)

    def _eff(self, justify):
        eff = ["effects", ["font", ["size", 1.27, 1.27]]]
        if justify:
            eff.append(["justify", Sym(justify)])
        return eff

    def text(self, s, at, size=1.27):
        at = snapxy(at)
        self.items.append(["text", s, ["at", at[0], at[1], 0],
                           ["effects", ["font", ["size", size, size]]], ["uuid", uid()]])

    def no_connect(self, p):
        p = snapxy(p)
        self.items.append(["no_connect", ["at", p[0], p[1]], ["uuid", uid()]])

    # ---- high-level: stub a pin out to a label of net name ----
    def net(self, comp, pinkey, name, dx=2.54, dy=0.0, kind="label", shape="bidirectional"):
        """Draw a stub wire from a pin and attach a label naming the net.
        dx/dy: stub direction & length from the pin endpoint."""
        p0 = comp.pin_xy(pinkey)
        p1 = (round(p0[0] + dx, 4), round(p0[1] + dy, 4))
        if (dx, dy) != (0, 0):
            self.wire(p0, p1)
        rot = 0 if dx >= 0 else 180
        if dy > 0:
            rot = 270
        elif dy < 0:
            rot = 90
        if kind == "label":
            self.label(name, p1, rot)
        elif kind == "global":
            self.global_label(name, p1, rot, shape)
        elif kind == "hier":
            self.hier_label(name, p1, rot, shape)
        return p1

    # ---- sheet instance (for root) ----
    def sheet(self, name, filename, at, size, pins):
        """pins: list of (pinname, shape, side, offset) where side in l/r/t/b."""
        x, y = at
        w, h = size
        suuid = uid()
        node = ["sheet", ["at", x, y], ["size", w, h],
                ["exclude_from_sim", Sym("no")], ["in_bom", Sym("yes")],
                ["on_board", Sym("yes")], ["dnp", Sym("no")],
                ["fields_autoplaced", Sym("yes")],
                ["stroke", ["width", 0.1524], ["type", Sym("solid")]],
                ["fill", ["color", 0, 0, 0, 0.0]],
                ["uuid", suuid],
                ["property", "Sheetname", name, ["at", x, y - 0.7, 0],
                 ["effects", ["font", ["size", 1.27, 1.27]], ["justify", Sym("left"), Sym("bottom")]]],
                ["property", "Sheetfile", filename, ["at", x, y + h + 0.7, 0],
                 ["effects", ["font", ["size", 1.27, 1.27]], ["justify", Sym("left"), Sym("top")], ["hide", Sym("yes")]]],
                ]
        for (pname, shape, side, off) in pins:
            if side == "l":
                px, py, rot = x, y + off, 180
            elif side == "r":
                px, py, rot = x + w, y + off, 0
            elif side == "t":
                px, py, rot = x + off, y, 90
            else:
                px, py, rot = x + off, y + h, 270
            # sheet pins: electrical type is a BARE token (not "(shape ...)")
            node.append(["pin", pname, Sym(_shape(shape)),
                         ["at", px, py, rot],
                         ["effects", ["font", ["size", 1.27, 1.27]],
                          ["justify", Sym("right" if side == "l" else "left")]],
                         ["uuid", uid()]])
        node.append(["instances", ["project", self.proj,
                     ["path", "/" + self.uuid, ["page", str(len(self.sheet_uuids) + 2)]]]])
        self.items.append(node)
        self.sheet_uuids.append((suuid, name, filename))
        return suuid

    # ---- power convenience ----
    def power(self, lib_id, ref, at, rotation=0, mirror=None):
        return self.place(lib_id, ref, lib_id.split(":")[1], at, rotation, mirror)

    # ---- serialize ----
    def render(self):
        root = ["kicad_sch",
                ["version", 20250114],
                ["generator", "mxsch"],
                ["generator_version", "9.0"],
                ["uuid", self.uuid],
                ["paper", self.paper]]
        root.append(["title_block",
                     ["title", self.title],
                     ["date", self.date],
                     ["rev", self.rev],
                     ["company", self.company]])
        # lib_symbols
        libsyms = ["lib_symbols"]
        for lib_id, sdef in self.used_libs.items():
            libsyms.append(self._embed_symbol(lib_id, sdef))
        root.append(libsyms)
        # items (wires, labels, sheets...)
        root.extend(self.items)
        # component instances
        for c in self.components:
            root.append(self._render_component(c))
        # root sheets need a sheet_instances block
        if self.is_root:
            si = ["sheet_instances", ["path", "/", ["page", "1"]]]
            root.append(si)
        return dump(root) + "\n"

    def _embed_symbol(self, lib_id, sdef):
        node = _deepcopy(sdef.node)
        node[1] = lib_id  # rename top-level "Name" -> "Lib:Name"
        # NOTE: KiCad keeps the nested unit symbols at their original short
        # names ("Name_0_1"), so we deliberately do NOT namespace children.
        return node

    def _render_component(self, c):
        n = ["symbol", ["lib_id", c.lib_id],
             ["at", c.at[0], c.at[1], c.rotation],
             ["unit", 1],
             ["exclude_from_sim", Sym("no")],
             ["in_bom", Sym("yes")], ["on_board", Sym("yes")], ["dnp", Sym("no")],
             ["fields_autoplaced", Sym("yes")],
             ["uuid", c.uuid]]
        if c.mirror:
            n.insert(3, ["mirror", Sym(c.mirror)])
        n.append(["property", "Reference", c.ref, ["at", c.at[0], c.at[1] - 5.08, 0],
                  ["effects", ["font", ["size", 1.27, 1.27]]]])
        n.append(["property", "Value", c.value, ["at", c.at[0], c.at[1] + 5.08, 0],
                  ["effects", ["font", ["size", 1.27, 1.27]]]])
        n.append(["property", "Footprint", "", ["at", c.at[0], c.at[1], 0],
                  ["effects", ["font", ["size", 1.27, 1.27]], ["hide", Sym("yes")]]])
        # pin uuids
        for p in c.sdef.pins:
            n.append(["pin", p.number, ["uuid", uid()]])
        # instance paths: sub-sheets get one path per placement (with per-inst ref)
        proj = ["project", self.proj]
        if self.inst_paths:
            for (prefix, refmap) in self.inst_paths:
                ref = refmap.get(c.ref, c.ref)
                proj.append(["path", prefix, ["reference", ref], ["unit", 1]])
        else:
            proj.append(["path", "/" + self.uuid, ["reference", c.ref], ["unit", 1]])
        n.append(["instances", proj])
        return n


def _deepcopy(node):
    if isinstance(node, list):
        return [_deepcopy(x) for x in node]
    return node

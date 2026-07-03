# Open questions -- audio sheet

Sheet: PC-speaker + op-amp summer -> line-out, with a header stub for the
(absent, out-of-scope) PicoGUS line-out. Interface: SPKR (in), GND.

## 1. No AudioJack / Connector_Audio symbol installed
Q: Guide suggested `Connector_Audio:AudioJack3`. That library is not present
   (`pins.py -s AudioJack` and `-s Connector_Audio` both return nothing).
Options: (a) use a generic header as a TRS jack placeholder; (b) add a custom
   AudioJack symbol to mini-xt.kicad_sym.
Pick: (a) -- `Connector_Generic:Conn_01x03` for J2, labelled "LineOut_TRS"
   with tip=L (pin1) / ring=R (pin2) / sleeve=GND (pin3) in a comment + free
   text. Easy to swap for a real jack footprint later.

## 2. PicoGUS line-in header
Q: Card is explicitly out of scope -- just need its input stub.
Pick: `Connector_Generic:Conn_01x03` J1 = L / R / GND, clearly labelled as the
   PicoGUS line-out interface (free text "PicoGUS line-out (card not on board)").

## 3. No LM386 symbol installed
Q: Optional LM386 + small-speaker amp.
   `pins.py -s LM386` returns nothing.
Pick: omit it (the guide said "if absent skip"). Line-out only.

## 4. Mono mix vs. stereo summers (build-harness multi-unit limitation)
Q: A nice design would use both TL072 halves (one inverting summer per stereo
   channel). But the build harness instantiates **unit 1 only** of a multi-unit
   symbol (mxsch always emits `["unit", 1]`), so unit B's pins (5/6/7) land at
   the SAME world coordinates as unit A's (1/2/3). Wiring both halves produced
   `multiple_net_names` + `unconnected_wire_endpoint` ERC errors.
Options: (a) place a 2nd physical TL072 just to reach a "unit 1" for the right
   channel (wasteful, confusing); (b) do a single mono inverting summer in
   unit A and drive both jack channels from it.
Pick: (b). OUT = -(SPKR + PicoGUS_L + PicoGUS_R), 10k summing + 10k feedback,
   AC-coupled to both tip and ring. Doc S9 only asks for a "simple op-amp
   summer", so mono is acceptable. Unit B is left unused.

## 5. Op-amp power pins (same multi-unit limitation)
Q: TL072 V+ (pin 8) / V- (pin 4) belong to the symbol's separate POWER unit,
   which the harness does not place. Stubbing +5V/GND onto them created wire
   endpoints at non-existent pins (`unconnected_wire_endpoint`), and ERC still
   reports `missing_power_pin` for the unplaced power unit.
Pick: do NOT draw stubs on pins 4/8 (kept the design valid). Power intent is
   documented in-code and a 100nF decoupling cap (C6) ties +5V/GND at the part.
   The single-supply bias (VREF = +2.5V virtual ground from a 10k/10k divider +
   bypass cap) feeds the non-inverting input. At true board integration the
   TL072 should be given a real footprint with its power unit wired to +5V/GND.

## 6. Single +5V supply
Q: Op-amp runs from +5V/GND only (no split rail available on this board).
Pick: single-supply topology -- VREF = +2.5V virtual ground on the +in;
   all signals AC-coupled in (C2/C3 spkr, C4/C5 PicoGUS) and out (C7).

---
**Correction (2026-07-03, design review H6):** the single-supply summer stays,
but the TL072 cannot run it (needs >=+-5 V; JFET input CM excludes V-+4 V, so
2.5 V Vref is out of spec on both counts). U1 is now an MCP6002 (RRIO, CM to
ground) via a value override on the pin-identical TL072 dual-op-amp body.

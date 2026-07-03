# questions-sidecar — SUPERSEDED

The original contents of this file described the first-cut 64-pin sidecar
header (IRQ10/11/14, pin-63 key). That design was replaced by the shared
standard-pinout **60-pin 8-bit ISA header** in `sheets/isa_conn.py` — see
`open-questions.md` ("ISA connector re-based on the standard 8-bit ISA
pinout") for the current pin map and rationale:

- pins 7 / 11 / 15 reclaimed as ~IOCHCK / GND / IRQ8; pin 35 = REFRESH#
- IRQ10/11/14 dropped (not on an 8-bit edge); a sidecar COM4 uses the bus
  IRQ2 line, delivered as IRQ9 via the AT redirect (design doc §11.1/§14)

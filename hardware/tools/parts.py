"""JLCPCB/LCSC sourcing map for mini-xt (verified against the JLC parts DB,
2026-07-03; footprints + package re-check 2026-07-13; 3.3V single-board
rebind 2026-07-14 -- see docs/superpowers/specs/2026-07-14-3v3-single-board-design.md
and hardware/notes/3v3-verification.md for the picks/rationale).

Applied at build time by build.py: every placed component gets an
'LCSC Part Num' property looked up by (lib_id, value), falling back to lib_id
alone. The schematics stay GENERIC (74-series logic, R/C/L, connectors); this
file is where generic symbols bind to the concrete SMD parts JLCPCB will
assemble. Swapping this table (e.g. for a through-hole build) re-targets the
whole BOM without touching a sheet.

Each entry also carries fp = the KiCad footprint ("Lib:Name"), emitted as the
component's Footprint property. Stock KiCad footprints are used wherever one
matches the verified JLC package; "mini-xt:*" footprints do NOT exist yet --
they mark parts whose land pattern must be authored at layout time (import
the EasyEDA footprint via its LCSC number). tools/check_parts.py validates
that every non-custom fp exists in the installed KiCad footprint libs.

Conventions (see CLAUDE.md "Fabrication constraints"):
  * SMD everywhere possible (boards must fit 100x100 mm); THT only for
    connectors/headers/jumpers and the socketed vintage parts.
  * Socketed parts (fab installs the SOCKET; chip goes in by hand): V20
    (DIP-40) only, as of the 3.3V redesign -- the AS6C4008 SRAM and DS12C887
    RTC sockets are gone (SRAM -> IS62WV51216BLL SMD TSOP-44; RTC -> Bus-MCU-
    emulated + small I2C PCF8563, see below). For V20 the LCSC number IS the
    socket; the chip is listed in `note`.
  * Modules (Core2350B, Pico) mount on 2.54 mm female headers.

Substitutions forced by JLC stock (all verified same-pinout):
  * 74HCT374 -> 74HCT574 (no '374 stocked; sheets rewired for the '574)
  * 74HCT157 -> 74HC157, +3.3 V (speed mux): SPEED_SEL drives the select
    DIRECTLY off the 3.3 V MCU GPIO now (clears HC Vih 2.31 V), so the old
    5 V HCT select-inverter is gone and I0a/I1a are UN-swapped (see cpu_core Q5)
  * TCM809   -> TCM809TENB713 (SOT-23, 3.08 V threshold -- 3.3V-rail grade;
    the -450I/TT (4.375 V) pick was wrong, chosen back when this part
    monitored +5V; see notes/questions-cpu_core.md Q9)
  * 2N3904   -> MMBT3904 (SOT-23)
  * TL072    -> MCP6002 (RRIO; pin-identical dual op-amp)
  * 1.8432 MHz canned osc -> crystal on the 16C550's XIN/XOUT
  * 14.31818 MHz osc: only 3.3 V parts stocked -> powered from 3V3. The clock
    tree is now the 3.3 V single-board design: OSC_3V3 clocks the LVC /2+/3
    dividers directly; the U13 HCT04 (still +5 V) squares CLK_MUX up to the
    V20's 5 V CPUCLK and re-buffers READY/HOLD (Task-10). No stale 5 V OSC net.

3.3V single-board redesign (2026-07-14, see notes/3v3-verification.md):
  * DS12C887 + its ISA glue deleted -- RTC emulated in the Bus MCU (ports
    0x70/71); hardware timekeeping is now a PCF8563 I2C RTC + CR2032 on the
    Supervisor, synced over the existing UART link at boot.
  * AS6C4008-55 (DIP-32, user-stock 5V SRAM) -> IS62WV51216BLL (TSOP-44,
    SMD, 2.5-3.6V, in stock at JLC -- no more socket needed).
  * 74HCT163 -> 74LVC161 for the /3 clock divider, 74HCT74 -> 74LVC74A for
    /2 (check 7: neither HC- nor HCT-grade meets fmax margin at 3.3V/
    14.318 MHz; LVC does with wide margin).
  * 74HCT02 -> 74HC02 substitution above is now vestigial (its only prior
    use, RTC decode, is deleted) -- left in place since another sheet may
    still reference plain 74HC02 in the pure-3.3V domain.
  * Octal latches/buffers/FFs needing 5V-tolerant inputs move to LVC grade
    (74LVC573A/244A/574A/125A/245A); pure-3.3V-domain small gates (00/04/32/
    138, plus the already-present 08/165) move to plain HC grade on the same
    HCT-body symbols -- HCT itself needs 4.5-5.5V and no longer works once
    everything is 3.3V.

NOT available at JLC (flagged, no LCSC number):
  * NEC V20 (vintage; user stock)         -> DIP-40 socket placed instead
  * TL16C550CPT (LQFP-48): 0 stock at JLC (both TL16C550CPTR/PTRG4) as of
    2026-07-14 -> source TI direct/Mouser/Digi-Key, like the V20 (but NOT
    socketed -- still a soldered SMD reflow part, just not JLC-supplied)
  * VGA HD15 (DE15) connector             -> other distributor (THT)

Thin stock (check before ordering): MAX3241EEAI+T (0 on 2026-07-15!),
TPS563200DDCR (4!! -- re-verify before ordering or switch to a TPS5632xx
sibling), 74LVC574AT20-13 (~88), 74LVC161PW,118 (~100).

Known part/footprint caveats (all deliberate, resolve at layout):
  * C2897411 female headers are 2x10 strips: right for the Core2350B's
    double-ring PGA, but the Pico needs 2x 1x20 -- swap/add a 1xN part at
    order time.
  * Clone connectors (SHOU HAN USB-C/USB-A/HDMI, XKB barrel, Ckmtw D-sub):
    stock KiCad footprint assigned where the pattern is industry-standard;
    verify against the LCSC drawing before fab.
  * CR2032 holder: no stock KiCad footprint exactly matches CR2032-BS-6;
    a same-family Keystone 1x2032 SMD holder footprint is assigned as a
    placeholder -- verify against the LCSC drawing at layout.
"""

# (lib_id, value) -> entry; or lib_id -> entry as a fallback for all values.
# entry: lcsc (goes into the 'LCSC Part Num' property; '' = leave unset),
#        mpn/package for the BOM reader, fp = KiCad footprint ('' = none,
#        'mini-xt:*' = custom, author at layout), note for humans.
E = lambda lcsc, mpn="", package="", fp="", note="": {
    "lcsc": lcsc, "mpn": mpn, "package": package, "fp": fp, "note": note}

# shared footprint names (all verified present in the KiCad 9 footprint libs)
SOIC14 = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"
SOIC16 = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
SOIC20W = "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
TSSOP14 = "Package_SO:TSSOP-14_4.4x5mm_P0.65mm"
TSSOP16 = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
TSSOP20 = "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
XTAL3225 = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"
PH = "Connector_PinHeader_2.54mm:PinHeader_%s_P2.54mm_Vertical"

PART_MAP = {
    # ---- 74-series glue: 5 V HCT (TTL thresholds read 3.3 V drivers) ----
    ("mini-xt:74HCT00", "74HCT00"):   E("C282337", "74HCT00D,653", "SO-14", SOIC14),
    ("mini-xt:74HCT04", "74HCT04"):   E("C672096", "74HCT04D,653", "SO-14", SOIC14),
    ("mini-xt:74HCT08", "74HCT08"):   E("C5959", "74HCT08D,653", "SOIC-14", SOIC14),
    ("mini-xt:74HCT32", "74HCT32"):   E("C5985", "74HCT32D,653", "SOIC-14", SOIC14),
    ("mini-xt:74HCT74", "74HCT74"):   E("C686657", "74HCT74D,653", "SO-14", SOIC14),
    ("mini-xt:74HCT125", "74HCT125"): E("C5962", "74HCT125D,653", "SOIC-14", SOIC14),
    ("mini-xt:74HCT138", "74HCT138"): E("C5965", "74HCT138D,653", "SOIC-16", SOIC16),
    ("mini-xt:74HCT165", "74HCT165"): E("C456131", "74HCT165D,653", "SOIC-16", SOIC16),
    ("mini-xt:74HCT244", "74HCT244"): E("C5978", "74HCT244D,653", "SOIC-20", SOIC20W),
    ("mini-xt:74HCT245", "74HCT245"): E("C5979", "74HCT245D,653", "SOIC-20", SOIC20W),
    ("mini-xt:74HCT573", "74HCT573"): E("C5209384", "74HCT573D,653", "SOIC-20", SOIC20W),
    ("mini-xt:74HCT574", "74HCT574"): E("C6001", "74HCT574D,653", "SOIC-20", SOIC20W),
    # ---- PicoGUS (on-board, chip-down copy) 2026-07-11 ----
    ("mini-xt:CB3T3257", "CB3T3257"):  E("C544573", "SN74CB3T3257PWR", "TSSOP-16", TSSOP16, "addr/data mux (FET switch)"),
    ("mini-xt:CB3T3245", "CB3T3245"):  E("C15298", "SN74CB3T3245PWR", "TSSOP-20", TSSOP20, "misc level shift (FET switch)"),
    ("mini-xt:74HCT04", "74AHC14"):        E("C54561786", "74AHC14PW-TP", "TSSOP-14", TSSOP14, "3.3V hex Schmitt inverter, 5V-tolerant in"),
    ("mini-xt:74LVC2G06", "74LVC2G06"):    E("C52145914", "74LVC2G06DW-TP", "SOT-23-6", SOT236, "open-drain: IOCHRDY + MIDI"),
    ("mini-xt:PCM5102A", "PCM5102A"):      E("C107671", "PCM5102APWR", "TSSOP-20", TSSOP20, "I2S DAC (PCM5100A-compatible)"),
    ("mini-xt:APS6404L", "APS6404L"):      E("C5333729", "APS6404L-3SQR-SN", "SOP-8", SOIC8, "GUS sample RAM; MUST be -3 (3.0-3.6V) -- the SQN is a 1.8V part"),
    ("Regulator_Linear:AMS1117-3.3", "AMS1117-3.3"): E("C6186", "AMS1117-3.3", "SOT-223",
        "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "PicoGUS local 3V3 island"),
    # ---- HC-grade substitutions (see module docstring for why each is safe)
    ("mini-xt:74HCT02", "74HC02"):    E("C5588", "74HC02D,653", "SOIC-14", SOIC14),
    ("mini-xt:74HCT157", "74HC157"):  E("C5609", "74HC157D,653", "SOIC-16", SOIC16),
    ("mini-xt:74HCT163", "74HC161"):  E("C5610", "74HC161D,653", "SOIC-16", SOIC16),
    ("mini-xt:74HCT08", "74HC08"):    E("C5593", "74HC08D,653", "SOIC-14", SOIC14),
    ("mini-xt:74HCT165", "74HC165"):  E("C5613", "74HC165D,653", "SOIC-16", SOIC16,
                                        "3.3 V domain (HCT is 4.5-5.5 V only)"),
    # ---- 3.3V single-board redesign (2026-07-14 spec): pure-3.3V-domain HC
    # re-buys on the existing HCT bodies (no cross-voltage concern once every
    # input is 3.3V-driven -- HCT itself needs 4.5-5.5V and no longer works) ----
    ("mini-xt:74HCT00", "74HC00"):    E("C699445", "74HC00D", "SOIC-14", SOIC14),
    ("mini-xt:74HCT04", "74HC04"):    E("C86613", "74HC04D", "SOIC-14", SOIC14),
    # 5V-tolerant-input inverter on the '04 body (Task-10 fix): bus_mcu U17
    # inverts the V20's 5V HLDA while itself powered at +3V3 -- plain HC04 is
    # NOT 5V-tolerant; LVC04A is. Same standard '04 pinout, SO-14 like the HC/HCT.
    ("mini-xt:74HCT32", "74HC32"):    E("C52140395", "74HC32D", "SOP-14L", SOIC14,
                                        "verify SOIC-14 footprint match at layout"),
    ("mini-xt:74HCT138", "74HC138"):  E("C5602", "74HC138D,653", "SOIC-16", SOIC16),
    # ---- 3.3V redesign: LVC-grade rebinds (5V-tolerant-input octal parts) ----
    ("mini-xt:74HCT573", "74LVC573A"): E("C6096", "74LVC573APW,118", "TSSOP-20", TSSOP20),
    ("mini-xt:74HCT244", "74LVC244A"): E("C6079", "74LVC244APW,118", "TSSOP-20", TSSOP20),
    ("mini-xt:74HCT574", "74LVC574A"): E("C842658", "74LVC574AT20-13", "TSSOP-20", TSSOP20,
                                         "thin stock (~88) -- re-verify before order"),
    ("mini-xt:74HCT125", "74LVC125A"): E("C6057", "74LVC125AD,118", "SOIC-14", SOIC14),
    ("mini-xt:74HCT245", "74LVC245A"): E("C6082", "74LVC245APW,118", "TSSOP-20", TSSOP20,
                                         "fallback if a sheet overrides this body's value "
                                         "instead of placing mini-xt:74LVC245A directly"),
    # HC-grade alternates for the same three roles (kept alongside the LVC
    # picks above in case a future sheet places the plain HC value instead)
    ("mini-xt:74HCT125", "74HC125"):  E("C52140399", "74HC125D", "SOP-14L", SOIC14,
                                        "verify SOIC-14 footprint match at layout"),
    ("mini-xt:74HCT244", "74HC244"):  E("C52140409", "74HC244D", "SOP-20L", SOIC20W,
                                        "verify SOIC-20 footprint match at layout"),
    ("mini-xt:74HCT245", "74HC245"):  E("C2675537", "74HC245D", "SOIC-20-300mil", SOIC20W),
    # ---- clock dividers move to LVC grade at 3.3V (check 7: HC-grade fmax
    # margin fails at 14.318 MHz on both the 5V and 3.3V rail once moved) ----
    ("mini-xt:74HCT74", "74LVC74A"):  E("C6100", "74LVC74APW,118", "TSSOP-14", TSSOP14),
    ("mini-xt:74HCT163", "74LVC161"): E("C548136", "74LVC161PW,118", "TSSOP-16", TSSOP16,
                                        "thin stock (~100) -- re-verify before order"),
    # 74LVC2G07 (non-inverting open-drain buffer) is pin-identical to the
    # 74LVC2G06 body already authored (same SOT-23-6 pin roles) -- reuse it via
    # value override rather than a new symbol.
    ("mini-xt:74LVC2G06", "74LVC2G07"): E("C24478", "74LVC2G07GW,125", "SOT-23-6", SOT236,
                                          "open-drain: IOCHRDY/IOCHCK (motherboard, distinct "
                                          "role from PicoGUS's 2G06 instance)"),
    # ---- new ICs (3.3V single-board redesign) ----
    ("mini-xt:IS62WV51216", "IS62WV51216BLL"): E("C11315", "IS62WV51216BLL-55TLI",
        "TSOP-II-44", "Package_SO:TSOP-II-44_10.16x18.41mm_P0.8mm"),
    ("mini-xt:TL16C550PT", "TL16C550C"): E("C882798", "TL16C550CPFBR", "TQFP-48(7x7)",
        "Package_QFP:TQFP-48_7x7mm_P0.5mm",
        "active PFB (TQFP-48) revision of the dead PTR -- pinout verified "
        "identical to the mini-xt:TL16C550PT symbol against EasyEDA C882798 "
        "(all 48 pins incl. the 8 NCs, same 7x7 P0.5 land pattern); THIN "
        "extended-part stock (5 @ 2026-07-14), confirm before ordering"),
    ("mini-xt:PCF8563", "PCF8563T"): E("C7440", "PCF8563T/5,518", "SO-8", SOIC8,
        "I2C RTC; Bus MCU emulates ports 0x70/71, time synced over the "
        "existing UART link at boot"),
    ("Device:Battery_Cell", "CR2032"): E("C22363833", "CR2032-BS-6", "SMD",
        "Battery:BatteryHolder_Keystone_1058_1x2032",
        "RTC backup cell; verify exact clip footprint against the LCSC "
        "drawing at layout (no exact BS-6 stock footprint)"),
    # ---- 3.3 V logic ----
    ("mini-xt:74LVC245A", "74LVC245A"): E("C6082", "74LVC245APW,118", "TSSOP-20", TSSOP20),
    ("74xx:74HC595", "74HC595"):      E("C5947", "74HC595D,118", "SOIC-16", SOIC16),
    # ---- ICs ----
    ("mini-xt:MAX3241", "MAX3241"):   E("C406859", "MAX3241EEAI+T", "SSOP-28",
                                        "Package_SO:SSOP-28_5.3x10.2mm_P0.65mm"),
    ("MCU_RaspberryPi:RP2040", "RP2040"): E("C2040", "RP2040", "LQFN-56",
        "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm"),
    ("Memory_Flash:W25Q128JVS", "W25Q128JVS"): E("C97521", "W25Q128JVSIQ", "SOIC-8",
        "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "208-mil wide body"),
    ("mini-xt:TL072", "MCP6002"):     E("C7377", "MCP6002T-I/SN", "SOIC-8", SOIC8),
    ("Power_Supervisor:TCM809", "TCM809"): E("C47195", "TCM809TENB713", "SOT-23", SOT23,
                                             "3.08 V threshold, push-pull ~RST -- 3.3V-rail grade "
                                             "(was wrongly the 4.375V -450I/TT, see Q9)"),
    ("Regulator_Switching:TPS563200", "TPS563200"): E("C97253", "TPS563200DDCR", "TSOT-23-6",
        "Package_TO_SOT_SMD:TSOT-23-6"),
    ("Interface_USB:CH224K", "CH224K"): E("C970725", "CH224K", "ESSOP-10-150mil-1mm",
        "mini-xt:ESSOP-10_150mil_P1.0mm", "no stock KiCad ESSOP-10; import EasyEDA fp at layout"),
    ("Transistor_BJT:2N3904", "2N3904"): E("C20526", "MMBT3904", "SOT-23", SOT23),
    ("Device:Q_PMOS", "Q_PMOS"):      E("C15127", "AO3401A", "SOT-23", SOT23),
    ("Device:D_Schottky", "D_Schottky"): E("C8678", "SS34", "SMA", "Diode_SMD:D_SMA"),
    ("Device:D_Schottky", "SS34"):    E("C8678", "SS34", "SMA", "Diode_SMD:D_SMA"),
    # ---- protection (design review 2026-07-11) ----
    ("Device:Polyfuse", "2A"):    E("C883156", "BSMD1812-200-16V", "1812",
                                    "Fuse:Fuse_1812_4532Metric", "ISA sidecar +5V feed"),
    ("Device:Polyfuse", "3A"):    E("C7500481", "BSMD1812-300-24V", "1812",
                                    "Fuse:Fuse_1812_4532Metric", "USB-C VBUS input"),
    ("Device:D_Zener", "SMBJ5.0A"): E("C19077558", "SMBJ5.0A", "SMB", "Diode_SMD:D_SMB",
                                      "unidirectional 5V-rail clamp TVS"),
    ("Power_Protection:USBLC6-2SC6", "USBLC6-2SC6"): E("C2687116", "USBLC6-2SC6", "SOT-23-6",
                                                       SOT236, "USB host-port ESD array"),
    ("Device:Q_NMOS", "2N7002"):  E("C8545", "2N7002", "SOT-23", SOT23,
                                    "storage IRQ5 tri-state inverter"),
    # (NIC part bindings -- RTL8019AS, AT93C46, 13F-39MNL magnetics, RJ45,
    # 20MHz crystal -- removed with the network sheet 2026-07-14; tag
    # full-board-with-nic has them.)
    # ---- socketed vintage / user-stock parts: LCSC number = the SOCKET ----
    # Machined-pin (round-hole) sockets, all 600 mil row spacing: better grip,
    # repeated-insertion tolerant, gentler on 40-year-old pins than stamped tin.
    ("mini-xt:V20", "V20"):           E("C2874018", "XFCN IC254V-12-40-0743-P1524",
                                        "DIP-40 THT machined",
                                        "Package_DIP:DIP-40_W15.24mm_Socket",
                                        "NEC uPD70108 (user stock) installs in socket"),
    # ---- clock ----
    ("Oscillator:ACO-xxxMHz", "14.31818MHz"): E("C49330311",
                                        "XOS32014318CT00351005", "SMD3225-4P",
                                        "Oscillator:Oscillator_SMD_EuroQuartz_XO32-4Pin_3.2x2.5mm",
                                        "3.3 V part -- powered from 3V3, "
                                        "buffered to 5 V by an HCT gate"),
    ("Device:Crystal", "12MHz"):      E("C9002", "X322512MSB4SI", "SMD3225", XTAL3225, "CL=20pF"),
    ("Device:Crystal", "32.768kHz"):  E("C32346", "Q13FC13500004", "SMD3215-2P",
        "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm",
        "PCF8563 RTC crystal; CL=12.5pF, ESR<=70k (datasheet max Rs=100k) -- "
        "JLC's deepest-stock 32.768kHz part, basic library"),
    ("Device:Crystal", "1.8432MHz"):  E("C47345430", "6A01843AG20UCD", "HC-49U THT",
                                        "Crystal:Crystal_HC49-U_Vertical",
                                        "CL=20pF; on 16C550 XIN/XOUT"),
    # ---- passives (0603 basic unless noted) ----
    ("Device:R_Pack04", "10kx4"): E("C29718", "4D03WGJ0103T5E", "0603x4",
        "Resistor_SMD:R_Array_Convex_4x0603",
        "basic 4x isolated 10k array (2026-07-14 pull consolidation; ±5% is "
        "fine for pulls). Also de-risks the discrete 10k line, which moved "
        "to 0805 C17414 when 0603 C25804 hit 0 stock (2026-07-15)."),
    ("Device:R_Pack04", "4.7kx4"): E("C1980", "4D03WGJ0472T5E", "0603x4",
        "Resistor_SMD:R_Array_Convex_4x0603",
        "basic 4x isolated 4.7k array (LPT printer-status pulls)"),
    ("Device:R", "27"):    E("C25190", "0603WAF270JT5E", "0603", R0603, "RP2040 USB series termination"),
    ("Device:R", "100"):   E("C22775", "0603WAF1000T5E", "0603", R0603),
    ("Device:R", "15k"):   E("C22809", "0603WAF1502T5E", "0603", R0603),
    ("Device:R", "10k"):   E("C17414", "0805W8F1002T5E", "0805", R0805,
        "0805, not 0603: the only in-stock BASIC 10k lines are 0805/1206 "
        "(0603 C25804 hit 0 stock 2026-07-15; 11.9M stock on this one)"),
    ("Device:R", "1k"):    E("C21190", "0603WAF1001T5E", "0603", R0603),
    ("Device:R", "270"):   E("C22966", "0603WAF2700T5E", "0603", R0603),
    ("Device:R", "2k"):    E("C22975", "0603WAF2001T5E", "0603", R0603),
    ("Device:R", "33k"):   E("C4216", "0603WAF3302T5E", "0603", R0603),
    ("Device:R", "4.7k"):  E("C23162", "0603WAF4701T5E", "0603", R0603),
    ("Device:R", "5.1k"):  E("C23186", "0603WAF5101T5E", "0603", R0603),
    ("Device:R", "510"):   E("C23193", "0603WAF5100T5E", "0603", R0603),
    ("Device:R", "470"):   E("C23179", "0603WAF4700T5E", "0603", R0603, "VGA blue ladder MSB; PicoGUS DAC filters"),
    ("Device:R", "820"):   E("C23253", "0603WAF8200T5E", "0603", R0603, "VGA blue ladder LSB"),
    ("Device:R", "20k"):   E("C4184", "0603WAF2002T5E", "0603", R0603, "audio summer PG_L/PG_R (0.5x)"),
    ("Device:R", "100k"):  E("C25803", "0603WAF1003T5E", "0603", R0603),
    ("Device:C", "100nF"): E("C14663", "CC0603KRX7R9BB104", "0603", C0603),
    ("Device:C", "10nF"):  E("C57112", "0603B103K500NT", "0603", C0603),
    ("Device:C", "1uF"):   E("C15849", "CL10A105KB8NNNC", "0603", C0603),
    ("Device:C", "30pF"):  E("C1658", "0603CG300J500NT", "0603", C0603, "12MHz crystal load (CL=20pF)"),
    ("Device:C", "22pF"):  E("C1653", "CL10C220JB8NNNC", "0603", C0603),
    ("Device:C", "2.2nF"): E("C1604", "0603B222K500NT", "0603", C0603),
    ("Device:C", "2.2uF"): E("C23630", "CL10A225KO8NNNC", "0603", C0603),
    ("Device:C", "47uF"):  E("C16780", "CL21A476MQYNNNE", "0805", C0805),
    ("Device:C", "10uF"):  E("C15850", "CL21A106KAYNNNE", "0805", C0805),
    ("Device:C_Polarized", "22uF"): E("C12891", "CL31A226KAHNNNE", "1206", C1206,
                                      "MLCC replaces the polarized symbol"),
    ("Device:C_Polarized", "100uF"): E("C2887276", "RVT100UF16V67RV0016", "SMD D6.3xL5.4",
                                       "Capacitor_SMD:CP_Elec_6.3x5.4",
                                       "alu electrolytic; USB host VBUS bulk"),
    ("Device:L", "2.2uH"): E("C602029", "FHD4020S-2R2MT", "SMD 4x4",
                             "Inductor_SMD:L_Taiyo-Yuden_NR-40xx",
                             "4.8 A rated for the TPS563200 buck; NR-40xx pad "
                             "pattern fits the 4x4 FHD4020S -- verify at layout"),
    ("Device:LED", "5V"):  E("C2286", "KT-0603R", "0603", "LED_SMD:LED_0603_1608Metric"),
    ("Device:LED", "3V3"): E("C2286", "KT-0603R", "0603", "LED_SMD:LED_0603_1608Metric"),
    ("Device:LED", "LED"): E("C2286", "KT-0603R", "0603", "LED_SMD:LED_0603_1608Metric",
                             "PicoGUS status LED"),
    ("Device:FerriteBead", "120R@100MHz"): E("C14709", "BLM18PG121SN1D", "0603",
                                             "Inductor_SMD:L_0603_1608Metric",
        "basic-library swap 2026-07-14 (was extended BLM18KG101TN1D 100R): "
        "same Murata 0603 family, 120R@100MHz, 2A -- plenty for the AVDD "
        "supply-filter roles on picogus"),
    ("Device:Polyfuse", "500mA"): E("C46641014", "SMD1206-050-16", "1206",
                                    "Fuse:Fuse_1206_3216Metric"),
    # ---- connectors ----
    ("Connector:USB_C_Receptacle", "USB_C_Receptacle"): E("C2765186",
                                        "TYPE-C 16PIN 2MD(073)", "SMD 16P",
                                        "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
                                        "clone of the HRO 16-pin -- verify drawing at layout"),
    ("Connector:USB_C_Receptacle", "USB_PROG"): E("C2765186",
                                        "TYPE-C 16PIN 2MD(073)", "SMD 16P",
                                        "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
                                        "supervisor programming port, same receptacle"),
    ("Connector:USB_A", "USB_HOST"):  E("C456015", "AF 180 ZJB13.7", "THT",
                                        "Connector_USB:USB_A_Stewart_SS-52100-001_Horizontal",
                                        "generic THT USB-A pattern -- verify drawing at layout"),
    ("Connector:Barrel_Jack", "5V jack"): E("C2880552", "DC-016-2.5A-2.0",
                                        "THT 5.5/2.0mm",
                                        "Connector_BarrelJack:BarrelJack_Horizontal",
                                        "verify pin pitch vs XKB DC-016 drawing at layout"),
    ("Connector:DE9_Pins", "DE9_Pins"): E("C141880", "D-DMR009PM-D002",
                                        "DB9 male right-angle THT",
                                        "Connector_Dsub:DSUB-9_Pins_Horizontal_P2.77x2.84mm_EdgePinOffset9.90mm_Housed_MountingHolesOffset11.32mm"),
    ("Connector:DB25_Pins", "DB25_Pins"): E("C190083", "D-DMR025PF-D002",
                                        "DB25 female right-angle THT",
                                        "Connector_Dsub:DSUB-25_Socket_Horizontal_P2.77x2.84mm_EdgePinOffset9.90mm_Housed_MountingHolesOffset11.32mm",
                                        "Ckmtw, same D-DMR series as the DE9; swapped from Amphenol "
                                        "DB25S564CTLF (C5400534, stock ~10) 2026-07-16. FEMALE, so the "
                                        "footprint is the _Socket_ variant (the old binding wrongly used "
                                        "_Pins_/male, which mirrors the pinout). Drawing: 2.77x2.84 pitch, "
                                        "3.18mm holes 1.42mm off the pin row -- verify edge offset at layout"),
    ("Connector:HDMI_A", "HDMI_A"):   E("C2858275", "HDMI 19PIN 043", "SMD",
                                        "mini-xt:HDMI_A_SHOUHAN_043",
                                        "custom fp -- import EasyEDA at layout"),
    ("Connector_Generic:Conn_02x25_Odd_Even", "Conn_02x25_Odd_Even"):
        E("C2962036", "HYCW01-CF50-395B", "SMD",
          "mini-xt:CF_HYCW01-CF50-395B",
          "CompactFlash socket (True-IDE); real CF footprint at layout"),
    ("Connector_Generic:Conn_02x20_Odd_Even", "IDE 40-pin (boxed)"):
        E("C9138", "2.54-2*20P straight IDC box header", "THT",
          "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical",
          "shrouded/polarized for IDE ribbons; clip pin 20 for keyed cables"),
    ("Connector_Generic:Conn_02x05_Odd_Even", "DIS block (2x5)"):
        E("C492422", "PZ254V-12-10P", "THT",
          PH % "2x05",
          "addr_decode disable-jumper block: ONE fixed 2x5 male header "
          "(pos 1-5 = COM1/COM2/LPT/IDE/VID), not a breakaway strip"),
    ("Connector_Generic:Conn_02x25_Odd_Even", "ISA 8-bit (50p)"):
        E("C21262364", "X6521FR-2x25-C85D32", "THT right-angle",
          "Connector_PinSocket_2.54mm:PinSocket_2x25_P2.54mm_Horizontal",
          "expansion port: 90-deg FEMALE socket (cards/backplane plug in "
          "edge-on with male pins); ~350 stock -- verify before ordering"),
    ("Connector_Generic:Conn_01x15", "VGA HD15"):
        E("", "DE15 HD15 female", "THT",
          "Connector_Dsub:DSUB-15-HD_Socket_Horizontal_P2.29x2.54mm_EdgePinOffset8.35mm_Housed_MountingHolesOffset10.89mm",
          "NOT stocked at JLC -- source elsewhere or HDMI-only build"),
    # (Bus_ISA_8bit card-edge socket entry deleted 2026-07-14 with the
    # card_isatest dev card, its only user.)
}

# Fallbacks by lib_id alone (any value). Headers/jumpers are cut-to-length
# 2.54 mm breakaway strips; modules get female-header sockets.
LIBID_MAP = {
    "Connector_Generic:Conn_01x02": E("C2337", "1x40 2.54mm header (break to 2)", "THT", PH % "1x02"),
    "Connector_Generic:Conn_01x03": E("C2337", "1x40 2.54mm header (break to 3)", "THT", PH % "1x03"),
    "Connector_Generic:Conn_01x04": E("C2337", "1x40 2.54mm header (break to 4)", "THT", PH % "1x04"),
    "Connector_Generic:Conn_01x08": E("C2337", "1x40 2.54mm header (break to 8)", "THT", PH % "1x08"),
    "Connector_Generic:Conn_01x10": E("C2337", "1x40 2.54mm header (break to 10)", "THT", PH % "1x10"),
    "Connector_Generic:Conn_02x04_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x4)", "THT", PH % "2x04"),
    "Connector_Generic:Conn_02x20_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x20)", "THT", PH % "2x20"),
    # (No Conn_02x25 fallback: both 2x25 users are tuple-bound above -- the CF
    # socket by its default value, the expansion port by "ISA 8-bit (50p)".
    # The 2x30 entry retired with the 60-pin header, 2026-07-14.)
    "Switch:SW_Push": E("C318884", "TS-1187A-B-A-B", "SMD 5.1x5.1",
                        "mini-xt:SW_TS-1187A_5.1x5.1mm",
                        "BOOTSEL buttons; custom fp -- import EasyEDA at layout"),
    "Switch:SW_Slide_DPDT": E("C431544", "MST22D18G2", "SMD 9.1x3.6",
                              "mini-xt:SW_MST22D18G2_9.1x3.6mm",
                              "programming-port selector; custom fp -- import EasyEDA at layout"),
    "mini-xt:Core2350B": E("C2897411", "PM254 2.54mm female headers", "THT",
                           "mini-xt:Core2350B_PGA",
                           "module is a DOUBLE-RING PGA (25.4mm sq, no "
                           "castellations): dual-row 2xN female strips per "
                           "side; cannot be SMD-mounted; custom fp at layout"),
    "mini-xt:Pico": E("C2897411", "PM254 2.54mm female headers", "THT",
                      "Module:RaspberryPi_Pico_Common_THT",
                      "module socket -- needs 2x 1x20 female strips, NOT the "
                      "2x10 C2897411 -- swap part at order time"),
}


def lookup(lib_id, value):
    e = PART_MAP.get((lib_id, value))
    if e is None:
        e = LIBID_MAP.get(lib_id)
    return e


def apply(sch):
    """Attach 'LCSC Part Num' + Footprint properties to every mapped component."""
    n = 0
    for c in sch.components:
        e = lookup(c.lib_id, c.value)
        if e:
            if e["lcsc"]:
                c.props["LCSC Part Num"] = e["lcsc"]
                n += 1
            if e["fp"]:
                c.props["Footprint"] = e["fp"]
    return n

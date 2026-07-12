"""JLCPCB/LCSC sourcing map for mini-xt (verified against the JLC parts DB,
2026-07-03).

Applied at build time by build.py: every placed component gets an
'LCSC Part Num' property looked up by (lib_id, value), falling back to lib_id
alone. The schematics stay GENERIC (74-series logic, R/C/L, connectors); this
file is where generic symbols bind to the concrete SMD parts JLCPCB will
assemble. Swapping this table (e.g. for a through-hole build) re-targets the
whole BOM without touching a sheet.

Conventions (see CLAUDE.md "Fabrication constraints"):
  * SMD everywhere possible (boards must fit 100x100 mm); THT only for
    connectors/headers/jumpers and the socketed vintage parts.
  * Socketed parts (fab installs the SOCKET; chip goes in by hand): V20
    (DIP-40), 2x AS6C4008-55 SRAM (DIP-32), DS12C887 RTC (DIP-24 600 mil).
    For these the LCSC number IS the socket; the chip is listed in `note`.
  * Modules (Core2350B, Pico) mount on 2.54 mm female headers.

Substitutions forced by JLC stock (all verified same-pinout):
  * 74HCT374 -> 74HCT574 (no '374 stocked; sheets rewired for the '574)
  * 74HCT163 -> 74HC161 at 3.3 V (bus_mcu counters) / 5 V (dividers)
  * 74HCT157 -> 74HC157 + HCT-buffered 3.3 V selects (I0/I1 swapped)
  * 74HCT02  -> 74HC02 (RTC decode -- all inputs are 5 V address lines)
  * TCM809   -> MCP809T-450I (SOT-23, 4.375 V threshold)
  * 2N3904   -> MMBT3904 (SOT-23)
  * TL072    -> MCP6002 (RRIO; pin-identical dual op-amp)
  * 1.8432 MHz canned osc -> crystal on the 16C550's XIN/XOUT
  * 14.31818 MHz osc: only 3.3 V parts stocked -> powered from 3V3, squared
    up through a spare HCT gate

NOT available at JLC (flagged, no LCSC number):
  * NEC V20 (vintage; user stock)         -> DIP-40 socket placed instead
  * AS6C4008-55 (5 V SRAM; user stock)    -> DIP-32 sockets placed instead
  * 8-bit ISA card-edge slot (card_isatest J1) -> consign / other distributor
  * VGA HD15 (DE15) connector             -> other distributor (THT)

Thin stock (check before ordering): TL16C550DPTR (~18), DB25 (~10),
MAX3241EEAI+T (~175), DS12C887+ (~573), TPS563200DDCR (4!! -- re-verify before
ordering or switch to a TPS5632xx sibling).
"""

# (lib_id, value) -> entry; or lib_id -> entry as a fallback for all values.
# entry: lcsc (goes into the 'LCSC Part Num' property; '' = leave unset),
#        mpn/package for the BOM reader, note for humans.
E = lambda lcsc, mpn="", package="", note="": {
    "lcsc": lcsc, "mpn": mpn, "package": package, "note": note}

PART_MAP = {
    # ---- 74-series glue: 5 V HCT (TTL thresholds read 3.3 V drivers) ----
    ("mini-xt:74HCT00", "74HCT00"):   E("C282337", "74HCT00D,653", "SO-14"),
    ("mini-xt:74HCT04", "74HCT04"):   E("C672096", "74HCT04D,653", "SO-14"),
    ("mini-xt:74HCT08", "74HCT08"):   E("C5959", "74HCT08D,653", "SOIC-14"),
    ("mini-xt:74HCT32", "74HCT32"):   E("C5985", "74HCT32D,653", "SOIC-14"),
    ("mini-xt:74HCT74", "74HCT74"):   E("C686657", "74HCT74D,653", "SO-14"),
    ("mini-xt:74HCT125", "74HCT125"): E("C5962", "74HCT125D,653", "SOIC-14"),
    ("mini-xt:74HCT138", "74HCT138"): E("C5965", "74HCT138D,653", "SOIC-16"),
    ("mini-xt:74HCT165", "74HCT165"): E("C456131", "74HCT165D,653", "SOIC-16"),
    ("mini-xt:74HCT244", "74HCT244"): E("C5978", "74HCT244D,653", "SOIC-20"),
    ("mini-xt:74HCT245", "74HCT245"): E("C5979", "74HCT245D,653", "SOIC-20"),
    ("mini-xt:74HCT573", "74HCT573"): E("C5209384", "74HCT573D,653", "SOIC-20"),
    ("mini-xt:74HCT574", "74HCT574"): E("C6001", "74HCT574D,653", "SOIC-20"),
    # ---- PicoGUS (on-board, chip-down copy) 2026-07-11 ----
    ("mini-xt:CB3T3257", "SN74CB3T3257"):  E("C544573", "SN74CB3T3257PWR", "TSSOP-16", "addr/data mux (FET switch)"),
    ("mini-xt:CB3T3245", "SN74CB3T3245"):  E("C15298", "SN74CB3T3245PWR", "TSSOP-20", "misc level shift (FET switch)"),
    ("mini-xt:74HCT04", "74AHC14"):        E("C54561786", "74AHC14PW-TP", "TSSOP-14", "3.3V hex Schmitt inverter, 5V-tolerant in"),
    ("mini-xt:74HCT00", "74LVC00"):        E("C526338", "74LVC00AS14-13", "SO-14", "3.3V NAND, 5V-tolerant in; THIN stock (~125)"),
    ("mini-xt:74LVC2G06", "74LVC2G06"):    E("C52145914", "74LVC2G06DW-TP", "SOT-23-6", "open-drain: IOCHRDY + MIDI"),
    ("mini-xt:PCM5102A", "PCM5102A"):      E("C107671", "PCM5102APWR", "TSSOP-20", "I2S DAC (PCM5100A-compatible)"),
    ("mini-xt:APS6404L", "APS6404L-3SQR"): E("C5333729", "APS6404L-3SQR-SN", "SOP-8", "GUS sample RAM; MUST be -3 (3.0-3.6V) -- the SQN is a 1.8V part"),
    ("Regulator_Linear:AMS1117-3.3", "AMS1117-3.3"): E("C6186", "AMS1117-3.3", "SOT-223", "PicoGUS local 3V3 island"),
    # ---- HC-grade substitutions (see module docstring for why each is safe)
    ("mini-xt:74HCT02", "74HC02"):    E("C5588", "74HC02D,653", "SOIC-14"),
    ("mini-xt:74HCT157", "74HC157"):  E("C5609", "74HC157D,653", "SOIC-16"),
    ("mini-xt:74HCT163", "74HC161"):  E("C5610", "74HC161D,653", "SOIC-16"),
    ("mini-xt:74HCT08", "74HC08"):    E("C5593", "74HC08D,653", "SOIC-14"),
    ("mini-xt:74HCT165", "74HC165"):  E("C5613", "74HC165D,653", "SOIC-16",
                                        "3.3 V domain (HCT is 4.5-5.5 V only)"),
    # ---- 3.3 V logic ----
    ("mini-xt:74LVC245A", "74LVC245A"): E("C6082", "74LVC245APW,118", "TSSOP-20"),
    ("74xx:74HC595", "74HC595"):      E("C5947", "74HC595D,118", "SOIC-16"),
    # ---- ICs ----
    ("mini-xt:MAX3241", "MAX3241"):   E("C406859", "MAX3241EEAI+T", "SSOP-28"),
    # 16550: fab places an SMD PLCC-44 SOCKET (reflows with everything else);
    # the UART itself is a TL16C550CFNR (PLCC-44, Active at Mouser ~$4-6, or
    # JLC C2653193 TL16C550CIFNR) installed by hand. One footprint accepts
    # new TI parts, NOS tubes, and period NS16550AFN pulls, and a suspect
    # UART is diagnosed by swap. (MaxLinear's PLCC ST16C550CJ44-F is EOL.)
    ("Interface_UART:16550", "16550"): E("C2828044", "Nextron Z-15144001280000",
                                         "PLCC-44 SMD socket",
                                         "chip = TL16C550CFNR (consign/global "
                                         "sourcing); PLCC-44 pin map differs "
                                         "from the DIP-40 symbol -- map at layout"),
    ("MCU_RaspberryPi:RP2040", "RP2040"): E("C2040", "RP2040", "LQFN-56"),
    ("Memory_Flash:W25Q128JVS", "W25Q128JVS"): E("C97521", "W25Q128JVSIQ", "SOIC-8"),
    ("mini-xt:TL072", "MCP6002"):     E("C7377", "MCP6002T-I/SN", "SOIC-8"),
    ("Power_Supervisor:TCM809", "TCM809"): E("C511285", "MCP809T-450I/TT", "SOT-23",
                                             "4.375 V threshold, push-pull ~RST"),
    ("Regulator_Switching:TPS563200", "TPS563200"): E("C97253", "TPS563200DDCR", "TSOT-23-6"),
    ("Interface_USB:CH224K", "CH224K"): E("C970725", "CH224K", "ESSOP-10"),
    ("Transistor_BJT:2N3904", "2N3904"): E("C20526", "MMBT3904", "SOT-23"),
    ("Device:Q_PMOS", "Q_PMOS"):      E("C15127", "AO3401A", "SOT-23"),
    ("Device:D_Schottky", "D_Schottky"): E("C8678", "SS34", "SMA"),
    # ---- protection (design review 2026-07-11) ----
    ("Device:Polyfuse", "2A"):    E("C883156", "BSMD1812-200-16V", "1812", "ISA sidecar +5V feed"),
    ("Device:Polyfuse", "3A"):    E("C7500481", "BSMD1812-300-24V", "1812", "USB-C VBUS input"),
    ("Device:D_Zener", "SMBJ5.0A"): E("C19077558", "SMBJ5.0A", "SMB", "unidirectional 5V-rail clamp TVS"),
    ("Power_Protection:USBLC6-2SC6", "USBLC6-2SC6"): E("C2687116", "USBLC6-2SC6", "SOT-23-6", "USB host-port ESD array"),
    ("Device:Q_NMOS", "2N7002"):  E("C8545", "2N7002", "SOT-23", "storage IRQ5 tri-state inverter"),
    # ---- network (NE2000, ISA8019 transcription) 2026-07-12 ----
    ("mini-xt:RTL8019AS", "RTL8019AS"): E("C22465363", "RTL8019AS-LF_R", "TQFP-100",
        "NE2000 NIC. Alt C10016 (~$11) had only 4 pcs on 2026-07-12; C22465363 (~$19.5, 202 pcs) is the safe bind -- re-check both at order time"),
    ("mini-xt:AT93C46", "AT93C46"): E("C6499", "AT93C46DN-SH-T", "SOIC-8",
        "NIC MAC EEPROM; ships blank -- program once with RSET8019.EXE"),
    ("mini-xt:13F-39MNL", "13F-39MNL"): E("C115949", "13F-39MNL", "SMD-16",
        "10BaseT magnetics, as ISA8019 upstream"),
    ("mini-xt:RJ45_LED", "RJ45_LED"): E("C386757", "R-RJ45R08P-C000", "RJ45 TH right-angle",
        "shielded + 2 LEDs; successor to upstream C133529 (EOL)"),
    ("Device:Crystal", "20MHz"): E("C110936", "X322520MSB4SI", "SMD-3225",
        "NIC 20 MHz crystal, as ISA8019 upstream"),
    # ---- socketed vintage / user-stock parts: LCSC number = the SOCKET ----
    # Machined-pin (round-hole) sockets, all 600 mil row spacing: better grip,
    # repeated-insertion tolerant, gentler on 40-year-old pins than stamped tin.
    ("mini-xt:V20", "V20"):           E("C2874018", "XFCN IC254V-12-40-0743-P1524",
                                        "DIP-40 THT machined",
                                        "NEC uPD70108 (user stock) installs in socket"),
    ("Memory_RAM:AS6C4008-55PCN", "AS6C4008-55PCN"): E("C2874017",
                                        "XFCN IC254V-12-32-0743-P1524",
                                        "DIP-32 THT machined",
                                        "AS6C4008-55PC (user stock) installs in socket"),
    ("mini-xt:DS12C887", "DS12C887"): E("C2684765", "XKB X5621FV-2x12-C1524D7430",
                                        "DIP-24 THT machined",
                                        "DS12C887+ chip = LCSC C9869 (extended)"),
    # ---- modules on female headers ----
    ("mini-xt:Core2350B",):           None,  # placeholder, see fallbacks below
    # ---- clock ----
    ("Oscillator:ACO-xxxMHz", "14.31818MHz"): E("C49330311",
                                        "XOS32014318CT00351005", "SMD3225",
                                        "3.3 V part -- powered from 3V3, "
                                        "buffered to 5 V by an HCT gate"),
    ("Device:Crystal", "12MHz"):      E("C9002", "X322512MSB4SI", "SMD3225", "CL=20pF"),
    ("Device:Crystal", "1.8432MHz"):  E("C47345430", "6A01843AG20UCD", "HC-49U THT",
                                        "CL=20pF; on 16C550 XIN/XOUT"),
    # ---- passives (0603 basic unless noted) ----
    ("Device:R", "27"):    E("C25190", "0603WAF270JT5E", "0603", "RP2040 USB series termination"),
    ("Device:R", "100"):   E("C22775", "0603WAF1000T5E", "0603"),
    ("Device:R", "15k"):   E("C22809", "0603WAF1502T5E", "0603"),
    ("Device:R", "10k"):   E("C25804", "0603WAF1002T5E", "0603"),
    ("Device:R", "1k"):    E("C21190", "0603WAF1001T5E", "0603"),
    ("Device:R", "270"):   E("C22966", "0603WAF2700T5E", "0603"),
    ("Device:R", "2k"):    E("C22975", "0603WAF2001T5E", "0603"),
    ("Device:R", "33k"):   E("C4216", "0603WAF3302T5E", "0603"),
    ("Device:R", "27k"):   E("C22967", "0603WAF2702T5E", "0603", "NIC SLOT16 8-bit strap"),
    ("Device:R", "1M"):    E("C22935", "0603WAF1004T5E", "0603", "NIC crystal bias"),
    ("Device:R", "200"):   E("C8218", "0603WAF2000T5E", "0603", "NIC TPIN termination"),
    ("Device:R", "4.7k"):  E("C23162", "0603WAF4701T5E", "0603"),
    ("Device:R", "5.1k"):  E("C23186", "0603WAF5101T5E", "0603"),
    ("Device:R", "510"):   E("C23193", "0603WAF5100T5E", "0603"),
    ("Device:R", "470"):   E("C23179", "0603WAF4700T5E", "0603", "VGA blue ladder MSB; PicoGUS DAC filters"),
    ("Device:R", "820"):   E("C23253", "0603WAF8200T5E", "0603", "VGA blue ladder LSB"),
    ("Device:R", "20k"):   E("C4184", "0603WAF2002T5E", "0603", "audio summer PG_L/PG_R (0.5x)"),
    ("Device:R", "100k"):  E("C25803", "0603WAF1003T5E", "0603"),
    ("Device:C", "100nF"): E("C14663", "CC0603KRX7R9BB104", "0603"),
    ("Device:C", "47nF"):  E("C1622", "CL10B473KB8NNNC", "0603", "MAX3241 C1 at 5V"),
    ("Device:C", "330nF"): E("C1615", "0603B334K250NT", "0603", "MAX3241 C2-C4 at 5V"),
    ("Device:C", "10nF"):  E("C57112", "0603B103K500NT", "0603"),
    ("Device:C", "1uF"):   E("C15849", "CL10A105KB8NNNC", "0603"),
    ("Device:C", "30pF"):  E("C1658", "0603CG300J500NT", "0603", "12MHz crystal load (CL=20pF)"),
    ("Device:C", "22pF"):  E("C1653", "CL10C220JB8NNNC", "0603"),
    ("Device:C", "20pF"):  E("C1648", "CL10C200JB8NNNC", "0603", "NIC 20 MHz crystal load"),
    ("Device:C", "1nF"):   E("C1588", "CL10B102KB8NNNC", "0603", "NIC magnetics center-tap bypass"),
    ("Device:C", "2.2nF"): E("C1604", "0603B222K500NT", "0603"),
    ("Device:C", "2.2uF"): E("C23630", "CL10A225KO8NNNC", "0603"),
    ("Device:C", "47uF"):  E("C16780", "CL21A476MQYNNNE", "0805"),
    ("Device:C", "10uF"):  E("C15850", "CL21A106KAYNNNE", "0805"),
    ("Device:C_Polarized", "22uF"): E("C12891", "CL31A226KAHNNNE", "1206",
                                      "MLCC replaces the polarized symbol"),
    ("Device:C_Polarized", "100uF"): E("C2887276", "RVT100UF16V67RV0016", "SMD D6.3xL5.4",
                                       "alu electrolytic; USB host VBUS bulk"),
    ("Device:L", "2.2uH"): E("C602029", "FHD4020S-2R2MT", "SMD 4x4",
                             "4.8 A rated for the TPS563200 buck"),
    ("Device:LED", "5V"):  E("C2286", "KT-0603R", "0603"),
    ("Device:LED", "3V3"): E("C2286", "KT-0603R", "0603"),
    ("Device:FerriteBead", "100R@100MHz"): E("C160981", "BLM18KG101TN1D", "0603"),
    ("Device:Polyfuse", "500mA"): E("C46641014", "SMD1206-050-16", "1206"),
    # ---- connectors ----
    ("Connector:USB_C_Receptacle", "USB_C_Receptacle"): E("C2765186",
                                        "TYPE-C 16PIN 2MD(073)", "SMD 16P"),
    ("Connector:USB_A", "USB_HOST"):  E("C456015", "AF 180 ZJB13.7", "THT"),
    ("Connector:Barrel_Jack", "5V jack"): E("C2880552", "DC-016-2.5A-2.0",
                                        "THT 5.5/2.0mm"),
    ("Connector:DE9_Pins", "DE9_Pins"): E("C141880", "D-DMR009PM-D002",
                                        "DB9 male right-angle THT"),
    ("Connector:DB25_Pins", "DB25_Pins"): E("C5400534", "DB25S564CTLF", "THT",
                                        "thin stock (~10) -- verify or substitute"),
    ("Connector:HDMI_A", "HDMI_A"):   E("C2858275", "HDMI 19PIN 043", "SMD"),
    ("Connector_Generic:Conn_02x25_Odd_Even", "Conn_02x25_Odd_Even"):
        E("C2962036", "HYCW01-CF50-395B", "SMD",
          "CompactFlash socket (True-IDE); real CF footprint at layout"),
    ("Connector_Generic:Conn_01x15", "VGA HD15"):
        E("", "DE15 HD15 female", "THT",
          "NOT stocked at JLC -- source elsewhere or HDMI-only build"),
    ("Connector:Bus_ISA_8bit", "ISA slot (8-bit)"):
        E("", "8-bit ISA card-edge socket", "THT",
          "NOT stocked at JLC -- consign (e.g. EDAC 305/CONNFLY 3.96mm)"),
    ("mini-xt:Core2350B",):           None,
}
# drop the placeholder keys used only for documentation flow above
PART_MAP = {k: v for k, v in PART_MAP.items() if v is not None}

# Fallbacks by lib_id alone (any value). Headers/jumpers are cut-to-length
# 2.54 mm breakaway strips; modules get female-header sockets.
LIBID_MAP = {
    "Connector_Generic:Conn_01x02": E("C2337", "1x40 2.54mm header (break to 2)", "THT"),
    "Connector_Generic:Conn_01x03": E("C2337", "1x40 2.54mm header (break to 3)", "THT"),
    "Connector_Generic:Conn_01x04": E("C2337", "1x40 2.54mm header (break to 4)", "THT"),
    "Connector_Generic:Conn_01x08": E("C2337", "1x40 2.54mm header (break to 8)", "THT"),
    "Connector_Generic:Conn_01x10": E("C2337", "1x40 2.54mm header (break to 10)", "THT"),
    "Connector_Generic:Conn_02x04_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x4)", "THT"),
    "Connector_Generic:Conn_02x20_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x20)", "THT"),
    "Connector_Generic:Conn_02x30_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x30)", "THT"),
    "Switch:SW_Push": E("C318884", "TS-1187A-B-A-B", "SMD 5.1x5.1", "BOOTSEL buttons"),
    "Switch:SW_Slide_DPDT": E("C431544", "MST22D18G2", "SMD 9.1x3.6", "programming-port selector"),
    "mini-xt:Core2350B": E("C2897411", "PM254 2.54mm female headers", "THT",
                           "module is a DOUBLE-RING PGA (25.4mm sq, no "
                           "castellations): dual-row 2xN female strips per "
                           "side; cannot be SMD-mounted"),
    "mini-xt:Pico": E("C2897411", "PM254 2.54mm female headers", "THT",
                      "module socket -- 2x 1x20 strips"),
}


def lookup(lib_id, value):
    e = PART_MAP.get((lib_id, value))
    if e is None:
        e = LIBID_MAP.get(lib_id)
    return e


def apply(sch):
    """Attach 'LCSC Part Num' properties to every mapped component."""
    n = 0
    for c in sch.components:
        e = lookup(c.lib_id, c.value)
        if e and e["lcsc"]:
            c.props["LCSC Part Num"] = e["lcsc"]
            n += 1
    return n

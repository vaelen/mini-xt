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
MAX3241EEAI+T (~175), DS12C887+ (~573), TPS563200DDCR (~256).
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
    ("Device:R", "10k"):   E("C25804", "0603WAF1002T5E", "0603"),
    ("Device:R", "1k"):    E("C21190", "0603WAF1001T5E", "0603"),
    ("Device:R", "270"):   E("C22966", "0603WAF2700T5E", "0603"),
    ("Device:R", "2k"):    E("C22975", "0603WAF2001T5E", "0603"),
    ("Device:R", "33k"):   E("C4216", "0603WAF3302T5E", "0603"),
    ("Device:R", "4.7k"):  E("C23162", "0603WAF4701T5E", "0603"),
    ("Device:R", "5.1k"):  E("C23186", "0603WAF5101T5E", "0603"),
    ("Device:R", "510"):   E("C23193", "0603WAF5100T5E", "0603"),
    ("Device:C", "100nF"): E("C14663", "CC0603KRX7R9BB104", "0603"),
    ("Device:C", "10nF"):  E("C57112", "0603B103K500NT", "0603"),
    ("Device:C", "1uF"):   E("C15849", "CL10A105KB8NNNC", "0603"),
    ("Device:C", "15pF"):  E("C1644", "CL10C150JB8NNNC", "0603",
                             "verify against 12 MHz crystal CL at layout"),
    ("Device:C", "22pF"):  E("C1653", "CL10C220JB8NNNC", "0603"),
    ("Device:C", "10uF"):  E("C15850", "CL21A106KAYNNNE", "0805"),
    ("Device:C_Polarized", "22uF"): E("C12891", "CL31A226KAHNNNE", "1206",
                                      "MLCC replaces the polarized symbol"),
    ("Device:L", "2.2uH"): E("C602029", "FHD4020S-2R2MT", "SMD 4x4",
                             "4.8 A rated for the TPS563200 buck"),
    ("Device:LED", "5V"):  E("C2286", "KT-0603R", "0603"),
    ("Device:LED", "3V3"): E("C2286", "KT-0603R", "0603"),
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
    "Connector_Generic:Conn_01x03": E("C2337", "1x40 2.54mm header (break to 3)", "THT"),
    "Connector_Generic:Conn_01x04": E("C2337", "1x40 2.54mm header (break to 4)", "THT"),
    "Connector_Generic:Conn_01x08": E("C2337", "1x40 2.54mm header (break to 8)", "THT"),
    "Connector_Generic:Conn_01x10": E("C2337", "1x40 2.54mm header (break to 10)", "THT"),
    "Connector_Generic:Conn_02x20_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x20)", "THT"),
    "Connector_Generic:Conn_02x30_Odd_Even": E("C2333", "2x40 2.54mm header (break to 2x30)", "THT"),
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

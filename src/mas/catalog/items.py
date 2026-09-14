"""Spare-part / consumable catalog — ~90 items across 14 categories, costs in INR.

Cost spread runs from ~₹700 (O-ring) to ~₹7,00,000 (turbine journal bearing),
matching doc 02 §10.2. ``unit_cost`` is the current price; ``CONSUMED`` edges
record ``unit_cost_at_time`` equal to it so the two natural cost Cyphers agree
(gate G-16).
"""

from __future__ import annotations

from .spec import ItemSpec

CATEGORIES: tuple[str, ...] = (
    "bearing", "seal", "filter", "gasket", "o_ring", "lubricant", "coupling",
    "impeller", "wear_ring", "sleeve", "valve", "instrument", "fastener", "electrical",
)

# (code, name, category, unit_cost_INR, uom, manufacturer, part_number,
#  stock_qty, reorder_level, lead_time_days)
_ROWS: list[tuple] = [
    # ── bearings ──────────────────────────────────────────────────────────
    ("BRG-001", "Turbine journal bearing, tilting-pad", "bearing", 705000, "each", "Kingsbury", "TP-360", 2, 1, 120),
    ("BRG-002", "Turbine thrust bearing assembly", "bearing", 620000, "each", "Kingsbury", "LEG-300", 1, 1, 140),
    ("BRG-003", "Generator journal bearing", "bearing", 410000, "each", "Michell", "GJ-220", 2, 1, 110),
    ("BRG-004", "BFP tilting-pad thrust bearing", "bearing", 285000, "each", "Waukesha", "WT-180", 2, 1, 90),
    ("BRG-005", "BFP radial journal bearing", "bearing", 190000, "each", "Waukesha", "WJ-160", 3, 1, 75),
    ("BRG-006", "CEP guide bearing, water-lubricated", "bearing", 84000, "each", "Sulzer", "GB-90", 4, 2, 60),
    ("BRG-007", "CEP thrust bearing", "bearing", 118000, "each", "Sulzer", "CT-110", 3, 1, 65),
    ("BRG-008", "Motor DE bearing (roller)", "bearing", 46000, "each", "SKF", "6320-C3", 6, 2, 30),
    ("BRG-009", "Motor NDE bearing (roller)", "bearing", 39000, "each", "SKF", "6316-C3", 6, 2, 30),
    ("BRG-010", "Booster pump bearing set", "bearing", 52000, "set", "SKF", "BP-70", 4, 2, 45),
    ("BRG-011", "Coupling-end journal bearing", "bearing", 96000, "each", "Waukesha", "WC-120", 2, 1, 70),
    ("BRG-012", "Pedestal bearing white-metal reline", "bearing", 135000, "each", "Local", "WM-RELN", 1, 1, 55),
    # ── seals ─────────────────────────────────────────────────────────────
    ("SEL-001", "BFP mechanical seal cartridge set", "seal", 118000, "set", "John Crane", "T2800-125", 3, 1, 60),
    ("SEL-002", "CEP mechanical seal cartridge", "seal", 76000, "set", "John Crane", "5860-90", 3, 1, 55),
    ("SEL-003", "Gland packing set, graphite", "seal", 9500, "set", "Garlock", "GP-98", 10, 3, 20),
    ("SEL-004", "Balance drum seal ring", "seal", 42000, "each", "Sulzer", "BD-140", 4, 2, 50),
    ("SEL-005", "Throttle bush / breakdown seal", "seal", 28000, "each", "Sulzer", "TB-120", 5, 2, 45),
    ("SEL-006", "Generator H2 seal ring set", "seal", 88000, "set", "BHEL", "H2S-300", 2, 1, 80),
    ("SEL-007", "Lip seal, oil-side", "seal", 3200, "each", "Freudenberg", "LS-85", 20, 5, 15),
    ("SEL-008", "Labyrinth seal segment", "seal", 15500, "each", "TurboCare", "LAB-60", 8, 2, 40),
    ("SEL-009", "Seal flush ring assembly", "seal", 12500, "each", "John Crane", "FR-40", 6, 2, 30),
    ("SEL-010", "Steam gland seal ring", "seal", 21000, "each", "TurboCare", "SG-90", 5, 2, 50),
    # ── filters ───────────────────────────────────────────────────────────
    ("FLT-001", "Lube oil filter element, 10 micron", "filter", 6800, "each", "Pall", "HC8314", 24, 8, 20),
    ("FLT-002", "Lube oil filter element, 25 micron", "filter", 5200, "each", "Pall", "HC8300", 24, 8, 20),
    ("FLT-003", "Control oil filter element", "filter", 8900, "each", "Hydac", "0330-D010", 12, 4, 25),
    ("FLT-004", "Suction strainer basket", "filter", 24000, "each", "Eaton", "SS-300", 4, 2, 35),
    ("FLT-005", "Duplex filter changeover kit", "filter", 15500, "kit", "Hydac", "DFK-2", 3, 1, 30),
    ("FLT-006", "Motor cooling air filter", "filter", 3200, "each", "Camfil", "MA-40", 16, 6, 15),
    ("FLT-007", "Seal water fine filter", "filter", 4400, "each", "Pall", "SW-05", 12, 4, 20),
    ("FLT-008", "Air ejector inlet screen", "filter", 1900, "each", "Local", "AE-SCR", 10, 4, 15),
    # ── gaskets ───────────────────────────────────────────────────────────
    ("GSK-001", "Casing joint gasket, spiral wound", "gasket", 14500, "each", "Flexitallic", "CG-300", 6, 2, 30),
    ("GSK-002", "Cover flange gasket set", "gasket", 8600, "set", "Flexitallic", "CF-180", 8, 2, 25),
    ("GSK-003", "Manway gasket", "gasket", 3400, "each", "Garlock", "MW-90", 12, 4, 15),
    ("GSK-004", "Heat-exchanger gasket set", "gasket", 6200, "set", "Klinger", "HX-120", 6, 2, 25),
    ("GSK-005", "Valve bonnet gasket", "gasket", 1800, "each", "Flexitallic", "VB-60", 20, 6, 15),
    ("GSK-006", "Condenser waterbox gasket", "gasket", 11200, "each", "Garlock", "WB-400", 4, 1, 35),
    ("GSK-007", "Turbine casing spill strip gasket", "gasket", 5400, "each", "Flexitallic", "SS-140", 8, 2, 30),
    ("GSK-008", "Instrument tapping gasket", "gasket", 520, "each", "Garlock", "IT-15", 40, 10, 10),
    # ── o-rings ───────────────────────────────────────────────────────────
    ("ORG-001", "O-ring, Viton, 90 mm", "o_ring", 720, "each", "Parker", "V-090", 60, 15, 10),
    ("ORG-002", "O-ring, Viton, 140 mm", "o_ring", 1150, "each", "Parker", "V-140", 40, 10, 10),
    ("ORG-003", "O-ring, EPDM, 60 mm", "o_ring", 680, "each", "Parker", "E-060", 60, 15, 10),
    ("ORG-004", "O-ring kit, assorted", "o_ring", 2800, "kit", "Parker", "OK-01", 12, 4, 12),
    ("ORG-005", "O-ring, high-temp silicone", "o_ring", 1450, "each", "Parker", "S-110", 30, 8, 12),
    ("ORG-006", "Back-up ring set", "o_ring", 950, "set", "Parker", "BR-01", 25, 6, 10),
    # ── lubricants ────────────────────────────────────────────────────────
    ("LUB-001", "Turbine oil ISO VG 32 (208 L drum)", "lubricant", 58000, "drum", "Shell", "Turbo-T32", 6, 2, 20),
    ("LUB-002", "Turbine oil ISO VG 46 (208 L drum)", "lubricant", 61000, "drum", "Shell", "Turbo-T46", 4, 2, 20),
    ("LUB-003", "EP gear oil (20 L pail)", "lubricant", 9800, "pail", "Mobil", "SHC-630", 8, 3, 15),
    ("LUB-004", "High-temp bearing grease (18 kg)", "lubricant", 12500, "keg", "Mobil", "Polyrex-EM", 6, 2, 15),
    ("LUB-005", "Coupling grease (5 kg)", "lubricant", 4200, "tub", "Mobil", "SHC-007", 10, 3, 15),
    ("LUB-006", "Oil-conditioning filter cartridge", "lubricant", 7600, "each", "Kleentek", "KL-A100", 8, 3, 25),
    # ── couplings ─────────────────────────────────────────────────────────
    ("CPL-001", "Hydraulic coupling scoop tube", "coupling", 165000, "each", "Voith", "SVT-1150", 1, 1, 130),
    ("CPL-002", "Gear coupling element set", "coupling", 96000, "set", "Flender", "GCE-320", 2, 1, 90),
    ("CPL-003", "Flexible disc coupling pack", "coupling", 58000, "set", "Rexnord", "DP-220", 3, 1, 70),
    ("CPL-004", "Coupling hub, shrink-fit", "coupling", 78000, "each", "Flender", "CH-200", 2, 1, 85),
    ("CPL-005", "Coupling guard assembly", "coupling", 22000, "each", "Local", "CG-01", 3, 1, 30),
    # ── impellers ─────────────────────────────────────────────────────────
    ("IMP-001", "BFP first-stage impeller", "impeller", 480000, "each", "Sulzer", "FS-260", 1, 1, 160),
    ("IMP-002", "BFP intermediate-stage impeller", "impeller", 320000, "each", "Sulzer", "IS-240", 2, 1, 150),
    ("IMP-003", "CEP bowl impeller", "impeller", 175000, "each", "Sulzer", "BW-180", 2, 1, 120),
    ("IMP-004", "Booster pump impeller", "impeller", 92000, "each", "KSB", "BP-140", 2, 1, 90),
    ("IMP-005", "Impeller wear-ring machining kit", "impeller", 84000, "kit", "Local", "IWR-01", 1, 1, 60),
    # ── wear rings ────────────────────────────────────────────────────────
    ("WRG-001", "Impeller wear ring, stage", "wear_ring", 38000, "each", "Sulzer", "IWR-240", 6, 2, 70),
    ("WRG-002", "Casing wear ring, stage", "wear_ring", 42000, "each", "Sulzer", "CWR-240", 6, 2, 70),
    ("WRG-003", "Balance drum wear ring", "wear_ring", 88000, "each", "Sulzer", "BDW-160", 3, 1, 80),
    ("WRG-004", "CEP bowl wear ring", "wear_ring", 26000, "each", "Sulzer", "BWR-180", 4, 2, 60),
    ("WRG-005", "Throttle bush wear ring", "wear_ring", 14500, "each", "Sulzer", "TWR-120", 5, 2, 50),
    # ── sleeves ───────────────────────────────────────────────────────────
    ("SLV-001", "Shaft sleeve, seal area", "sleeve", 34000, "each", "Sulzer", "SS-90", 6, 2, 55),
    ("SLV-002", "Inter-stage shaft sleeve", "sleeve", 28000, "each", "Sulzer", "IS-90", 6, 2, 55),
    ("SLV-003", "Line-shaft sleeve (CEP)", "sleeve", 18500, "each", "Sulzer", "LS-70", 8, 2, 45),
    ("SLV-004", "Bearing sleeve / journal sleeve", "sleeve", 46000, "each", "Waukesha", "BS-160", 4, 2, 60),
    ("SLV-005", "Distance sleeve set", "sleeve", 9800, "set", "Local", "DS-01", 8, 2, 30),
    # ── valves ────────────────────────────────────────────────────────────
    ("VLV-001", "Minimum-flow recirculation valve", "valve", 285000, "each", "Schroedahl", "ARC-150", 1, 1, 140),
    ("VLV-002", "Non-return / check valve", "valve", 96000, "each", "KSB", "NRV-250", 2, 1, 90),
    ("VLV-003", "Discharge isolation valve", "valve", 128000, "each", "KSB", "GAV-250", 2, 1, 100),
    ("VLV-004", "Governor control valve overhaul kit", "valve", 210000, "kit", "GE", "GCV-OH", 1, 1, 120),
    ("VLV-005", "Relief valve, spring-loaded", "valve", 42000, "each", "Leser", "RV-80", 3, 1, 60),
    ("VLV-006", "Solenoid pilot valve", "valve", 18500, "each", "ASCO", "SPV-24", 6, 2, 30),
    # ── instruments ───────────────────────────────────────────────────────
    ("INS-001", "Bearing RTD PT100 duplex", "instrument", 6800, "each", "WIKA", "RTD-D100", 20, 6, 20),
    ("INS-002", "Vibration proximity probe + driver", "instrument", 118000, "set", "Bently Nevada", "3300-XL", 6, 2, 45),
    ("INS-003", "Casing vibration accelerometer", "instrument", 42000, "each", "Bently Nevada", "200350", 8, 2, 40),
    ("INS-004", "Pressure transmitter", "instrument", 38000, "each", "Emerson", "3051S", 10, 3, 30),
    ("INS-005", "Temperature thermocouple type-K", "instrument", 4200, "each", "WIKA", "TC-K", 24, 8, 20),
    ("INS-006", "Flow transmitter (DP type)", "instrument", 56000, "each", "Emerson", "3051CD", 6, 2, 35),
    ("INS-007", "Speed / key-phasor probe", "instrument", 62000, "each", "Bently Nevada", "KP-330", 4, 2, 45),
    ("INS-008", "Level transmitter", "instrument", 34000, "each", "Emerson", "5300", 6, 2, 30),
    # ── fasteners ─────────────────────────────────────────────────────────
    ("FST-001", "Casing stud & nut kit, high-tensile", "fastener", 7800, "kit", "Local", "STK-24", 12, 4, 20),
    ("FST-002", "Coupling bolt set, fitted", "fastener", 5400, "set", "Local", "CBS-12", 12, 4, 20),
    ("FST-003", "Foundation / hold-down bolt set", "fastener", 3200, "set", "Local", "FBS-08", 16, 4, 15),
    ("FST-004", "Bearing cap bolt kit", "fastener", 1600, "kit", "Local", "BCB-06", 20, 6, 12),
    # ── electrical ────────────────────────────────────────────────────────
    ("ELC-001", "Motor winding insulation reconditioning kit", "electrical", 148000, "kit", "BHEL", "WIR-6K3", 1, 1, 110),
    ("ELC-002", "Bearing insulation kit (shaft grounding)", "electrical", 22000, "kit", "AEGIS", "SGR-160", 4, 2, 40),
    ("ELC-003", "Stator RTD embedded sensor", "electrical", 5600, "each", "WIKA", "SRT-100", 12, 4, 30),
    ("ELC-004", "Space heater element", "electrical", 3400, "each", "Backer", "SH-500", 10, 3, 20),
    ("ELC-005", "Contactor / starter module", "electrical", 28000, "each", "Siemens", "3RT-320", 4, 2, 30),
    ("ELC-006", "Excitation diode wheel set", "electrical", 96000, "set", "ABB", "EDW-300", 1, 1, 90),
]


def build_items() -> list[ItemSpec]:
    items = [
        ItemSpec(
            item_code=r[0], name=r[1], category=r[2], description=r[1],
            unit_cost=float(r[3]), uom=r[4], manufacturer=r[5], part_number=r[6],
            stock_qty=r[7], reorder_level=r[8], lead_time_days=r[9],
        )
        for r in _ROWS
    ]
    codes = [i.item_code for i in items]
    if len(codes) != len(set(codes)):
        raise AssertionError("duplicate item_code in catalog")
    cats = {i.category for i in items}
    missing = set(CATEGORIES) - cats
    if missing:
        raise AssertionError(f"item categories missing: {sorted(missing)}")
    return items

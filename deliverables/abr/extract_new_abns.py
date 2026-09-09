#!/usr/bin/env python3
"""
Extract newly registered ABNs from an ABR bulk-extract XML file and categorise
them by trade using business/trading-name keywords.

Usage:
    python3 extract_new_abns.py <input.xml> [more.xml ...] --since 20260101 --out-dir ./out

Notes:
  * The ABR public extract contains NO industry/ANZSIC code. Trade category is
    inferred from the business name and any registered trading names. Records
    whose name carries no trade signal land in "unclassified".
  * "Newly registered" = ABN status ACT with ABNStatusFromDate on/after --since.
"""
import argparse, csv, html, os, re, sys
from collections import Counter, defaultdict

CHUNK = 1 << 23  # 8 MB

RE_ABN      = re.compile(r'<ABN status="(\w+)" ABNStatusFromDate="(\d{8})">(\d{11})</ABN>')
RE_ETYPE    = re.compile(r'<EntityTypeText>([^<]*)</EntityTypeText>')
RE_NONIND   = re.compile(r'<NonIndividualNameText>([^<]*)</NonIndividualNameText>')
RE_GIVEN    = re.compile(r'<GivenName>([^<]*)</GivenName>')
RE_FAMILY   = re.compile(r'<FamilyName>([^<]*)</FamilyName>')
RE_STATE    = re.compile(r'<State>([^<]*)</State>')
RE_POST     = re.compile(r'<Postcode>([^<]*)</Postcode>')
RE_GST      = re.compile(r'<GST status="(\w+)" GSTStatusFromDate="(\d{8})"')
RE_MAINNAME = re.compile(r'<NonIndividualName type="MN"><NonIndividualNameText>([^<]*)<')

# Ordered most-specific first: the first category whose pattern matches wins.
TRADE_RULES = [
    ("Plumbing & Gasfitting",   r"\bPLUMB|GASFIT|GAS FIT|BLOCKED DRAIN|DRAIN(AGE|ER|S)?\b|HOT WATER|BACKFLOW"),
    ("Electrical",              r"\bELECTRIC(AL|IAN|S)?\b|\bSPARK(Y|IES)\b|SWITCHBOARD|\bLEVEL 2 ASP\b|DATA CABL"),
    ("Solar & Renewables",      r"\bSOLAR\b|PHOTOVOLTAIC|\bPV SYSTEM|BATTERY STORAGE|\bEV CHARG"),
    ("HVAC & Refrigeration",    r"AIR ?CON|AIRCONDITION|\bHVAC\b|REFRIGERAT|\bCOOLROOM|CLIMATE CONTROL|DUCTED"),
    ("Roofing & Guttering",     r"\bROOF(ING|ER|S)?\b|GUTTER|\bDOWNPIPE|COLORBOND|\bRE-?ROOF"),
    ("Carpentry & Joinery",     r"CARPENT|\bJOINER|CABINET ?MAK|\bCABINETRY\b|\bSHOPFIT|\bDECK(ING|S)?\b|\bPERGOLA"),
    ("Concreting & Kerbing",    r"CONCRET|\bKERB(ING)?\b|\bSCREED|\bSLAB(S)?\b|\bPOLISHED CONC"),
    ("Bricklaying & Blockwork", r"BRICKLAY|\bBRICKIE|BLOCKLAY|\bSTONEMASON|MASONRY"),
    ("Plastering & Rendering",  r"PLASTER|\bRENDER(ING|ER)?\b|\bGYPROCK|\bDRYWALL|\bCORNICE"),
    ("Painting & Decorating",   r"\bPAINT(ING|ER|ERS)?\b|\bDECORATOR|SPRAY ?PAINT"),
    ("Tiling & Waterproofing",  r"\bTILE(R|RS|S)?\b|\bTILING\b|WATERPROOF|\bMEMBRANE\b"),
    ("Flooring & Carpet",       r"FLOOR(ING|S)?\b|\bCARPET|\bVINYL PLANK|TIMBER FLOOR|\bEPOXY FLOOR"),
    ("Glazing & Windows",       r"\bGLAZ(ING|IER)|\bGLASS\b|\bWINDOW(S)?\b|SHOWER SCREEN|\bSPLASHBACK"),
    ("Fencing & Gates",         r"\bFENC(E|ES|ING)\b|\bGATE(S)?\b|\bBALUSTRAD|\bRETAINING WALL"),
    ("Landscaping & Gardening", r"LANDSCAP|\bGARDEN(ING|S|ER)?\b|\bLAWN|\bTURF|\bMOWING|\bIRRIGATION|\bARBOR|TREE (LOPP|SERVIC|REMOV|CARE)"),
    ("Earthmoving & Excavation",r"EXCAVAT|EARTH ?MOV|\bBOBCAT|\bDIGG|\bTIPPER|\bPLANT HIRE|\bBORING\b|\bPILING\b|\bTRENCH"),
    ("Civil & Infrastructure",  r"\bCIVIL\b|\bASPHALT|\bROAD ?(WORKS|MARK|BASE)|\bBITUMEN|\bSURVEY(ING|OR)"),
    ("Demolition & Asbestos",   r"DEMOLITION|\bDEMO ?\&|ASBESTOS|\bSTRIP ?OUT"),
    ("Scaffolding & Rigging",   r"SCAFFOLD|\bRIGGING\b|\bRIGGER|\bDOGGING\b|\bCRANE(S)?\b|\bHOIST"),
    ("Welding & Metal Fab",     r"\bWELD(ING|ER|S)?\b|\bFABRICAT|\bBOILERMAK|SHEET ?METAL|\bSTEEL(WORK|FIX)|\bENGINEERING WORKS"),
    ("Building & Construction", r"\bBUILDER(S)?\b|\bBUILDING\b|CONSTRUCT|\bRENOVAT|\bHOME EXTENSION|\bHOUSE EXTENSION|\bCARPORT|\bGRANNY FLAT|\bFORMWORK|\bFRAM(ING|ER)\b"),
    ("Automotive & Mechanical", r"\bMECHANIC|\bAUTOMOTIVE|\bAUTO ?(ELEC|REPAIR|SERV)|\bPANEL ?BEAT|\bSMASH REPAIR|\bTYRE|\bDIESEL"),
    ("Transport & Haulage",     r"\bHAUL(AGE|ING)|\bTRUCK(ING|S)?\b|\bFREIGHT|\bCOURIER|\bTRANSPORT\b|\bREMOVAL(IST|S)"),
    ("Cleaning Services",       r"\bCLEAN(ING|ERS?)\b|\bPRESSURE WASH|\bWINDOW CLEAN|\bCARPET CLEAN"),
    ("Pest Control",            r"\bPEST\b|\bTERMITE|\bVERMIN"),
    ("Security & Locksmith",    r"\bSECURITY\b|\bLOCKSMITH|\bALARM(S)?\b|\bCCTV\b|\bACCESS CONTROL"),
    ("Signage & Print",         r"\bSIGN(AGE|S|WRIT)|\bPRINT(ING)?\b|\bVEHICLE WRAP"),
    ("Pools & Spas",            r"\bPOOL(S)?\b(?! ?TABLE)|POOLS? (AND|&) SPAS?|SWIM ?SPA"),
    ("Mining & Resources",      r"\bMINING\b|\bDRILL(ING)?\b|\bQUARR|\bRESOURCES\b"),
    ("Trade Services (general)",r"\bHANDY ?(MAN|PERSON)|\bMAINTENANCE\b|\bREPAIR(S)?\b|\bINSTALLATION(S)?\b|\bSERVICES? & MAINT|\bPROPERTY SERVICES"),
]
TRADE_RULES = [(n, re.compile(p)) for n, p in TRADE_RULES]

STATES = {"NSW","VIC","QLD","SA","WA","TAS","NT","ACT"}


def classify(names):
    hay = " | ".join(names).upper()
    for name, pat in TRADE_RULES:
        if pat.search(hay):
            return name
    return "Unclassified"


def iter_records(paths):
    for path in paths:
        tail = ""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            while True:
                buf = fh.read(CHUNK)
                if not buf:
                    break
                tail += buf
                parts = tail.split("</ABR>")
                tail = parts.pop()
                for p in parts:
                    i = p.find("<ABR ")
                    if i != -1:
                        yield p[i:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--since", default="20260101", help="YYYYMMDD; ABNs active from this date onward")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    out_csv = os.path.join(args.out_dir, f"new-abns-since-{args.since}.csv")

    total = kept = 0
    by_trade = Counter()
    by_trade_state = defaultdict(Counter)
    by_month = Counter()

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["abn","abn_start_date","month","trade_category","entity_type",
                    "name","trading_names","state","postcode","gst_registered","gst_from"])

        for rec in iter_records(args.inputs):
            total += 1
            m = RE_ABN.search(rec)
            if not m:
                continue
            status, start, abn = m.groups()
            if status != "ACT" or start < args.since:
                continue

            et = RE_ETYPE.search(rec)
            entity_type = et.group(1) if et else ""

            main_name = ""
            rec = html.unescape(rec)
            mm = RE_MAINNAME.search(rec)
            if mm:
                main_name = mm.group(1).strip()
            all_nonind = [n.strip() for n in RE_NONIND.findall(rec) if n.strip()]
            if not main_name:
                g, f = RE_GIVEN.search(rec), RE_FAMILY.search(rec)
                if g or f:
                    main_name = " ".join(x.group(1).strip() for x in (g, f) if x)
                elif all_nonind:
                    main_name = all_nonind[0]
            trading = [n for n in all_nonind if n != main_name]

            st = RE_STATE.search(rec)
            state = st.group(1).strip() if st else ""
            if state not in STATES:
                state = state or "UNKNOWN"
            pc = RE_POST.search(rec)
            postcode = pc.group(1).strip() if pc else ""

            gst_reg, gst_from = "N", ""
            gm = RE_GST.search(rec)
            if gm and gm.group(1) == "ACT":
                gst_reg, gst_from = "Y", gm.group(2)

            trade = classify([main_name] + trading)
            month = f"{start[:4]}-{start[4:6]}"

            kept += 1
            by_trade[trade] += 1
            by_trade_state[trade][state] += 1
            by_month[month] += 1

            w.writerow([abn, f"{start[:4]}-{start[4:6]}-{start[6:]}", month, trade, entity_type,
                        main_name, "; ".join(trading), state, postcode, gst_reg, gst_from])

    # Trades-only CSV (drops Unclassified) — the actionable list
    trades_csv = os.path.join(args.out_dir, f"new-abns-since-{args.since}-trades-only.csv")
    with open(out_csv, encoding="utf-8") as src, open(trades_csv, "w", newline="", encoding="utf-8") as dst:
        r = csv.reader(src); w2 = csv.writer(dst)
        w2.writerow(next(r))
        rows = [row for row in r if row[3] != "Unclassified"]
        rows.sort(key=lambda x: (x[3], x[7], x[1]))
        w2.writerows(rows)
    print(f"trades  -> {trades_csv}  ({len(rows):,} rows)")

    # Summary CSV: trade x state
    sum_csv = os.path.join(args.out_dir, f"new-abns-since-{args.since}-summary.csv")
    cols = ["NSW","VIC","QLD","WA","SA","TAS","ACT","NT","UNKNOWN"]
    with open(sum_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["trade_category","total"] + cols)
        for trade, n in by_trade.most_common():
            w.writerow([trade, n] + [by_trade_state[trade].get(c, 0) for c in cols])

    print(f"records scanned : {total:,}")
    print(f"new active ABNs : {kept:,}  (since {args.since})")
    print(f"detail  -> {out_csv}")
    print(f"summary -> {sum_csv}\n")
    print("By month:")
    for mth in sorted(by_month):
        print(f"  {mth}  {by_month[mth]:>7,}")
    print("\nBy trade category:")
    for trade, n in by_trade.most_common():
        print(f"  {trade:<28} {n:>7,}  ({n/kept*100:4.1f}%)")


if __name__ == "__main__":
    main()

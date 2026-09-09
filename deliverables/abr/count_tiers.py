#!/usr/bin/env python3
"""Tier A pre-build count against the live ABR extract (one member per ZIP).

Measures, from a SINGLE snapshot:
  * ABNs whose GST status is ACT with GSTStatusFromDate in the last 7/14/30/90 days
  * broken down by ABN age band and state
  * plus a GST-date BACKDATING check (GSTStatusFromDate vs recordLastUpdatedDate)

Caveat, stated in the output: tier A in the spec fires on a GST ACT transition detected by
diffing two consecutive snapshots. Only one snapshot is published at a time, so this measures
the proxy. The backdating check tells us how good a proxy it is.
"""
import urllib.request, struct, zlib, re, sys, collections, datetime

ZIPS = {
 "public_split_1_10.zip":  "https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/0ae4d427-6fa8-4d40-8e76-c6909b5a071b/download/public_split_1_10.zip",
 "public_split_11_20.zip": "https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/635fcb95-7864-4509-9fa7-a62a6e32b62d/download/public_split_11_20.zip",
}
COMPRESSED_BYTES = 70*1024*1024   # enough to inflate one full ~630 MB member

RE_REC   = re.compile(r'<ABR\b.*?</ABR>', re.S)
RE_UPD   = re.compile(r'recordLastUpdatedDate="(\d{8})"')
RE_ABN   = re.compile(r'<ABN status="(\w+)" ABNStatusFromDate="(\d{8})">')
RE_GST   = re.compile(r'<GST[^>]*?status="(\w+)"[^>]*?GSTStatusFromDate="(\d{8})"')
RE_ETYPE = re.compile(r'<EntityTypeInd>([^<]*)</EntityTypeInd>')
RE_STATE = re.compile(r'<State>([^<]*)</State>')
RE_BN    = re.compile(r'<NonIndividualName type="BN"><NonIndividualNameText>([^<]*)<')
RE_MN    = re.compile(r'<NonIndividualName type="MN"><NonIndividualNameText>([^<]*)<')

def fetch(url, a, b):
    r = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}",
                                             "User-Agent": "maintain-media-tiera-count"})
    return urllib.request.urlopen(r, timeout=300).read()

def member_stream(url):
    head = fetch(url, 0, 63)
    assert head[:4] == b'PK\x03\x04'
    nlen, elen = struct.unpack('<HH', head[26:30])
    name = head[30:30+nlen].decode()
    off = 30 + nlen + elen
    comp = fetch(url, off, off + COMPRESSED_BYTES - 1)
    return name, zlib.decompressobj(-15).decompress(comp).decode('utf-8', 'replace')

def d(s): return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))

SNAP = d("20260903")
STATES = {"NSW","VIC","QLD","SA","WA","TAS","NT","ACT"}
COMPANYLIKE = {"PRV","PUB","CGE","SGE","LGE","OIE","CCB","FPT","FXT","DIT","DTT","FUT","HYT",
               "PQT","PST","PTT","SGT","TRT","UIT","CSA","CCS","CCU","NRF","ARF","POF","SMF"}

def band(months):
    if months is None: return "unknown"
    if months < 12:  return "<12mo"
    if months < 60:  return "12-59mo (TIER A)"
    if months < 120: return "60-119mo"
    return "120mo+"

tot = 0
gst_recent = collections.Counter()          # window -> count
tiera_state = collections.Counter()
tiera_band  = collections.Counter()
tiera_named = collections.Counter()
backdate    = collections.Counter()
backdate_days = []
members = []

for zname, url in ZIPS.items():
    mname, xml = member_stream(url)
    members.append(mname)
    print(f"  inflated {mname}: {len(xml):,} chars", file=sys.stderr)
    for rec in RE_REC.findall(xml):
        tot += 1
        ma = RE_ABN.search(rec)
        if not ma: continue
        astat, adate = ma.groups()
        if astat != "ACT": continue
        mg = RE_GST.search(rec)
        if not mg: continue
        gstat, gdate = mg.groups()
        if gstat != "ACT": continue
        try: gd = d(gdate)
        except ValueError: continue
        age_days = (SNAP - gd).days
        for w in (7, 14, 30, 90, 365):
            if 0 <= age_days < w: gst_recent[w] += 1
        # backdating: GST date vs the record's own last-updated date
        mu = RE_UPD.search(rec)
        if mu and 0 <= age_days < 365:
            try:
                gap = (d(mu.group(1)) - gd).days
                backdate_days.append(gap)
                backdate["<=7d" if gap <= 7 else "8-30d" if gap <= 30 else
                         "31-365d" if gap <= 365 else ">365d"] += 1
            except ValueError: pass
        if not (0 <= age_days < 7): continue
        # ABN age at snapshot
        try: months = (SNAP - d(adate)).days // 30
        except ValueError: months = None
        b = band(months)
        tiera_band[b] += 1
        if b != "12-59mo (TIER A)": continue
        st = RE_STATE.search(rec)
        tiera_state[(st.group(1).strip() if st and st.group(1).strip() in STATES else "UNKNOWN")] += 1
        et = RE_ETYPE.search(rec)
        etv = et.group(1).strip() if et else ""
        tiera_named["company/trust" if etv in COMPANYLIKE else "individual/other"] += 1
        tiera_named["has BN name" if RE_BN.search(rec) else "no BN name"] += 1
        tiera_named["has MN name" if RE_MN.search(rec) else "no MN name"] += 1

SCALE = 20 / len(members)
print("="*76)
print(f"TIER A PRE-BUILD COUNT — snapshot 2026-09-03, members: {', '.join(members)}")
print(f"records scanned: {tot:,}   (extrapolation factor x{SCALE:.0f} for all 20 members)")
print("="*76)
print("\nGST status = ACT with GSTStatusFromDate inside window (sampled members):")
for w in (7,14,30,90,365):
    print(f"   last {w:>3}d : {gst_recent[w]:>8,}   -> national est. {gst_recent[w]*SCALE:>10,.0f}")
print("\nGST-date BACKDATING (GSTStatusFromDate vs recordLastUpdatedDate, GST dates < 1yr old):")
n=sum(backdate.values())
for k in ("<=7d","8-30d","31-365d",">365d"):
    v=backdate[k]
    print(f"   {k:>9}: {v:>8,}  ({v/n*100:5.1f}%)" if n else k)
if backdate_days:
    backdate_days.sort()
    print(f"   median gap: {backdate_days[len(backdate_days)//2]}d   n={len(backdate_days):,}")
print("\nGST ACT in last 7d, by ABN age band:")
for k,v in tiera_band.most_common():
    print(f"   {k:<20} {v:>7,}  -> national est. {v*SCALE:>9,.0f}")
ta=tiera_band["12-59mo (TIER A)"]
print(f"\n>>> TIER A (GST ACT last 7d AND ABN 12-59 months old): {ta:,} sampled")
print(f">>> NATIONAL ESTIMATE: {ta*SCALE:,.0f} per week")
print("\nTier A by state:")
for k,v in tiera_state.most_common():
    print(f"   {k:<8} {v:>6,}  -> national est. {v*SCALE:>8,.0f}")
qn=tiera_state['QLD']*SCALE
print(f"\n   QLD only national est.: {qn:,.0f}/week")
print("\nTier A composition:")
for k,v in sorted(tiera_named.items()):
    print(f"   {k:<20} {v:>6,}  ({v/ta*100:5.1f}%)" if ta else k)

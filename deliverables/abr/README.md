# New ABN extract — trade categorisation

Source: ABR public bulk extract `20260902_Public10.xml` (file 10 of 10; extract time 2026-08-25).

## Outputs

| File | Rows | What it is |
|---|---|---|
| `new-abns-since-20260101.csv` | 45,556 | Every ABN that became ACTIVE on/after 1 Jan 2026 in this file |
| `new-abns-since-20260101-trades-only.csv` | 2,101 | The same list with `Unclassified` removed — the actionable list |
| `new-abns-since-20260101-summary.csv` | 31 | Trade category × state counts |

Columns: `abn, abn_start_date, month, trade_category, entity_type, name, trading_names,
state, postcode, gst_registered, gst_from`.

## How to re-run

```bash
python3 extract_new_abns.py <file.xml> [more.xml ...] --since YYYYMMDD --out-dir ./out
```

All ten split files at once (~10.2M records, roughly 5 minutes):

```bash
python3 extract_new_abns.py ~/Downloads/public_split_1_10/*.xml --since 20260101 --out-dir ./out-full
```

No dependencies beyond the Python 3 standard library. Streams the file in 8 MB chunks,
so memory use is flat regardless of input size.

## Method and its limits — read this before using the list

* **"Newly created" = ABN status `ACT` with `ABNStatusFromDate` on/after `--since`.** That is
  the ABN's active-from date, which is the closest thing the extract has to a registration date.
* **The ABR public extract contains no industry or ANZSIC code.** Trade category is inferred
  from the entity's main name plus any registered trading names, using an ordered keyword
  ruleset in `extract_new_abns.py` (first match wins, most specific rules first). Edit
  `TRADE_RULES` to add or tighten categories.
* **95% of new ABNs cannot be classified from this data, and that is a data ceiling, not a
  tuning problem.** 33,000 of the 45,556 are sole traders whose only recorded name is the
  person's legal name — no business name, no industry code. Only ~12,500 records carry a
  company or trading name that can be read at all.
* Spot-check of 20 random classifications found 2 false positives (both fixed:
  "hair extensions" and "pool table repairs"). Precision on the remainder was clean.
* Records with a start date in the future (13 rows, Sep 2026 – Feb 2027) are in the source
  data as-is and have been left untouched.

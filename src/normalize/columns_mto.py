"""Column mapping: legacy MTO delivery .DAT (2011 → today) -> unified delivery schema.

Verified against a real file (MTO_03012011.DAT):
  line 1: title, line 2: "Trade Date <DD-MON-YYYY>,...", line 3: 6-name header
  data rows have SEVEN fields — a SERIES column the header omits:
      20,<sr>,<SYMBOL>,<SERIES>,<qty_traded>,<deliv_qty>,<deliv_per>
Only record type 20 (equities) rows are kept; 9xx rows are indices.
Only EQ-series rows are loaded: delivery features are computed on the eligible (EQ)
universe; ponytail: non-EQ delivery rows are dropped at load — if a future feature
needs them, re-normalize from the cache (never re-download).
"""
SKIPROWS = 4  # title + 10,MTO counts + Trade Date + column-name line (names come from POSITIONS)
POSITIONS = ["record_type", "sr_no", "symbol", "series", "qty_traded", "deliv_qty", "deliv_per"]
RECORD_TYPE_KEEP = 20
SERIES_KEEP = {"EQ"}
DATE_LINE = 2  # 0-indexed: line 1 is the 10,MTO,<date>,... counts line; line 2 carries Trade Date <DD-MON-YYYY>
DATE_REGEX = r"Trade Date <(\d{2}-[A-Z]{3}-\d{4})>"
DATE_FORMAT = "%d-%b-%Y"
# Fallback date source: NSE's own archive has ~7 days (2017-2019) with line 3 truncated by one
# byte ("rade Date <...>"), so the Trade Date line can be missing. The counts line is intact and
# also carries the date; its DDMMYYYY digits are unambiguous (e.g. 30032017).
COUNTS_LINE = 1  # 0-indexed: the 10,MTO,<DDMMYYYY>,... line
COUNTS_DATE_RE = r"^10,MTO,(\d{8}),"

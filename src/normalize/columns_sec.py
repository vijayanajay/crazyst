"""Column mapping: sec_bhavdata_full delivery CSV (2019-10-01 → today) -> unified delivery schema.

Verified against a real file (sec_bhavdata_full_03082026.csv): the CSV is space-padded
("SYMBOL, SERIES, ...") — read with skipinitialspace. Only EQ-series rows are loaded
(same rationale as columns_mto.py); DELIV_QTY/DELIV_PER map straight through.
"""
COLS = {
    "SYMBOL": "symbol",
    "SERIES": "series",
    "DATE1": "date",
    "DELIV_QTY": "deliv_qty",
    "DELIV_PER": "deliv_per",
}
DATE_FORMAT = "%d-%b-%Y"
SERIES_KEEP = {"EQ"}
